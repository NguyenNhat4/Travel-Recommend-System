"""Dựng, kiểm và nối case mới vào dataset test case của Itinerary Agent (tab "Thêm case" của eval_app.py).

Logic thuần, không phụ thuộc Streamlit. Hướng dẫn từng khoá `expect` nằm ở `FIELD_HELP`; test ép nó phủ đủ
`EXPECT_KEYS` của runner, nên thêm khoá mới vào `golden.py` thì phải viết hướng dẫn ở đây. Nguồn của nội dung hướng
dẫn: `docs/spec/agent/golden-dataset-how-to-add-more-case.md` mục 4–6.
"""

from __future__ import annotations

import re
import subprocess
import tempfile
import textwrap
from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from src.evaluation.agent.golden import (
    DEFAULT_DATASET, EXPECT_KEYS, REPO_ROOT, Case, load_dataset, resolve_dates,
)

DATASET_PATH = REPO_ROOT / DEFAULT_DATASET
REQUIREMENTS_PATH = REPO_ROOT / "docs/prd/requirements.md"
FR_PATTERN = re.compile(r"^(FR|NFR)-[A-Z]+-\d+$")
CASE_ID_PATTERN = re.compile(r"^TC-(\d+)$")

# ItineraryResponse là oneOf không có "status" phẳng; bốn giá trị discriminator (giống test_golden.py).
STATUSES = ("COMPLETED", "NEEDS_CLARIFICATION", "NO_RESULTS", "FALLBACK")
# Mã warning không phải enum trong contract; đây là các mã code agent đang phát, người dùng vẫn gõ được mã khác.
WARNING_CODES = (
    "DAY_WITHOUT_PRODUCTS", "OVER_BUDGET", "PRODUCT_DROPPED_UNAVAILABLE", "PRODUCT_DROPPED_EXCLUDED",
    "PRODUCT_DROPPED_DATE", "PRODUCT_DROPPED_DESTINATION", "PRODUCT_DROPPED_TAXONOMY", "PRODUCT_DROPPED_PRICE",
    "PRODUCT_DROPPED_ATTRIBUTES", "PRODUCT_DROPPED_NAMED_REQUIREMENT", "PRODUCT_DROPPED_PRICE_BASIS",
    "PRODUCT_DETAIL_UNAVAILABLE", "PRODUCT_DROPPED_DUPLICATE",
)
HTTP_STATUSES = (200, 400, 404, 422, 503)


@dataclass(frozen=True)
class FieldHelp:
    label: str      # nhãn hiện trên form
    checks: str     # runner kiểm gì
    when: str       # khi nào nên / không nên dùng
    example: str    # ví dụ YAML

    def tooltip(self) -> str:
        return f"**Kiểm:** {self.checks}\n\n**Khi nào dùng:** {self.when}\n\n**Ví dụ:** `{self.example}`"


