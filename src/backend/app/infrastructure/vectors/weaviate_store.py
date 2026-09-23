"""Collection `Product` trên Weaviate (docs/prd/architecture.md §5, data-model.md entity WEAVIATE_PRODUCT).

Gọi REST `/v1` bằng httpx thay vì `weaviate-client` để không thêm dependency. Collection khai báo
`vectorizer: none`: backend tự embed rồi tự ghi, Weaviate không giữ khóa Cohere. Weaviate chỉ giữ
vector + `productId` / `modelVersion` / `textHash`; mọi thuộc tính hiển thị vẫn lấy từ Postgres.

Hiện chỉ có phần ghi cho job `embed_products`; đường truy vấn của backend chưa chuyển sang đây.
"""
from __future__ import annotations

from dataclasses import dataclass

import httpx

COLLECTION = "Product"
_PAGE = 500
_BATCH = 100


@dataclass(frozen=True)
class StoredVector:
    object_id: str       # UUID do Weaviate cấp
    model_version: str
    text_hash: str


def normalise_url(url: str) -> str:
    """WEAVIATE_URL của Weaviate Cloud thường chỉ là hostname; thêm https:// khi thiếu scheme."""
    url = url.strip().strip('"').rstrip("/")
    return url if url.startswith(("http://", "https://")) else f"https://{url}"


class WeaviateVectorStore:
    def __init__(self, url: str, api_key: str = "", *, client: httpx.Client | None = None):
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        self._client = client or httpx.Client(timeout=60)
        self._base = normalise_url(url) + "/v1"
        self._headers = headers

    def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        return self._client.request(method, self._base + path, headers=self._headers, **kwargs)

    def exists(self) -> bool:
        response = self._request("GET", f"/schema/{COLLECTION}")
        if response.status_code == 404:
            return False
        response.raise_for_status()
        return True

    def ensure_collection(self) -> bool:
        """Tạo collection nếu chưa có. Trả True khi vừa tạo."""
        if self.exists():
            return False
        text = {"dataType": ["text"], "tokenization": "field", "indexSearchable": False}
        schema = {
            "class": COLLECTION,
            "vectorizer": "none",
            "vectorIndexType": "hnsw",
            "vectorIndexConfig": {"distance": "cosine"},
            "properties": [
                {"name": "productId", **text, "description": "Khóa nối logic về cdp.products — không phải FK"},
                {"name": "modelVersion", **text},
                {"name": "textHash", **text},
            ],
        }
        self._request("POST", "/schema", json=schema).raise_for_status()
        return True

    def stored(self) -> dict[str, StoredVector]:
        """productId → object đang có, đọc hết collection theo cursor `after`."""
        found: dict[str, StoredVector] = {}
        after = None
        while True:
            params = {"class": COLLECTION, "limit": _PAGE}
            if after:
                params["after"] = after
            response = self._request("GET", "/objects", params=params)
            response.raise_for_status()
            objects = response.json().get("objects") or []
            for obj in objects:
                props = obj.get("properties") or {}
                found[props.get("productId", "")] = StoredVector(
                    obj["id"], props.get("modelVersion", ""), props.get("textHash", "")
                )
            if len(objects) < _PAGE:
                return found
            after = objects[-1]["id"]

    def upsert(self, rows: list[dict]) -> None:
        """rows: {productId, modelVersion, textHash, vector, object_id?}. Có object_id thì ghi đè, không thì Weaviate cấp UUID."""
        for i in range(0, len(rows), _BATCH):
            objects = []
            for row in rows[i : i + _BATCH]:
                obj = {
                    "class": COLLECTION,
                    "properties": {k: row[k] for k in ("productId", "modelVersion", "textHash")},
                    "vector": [float(x) for x in row["vector"]],
                }
                if row.get("object_id"):
                    obj["id"] = row["object_id"]
                objects.append(obj)
            response = self._request("POST", "/batch/objects", json={"objects": objects})
            response.raise_for_status()
            errors = [
                item["result"]["errors"]
                for item in response.json()
                if (item.get("result") or {}).get("errors")
            ]
            if errors:
                raise RuntimeError(f"Weaviate từ chối {len(errors)} object, ví dụ: {errors[0]}")

    def delete(self, object_ids: list[str]) -> None:
        for object_id in object_ids:
            response = self._request("DELETE", f"/objects/{COLLECTION}/{object_id}")
            if response.status_code != 404:
                response.raise_for_status()
