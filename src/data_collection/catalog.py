#!/usr/bin/env python3
"""Split the unchanged Product template by taxonomy, then merge JSON tables."""
import argparse
from collections import Counter
import json
import hashlib
import re
from pathlib import Path

TAXONOMIES = ("hotel", "flight", "attraction", "combo", "golf")
FIELDS = {"productId", "name", "taxonomy", "destination", "description", "attributes",
          "unitPrice", "currency", "available", "sourceRef", "imageUrl", "availableFrom", "availableTo"}


def read_products(path):
    text = Path(path).read_text(encoding="utf-8")
    return json.loads(text) if text.lstrip().startswith("[") else [json.loads(line) for line in text.split("\n") if line.strip()]  # không dùng splitlines(): nó cắt cả ở U+0085/U+2028 trong chuỗi JSON


def validate(rows):
    unique = {}
    for row in rows:
        if set(row) != FIELDS or row["taxonomy"] not in TAXONOMIES or not isinstance(row["attributes"], dict):
            raise ValueError(f"Product không đúng template 13 trường: {row.get('productId')}")
        key = row["productId"]
        if not isinstance(key, str) or not key:
            raise ValueError("productId phải là chuỗi có giá trị")
        if key in unique and row != unique[key]:
            raise ValueError(f"Conflict productId {key}: hai bản ghi khác nhau; chưa ghi đè output")
        unique[key] = row
    for row in unique.values():
        parent = row["attributes"].get("parentProductId")
        if parent and parent not in unique:
            raise ValueError(f"Thiếu parentProductId {parent} của {row['productId']}")
    return sorted(unique.values(), key=lambda r: (r["taxonomy"], r["destination"] or "", r["productId"]))


def write_json(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def split_catalog(input_path, folder):
    rows = validate(read_products(input_path))
    for taxonomy in TAXONOMIES:
        write_json(folder / f"{taxonomy}.json", [r for r in rows if r["taxonomy"] == taxonomy])
    return dict(Counter(r["taxonomy"] for r in rows))


def city_catalogs(input_path, folder):
    """Export all taxonomies together per destination; preserve canonical IDs."""
    from collectors.textutil import fold
    rows = validate(read_products(input_path))
    groups = {}
    for row in rows:
        groups.setdefault(row["destination"] or "Chưa xác định", []).append(row)
    slugs = {city: re.sub(r"[^a-z0-9]+", "-", fold(city)).strip("-") or "unknown" for city in groups}
    counts = Counter(slugs.values())
    index = []
    for city, products in sorted(groups.items()):
        slug = slugs[city]
        if counts[slug] > 1:
            slug += "-" + hashlib.sha256(city.encode()).hexdigest()[:8]
        filename = slug + ".json"
        write_json(folder / filename, products)
        index.append({"destination": city, "file": filename, "products": len(products),
                      "taxonomyCounts": dict(Counter(r["taxonomy"] for r in products))})
    write_json(folder / "_index.json", index)
    return index


def merge_catalog(folder, output):
    rows = []
    for taxonomy in TAXONOMIES:
        table = read_products(folder / f"{taxonomy}.json")
        if any(r.get("taxonomy") != taxonomy for r in table):
            raise ValueError(f"Có taxonomy sai trong {taxonomy}.json")
        rows.extend(table)
    rows = validate(rows)
    write_json(output, rows)
    return len(rows)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    split = sub.add_parser("split")
    split.add_argument("--input", type=Path, default=Path("data/products.jsonl"))
    split.add_argument("--out", type=Path, default=Path("data/catalog"))
    merge = sub.add_parser("merge")
    merge.add_argument("--from-dir", type=Path, default=Path("data/catalog"))
    merge.add_argument("--out", type=Path, default=Path("data/products.json"))
    cities = sub.add_parser("cities", help="xuất mỗi thành phố một JSON chứa mọi taxonomy")
    cities.add_argument("--input", type=Path, default=Path("data/products.jsonl"))
    cities.add_argument("--out", type=Path, default=Path("data/cities"))
    args = parser.parse_args(argv)
    try:
        if args.command == "cities":
            result = city_catalogs(args.input, args.out)
        elif args.command == "split":
            result = split_catalog(args.input, args.out)
        else:
            result = merge_catalog(args.from_dir, args.out)
    except (ValueError, OSError) as exc:
        parser.error(str(exc))
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