FIELD_HELP: dict[str, FieldHelp] = {
    "httpStatus": FieldHelp(
        "Mã HTTP", "Mã HTTP của response phải đúng bằng số này.",
        "Gần như mọi lượt: 200 cho hỏi lại/lịch trình; 422 cho điểm đến ngoài catalog; 400 cho yêu cầu ngoài phạm vi.",
        "httpStatus: 200"),
    "status": FieldHelp(
        "Trạng thái (status)", "`status` của response phải thuộc tập đã chọn.",
        "Chọn nhiều giá trị khi kết quả phụ thuộc dữ liệu catalog (điểm đến ít sản phẩm có thể ra FALLBACK hợp lệ). "
        "NEEDS_CLARIFICATION = agent hỏi lại; COMPLETED = có lịch trình; FALLBACK = chỉ gợi ý sản phẩm; "
        "NO_RESULTS = không tìm được gì.",
        "status: [COMPLETED, FALLBACK]"),
    "errorCode": FieldHelp(
        "Mã lỗi (errorCode)", "`error.code` của response lỗi phải đúng bằng mã này.",
        "Chỉ dùng cho lượt mong agent trả lỗi, ví dụ điểm đến ngoài catalog → UNSUPPORTED_DESTINATION. "
        "Bỏ trống với lượt bình thường.",
        "errorCode: UNSUPPORTED_DESTINATION"),
    "intent": FieldHelp(
        "Ý định trích được (intent)",
        "Từng trường intent agent hiểu được phải bằng giá trị ghi (đọc `intent`, không có thì `knownIntent`).",
        "Chỉ khoá trường mà câu người dùng nói rõ. \"Đi Đà Nẵng 3 ngày cho gia đình\" không nói số người nên không "
        "khoá party. Điểm đến phải viết đúng tên catalog (TP. Hồ Chí Minh, không viết TPHCM). Ngày dùng placeholder "
        "dạng :iso, ví dụ \"{today+7:iso}\".",
        "intent: {destination: Đà Nẵng, days: 3, startDate: \"{today+7:iso}\", party.adults: 2}"),
    "missingFieldsInclude": FieldHelp(
        "Trường còn thiếu (missingFieldsInclude)",
        "Các giá trị đã chọn phải có trong `missingFields` (được phép có thêm giá trị khác).",
        "Lượt agent phải hỏi lại vì thiếu thông tin. Câu chỉ có điểm đến + số ngày thì agent hỏi startDate, party, "
        "budget.",
        "missingFieldsInclude: [startDate, party, budget]"),
    "toolCalled": FieldHelp(
        "Có gọi tool tìm kiếm (toolCalled)",
        "Node `tool` có truy xuất dữ liệu (Search/Recommendation) ở lượt này hay không.",
        "false cho lượt hỏi lại hoặc trò chuyện (chưa đủ thông tin thì không được tìm); true khi lượt phải dựng lịch.",
        "toolCalled: false"),
    "nodesInclude": FieldHelp(
        "Node bắt buộc chạy (nodesInclude)", "Các node đã chọn phải xuất hiện trong trace của lượt.",
        "Khi luồng có spec rõ phải đi qua node nào, ví dụ hỏi lại phải qua clarify. Không dùng khi code cho phép "
        "nhiều nhánh hợp lệ.",
        "nodesInclude: [clarify]"),
    "nodesExclude": FieldHelp(
        "Node không được chạy (nodesExclude)", "Các node đã chọn không được xuất hiện trong trace.",
        "Chặn nhánh sai mà không khoá nhánh đúng, ví dụ câu hỏi thời tiết có thể ra converse hoặc lỗi 400 nhưng "
        "không bao giờ được vào tool.",
        "nodesExclude: [tool]"),
    "forbiddenText": FieldHelp(
        "Chuỗi cấm (forbiddenText)",
        "Không chuỗi nào được xuất hiện ở bất kỳ đâu trong response (không phân biệt hoa thường).",
        "Chỉ cho chuỗi đặc trưng của lỗi: câu trả lời cố định cũ, tên sản phẩm bịa. Không dùng tên điểm đến vì câu "
        "trả lời đúng vẫn nhắc tới nó. Mỗi dòng một chuỗi.",
        "forbiddenText: [\"Lịch trình đã được hoàn tất\"]"),
    "excludeProductsFromTurn": FieldHelp(
        "Không lặp sản phẩm của lượt trước (excludeProductsFromTurn)",
        "productId của lượt `turn` (đếm từ 1) không được xuất hiện lại ở lượt này. role=stay chỉ so chỗ ở; "
        "role=any so cả chỗ ở lẫn hoạt động.",
        "Lượt người dùng xin đổi khách sạn/hoạt động khác. Số lượt tính cả lượt hỏi lại.",
        "excludeProductsFromTurn: {turn: 1, role: stay}"),
    "minActivities": FieldHelp(
        "Số hoạt động tối thiểu (minActivities)", "Tổng số slot có sản phẩm trong lịch ít nhất bằng số này.",
        "Chỉ cho điểm đến catalog có nhiều điểm tham quan; điểm đến ít sản phẩm sẽ fail oan.",
        "minActivities: 3"),
    "hasStay": FieldHelp(
        "Có chỗ ở (hasStay)", "Lịch trình có (true) hoặc không có (false) chỗ ở.",
        "Khi người dùng nói rõ cần hoặc không cần khách sạn (\"đi trong ngày\", \"đã có chỗ ở\").",
        "hasStay: false"),
    "warningsExclude": FieldHelp(
        "Warning không được có (warningsExclude)", "Các `warnings[].code` đã chọn không được xuất hiện.",
        "Khi lỗi gốc là agent phát warning sai, ví dụ loại nhầm sản phẩm. Gõ được mã không có trong danh sách.",
        "warningsExclude: [PRODUCT_DROPPED_EXCLUDED]"),
    "toolsInclude": FieldHelp(
        "Tool phải có trong plan (toolsInclude)",
        "Các tool đã chọn phải có trong `tool_plan` cuối của lượt (lời gọi bị server bỏ không tính).",
        "Khi lượt bắt buộc dùng một tool cụ thể, ví dụ \"đổi khách sạn khác\" phải gọi get_similar_products.",
        "toolsInclude: [get_similar_products]"),
    "titleFirstLine": FieldHelp(
        "Dòng đầu là tiêu đề (titleFirstLine)",
        "true: dòng đầu câu trả lời là `**Tiêu đề**` và còn phần chi tiết; false: không có tiêu đề.",
        "false cho chào hỏi, cảm ơn; true cho câu hỏi lại/giải thích. Không dùng khi nhánh trả lời do LLM quyết.",
        "titleFirstLine: true"),
    "formMatchesAnswer": FieldHelp(
        "Form khớp lời gợi ý (formMatchesAnswer)",
        "Response có `clarificationForm`; nếu câu trả lời nêu tên một điểm đến gợi ý thì form phải điền sẵn đúng "
        "điểm đến đó.",
        "Lượt agent phải hiện form (người dùng trả lời \"không biết\" lần thứ hai).",
        "formMatchesAnswer: true"),
    "judge": FieldHelp(
        "Tiêu chí cho LLM giám khảo (judge)",
        "Một LLM đọc hội thoại + câu trả lời và chấm từng tiêu chí; tiêu chí không đạt thành finding [judge].",
        "Chỉ cho điều khó viết thành luật (lời giải thích, câu thông báo, giọng văn). Điều kiểm được bằng khoá khác "
        "thì dùng khoá đó. Mỗi dòng một tiêu chí, viết như câu khẳng định; tiêu chí bắt đầu bằng \"Nếu\" chỉ áp "
        "dụng khi điều kiện đúng.",
        "judge: [\"Trợ lý hỏi người dùng muốn đổi sang ngày nào; không tự chọn ngày mới.\"]"),
}

# Thứ tự và nhóm hiện trên form.
EXPECT_GROUPS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Kết quả", ("httpStatus", "status", "errorCode")),
    ("Ý định", ("intent",)),
    ("Hỏi lại", ("missingFieldsInclude", "formMatchesAnswer")),
    ("Tool & node", ("toolCalled", "toolsInclude", "nodesInclude", "nodesExclude")),
    ("Lịch trình", ("hasStay", "minActivities", "excludeProductsFromTurn", "warningsExclude")),
    ("Câu trả lời", ("forbiddenText", "titleFirstLine", "judge")),
)


@dataclass(frozen=True)
class IntentField:
    path: str
    label: str
    kind: str                      # "text" | "int" | "date" | "enum"
    help: str
    options: tuple[str, ...] = ()


def intent_fields() -> tuple[IntentField, ...]:
    return (
        IntentField("destination", "Điểm đến", "text", "Tên đúng như catalog (danh sách lấy từ /destinations)."),
        IntentField("days", "Số ngày", "int", "1–7 theo contract."),
        IntentField("startDate", "Ngày đi", "date", "Dùng placeholder dạng :iso, ví dụ {today+7:iso}."),
        IntentField("party.adults", "Số người lớn", "int", "Chỉ khoá khi câu nói rõ số người."),
        IntentField("party.children", "Số trẻ em", "int", "Chỉ khoá khi câu nói rõ."),
        IntentField("party.type", "Kiểu nhóm", "enum", "Agent cố ý không đoán từ \"gia đình\"; ít khi cần khoá.",
                    _schema_enum("PartyType")),
        IntentField("budget", "Ngân sách (VND)", "int", "Tổng ngân sách VND, ví dụ 1 triệu = 1000000."),
        IntentField("pace", "Nhịp độ", "enum", "RELAXED / BALANCED / PACKED.", _schema_enum("Pace")),
    )


def _schema_enum(name: str) -> tuple[str, ...]:
    from src.backend.app.application.itinerary.contracts import schema
    return tuple(schema(name)["enum"])


@lru_cache(maxsize=1)
def error_codes() -> tuple[str, ...]:
    from src.backend.app.application.itinerary.contracts import enum_values
    return enum_values("ErrorResponse", "error", "code")


@lru_cache(maxsize=1)
def missing_field_values() -> tuple[str, ...]:
    from src.backend.app.application.itinerary.contracts import schema
    return tuple(schema("ItineraryNeedsClarification")["properties"]["missingFields"]["items"]["enum"])


@lru_cache(maxsize=1)
def node_names() -> tuple[str, ...]:
    """Tên node lấy từ chính graph (không cần LLM hay tool để dựng topology)."""
    from src.backend.app.agents.graph import build_graph
    return tuple(name for name in build_graph().get_graph().nodes if not name.startswith("__"))


@lru_cache(maxsize=1)
def tool_names() -> tuple[str, ...]:
    from src.backend.app.application.itinerary.tool_contracts import OPERATIONS
    return tuple(OPERATIONS)


def fr_codes(path: Path = REQUIREMENTS_PATH) -> list[str]:
    """Mã FR/NFR có trong requirements.md, theo thứ tự xuất hiện."""
    found = re.findall(r"\b((?:FR|NFR)-[A-Z]+-\d+)\b", path.read_text(encoding="utf-8"))
    return list(dict.fromkeys(found))


def next_case_id(ids: list[str]) -> str:
    numbers = [int(m.group(1)) for m in map(CASE_ID_PATTERN.match, ids) if m]
    return f"TC-{(max(numbers, default=0) + 1):02d}"


def id_used_in_history(case_id: str, path: Path = DATASET_PATH) -> bool:
    """Id từng có trong lịch sử git của dataset (case đã xoá); dùng lại sẽ lẫn với biên bản và trace cũ."""
    try:
        out = subprocess.run(["git", "log", "--oneline", "-S", f"id: {case_id}\n", "--", str(path)],
                             capture_output=True, text=True, cwd=REPO_ROOT, timeout=10).stdout
    except Exception:
        return False
    return bool(out.strip())


# ------------------------------------------------------------------------------------------- YAML


def _flow(value: Any) -> str:
    """Một giá trị YAML trên một dòng (list/map dạng flow), có nháy khi cần — giống phong cách file dataset."""
    text = yaml.safe_dump(value, allow_unicode=True, default_flow_style=True, sort_keys=False, width=1_000_000)
    return text.removesuffix("\n").removesuffix("\n...").strip()


def _scalar(value: Any) -> str:
    return _flow([value])[1:-1]


def case_to_yaml(case: dict[str, Any], comment: str = "") -> str:
    """Khối YAML của một case, thụt lề và kiểu flow như các case viết tay trong dataset."""
    lines = [f"# {line}" if line else "#" for para in comment.strip().splitlines()
             for line in (textwrap.wrap(para, 116) or [""])] if comment.strip() else []
    lines += [f"- id: {_scalar(case['id'])}",
              f"  category: {_scalar(case['category'])}",
              f"  fr: {_flow(list(case.get('fr') or []))}",
              "  turns:"]
    for turn in case["turns"]:
        lines.append(f"    - message: {_scalar(turn['message'])}")
        for key in ("language", "conversationId"):
            if turn.get(key):
                lines.append(f"      {key}: {_scalar(turn[key])}")
        expect = turn.get("expect") or {}
        if not expect:
            lines.append("      expect: {}")
            continue
        lines.append("      expect:")
        for key, value in expect.items():
            if key in ("judge", "forbiddenText") and isinstance(value, list) and value:
                lines.append(f"        {key}:")
                lines += [f"          - {_scalar(item)}" for item in value]
            else:
                lines.append(f"        {key}: {_flow(value) if isinstance(value, (list, dict)) else _scalar(value)}")
    return "\n".join(lines) + "\n"


def dataset_raw_case(case_id: str, path: Path = DATASET_PATH) -> dict[str, Any]:
    """Case dạng dict như trong file (chưa thay placeholder), dùng làm mẫu cho case mới."""
    return next(item for item in yaml.safe_load(path.read_text(encoding="utf-8")) if item["id"] == case_id)


def parse_case_block(text: str) -> dict[str, Any]:
    raw = yaml.safe_load(text)
    if not isinstance(raw, list) or len(raw) != 1 or not isinstance(raw[0], dict):
        raise ValueError("YAML phải là đúng một case dạng danh sách: bắt đầu bằng `- id: ...`")
    return raw[0]


# --------------------------------------------------------------------------------------- validate


def validate_block(text: str, dataset_path: Path = DATASET_PATH, today: date | None = None,
                   destinations: list[str] | None = None) -> tuple[list[str], list[str]]:
    """(lỗi, cảnh báo) khi nối `text` vào dataset. Lỗi chặn việc lưu; cảnh báo chỉ để người viết xem lại.

    Ghép vào bản sao dataset rồi chạy đúng `load_dataset` của runner (bắt khoá lạ, id trùng) cộng các kiểm của
    `test_golden.py` (mã FR, status, errorCode, placeholder ngày).
    """
    errors: list[str] = []
    warnings: list[str] = []
    try:
        raw = parse_case_block(text)
    except (yaml.YAMLError, ValueError) as exc:
        return [f"YAML không hợp lệ: {exc}"], warnings
    for key in ("id", "category", "turns"):
        if not raw.get(key):
            errors.append(f"thiếu `{key}`")
    if errors:
        return errors, warnings

    combined = dataset_path.read_text(encoding="utf-8").rstrip("\n") + "\n\n" + text
    with tempfile.TemporaryDirectory() as tmp:
        candidate = Path(tmp) / "dataset.yaml"
        candidate.write_text(combined, encoding="utf-8")
        try:
            cases = load_dataset(candidate)
        except (ValueError, KeyError, TypeError, yaml.YAMLError) as exc:
            return [str(exc)], warnings
    case: Case = next(c for c in cases if c.id == raw["id"])

    if not CASE_ID_PATTERN.match(case.id):
        warnings.append(f"id {case.id!r} không theo dạng TC-NN")
    elif id_used_in_history(case.id, dataset_path):
        warnings.append(f"{case.id} từng có trong lịch sử git của dataset (case đã xoá); nên chọn id mới")
    if not case.fr:
        errors.append("chưa chọn mã FR/NFR")
    for code in case.fr:
        if not FR_PATTERN.match(code):
            errors.append(f"mã {code!r} sai định dạng FR-XXX-NN / NFR-XXX-NN")
    allowed_errors = set(error_codes())
    known = set(destinations or [])
    for index, turn in enumerate(case.turns, start=1):
        where = f"lượt {index}"
        if not str(turn.message).strip():
            errors.append(f"{where}: câu nhập trống")
        for value in turn.expect.get("status", []):
            if value not in STATUSES:
                errors.append(f"{where}: status {value!r} không có trong contract")
        if "errorCode" in turn.expect and turn.expect["errorCode"] not in allowed_errors:
            errors.append(f"{where}: errorCode {turn.expect['errorCode']!r} không có trong contract")
        spec = turn.expect.get("excludeProductsFromTurn")
        if spec and not (isinstance(spec.get("turn"), int) and 1 <= spec["turn"] < index):
            errors.append(f"{where}: excludeProductsFromTurn.turn phải là một lượt trước lượt này")
        for value in (turn.message, turn.expect):
            if "{today" in str(resolve_dates(value, today or date.today())):
                errors.append(f"{where}: placeholder ngày viết sai (dạng đúng: {{today+7}}, {{today+7:iso}})")
        destination = (turn.expect.get("intent") or {}).get("destination")
        if known and destination and destination not in known:
            warnings.append(f"{where}: điểm đến {destination!r} không có trong danh sách catalog")
        if not turn.expect:
            warnings.append(f"{where}: chưa có kỳ vọng nào — lượt chỉ được kiểm bằng các gate chung")
    return errors, warnings


def append_case(text: str, dataset_path: Path = DATASET_PATH) -> None:
    """Nối khối case vào cuối file; không ghi lại phần cũ nên comment lỗi gốc của các case khác giữ nguyên."""
    current = dataset_path.read_text(encoding="utf-8")
    prefix = "" if not current else ("\n" if current.endswith("\n") else "\n\n")
    with dataset_path.open("a", encoding="utf-8") as handle:
        handle.write(prefix + text.rstrip("\n") + "\n")
