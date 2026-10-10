"""Guardrail tất định: chặn chèn lệnh và tin nhắn rác ở đầu vào, chặn lộ secret/tuyên bố đặt chỗ ở đầu ra.

Không gọi LLM — regex mẫu hẹp. Lớp phân luồng bằng LLM (`classification.route_result`) đã gắn
`out_of_scope` cho chèn lệnh, đòi secret, đặt chỗ (`prompts.CLASSIFY_PROMPT`); module này là lưới an
toàn tất định phía trước và phía sau, không thay thế lớp đó. Mẫu cố ý hẹp để không chặn nhầm câu du
lịch hợp lệ (vd. "bỏ qua khách sạn"); mở rộng mẫu thì thêm test âm tính đi kèm.

`input_quality` là tầng 1 lọc rác (NFR-SEC-04, spec `docs/spec/agent/langgraph-nodes.md` mục "Guardrail tầng 1"):
rỗng/chỉ ký hiệu, một ký tự lặp, tỉ lệ chữ thấp, gõ bậy và tục tĩu thuần.
"""
from __future__ import annotations

import re
import unicodedata
from collections import Counter

# Chèn lệnh / đòi lộ thông tin hệ thống, rõ ràng không phải yêu cầu du lịch.
_QUALIFIER = r"(all\s+|any\s+|the\s+|previous\s+|prior\s+)*"
_INPUT_PATTERNS = [
    re.compile(rf"ignore\s+{_QUALIFIER}instructions?", re.IGNORECASE),
    re.compile(rf"disregard\s+{_QUALIFIER}instructions?", re.IGNORECASE),
    re.compile(rf"forget\s+{_QUALIFIER}instructions?", re.IGNORECASE),
    re.compile(r"bỏ qua\s+(mọi\s+|các\s+|những\s+|hết\s+)?(hướng dẫn|chỉ dẫn|chỉ thị)\s+(trước|trên|đã)",
              re.IGNORECASE),
    re.compile(r"quên\s+(mọi\s+|các\s+|những\s+|hết\s+)?(hướng dẫn|chỉ dẫn|chỉ thị)\s+(trước|trên|đã)",
              re.IGNORECASE),
    re.compile(r"system\s*prompt|prompt\s*hệ thống|chỉ dẫn\s*hệ thống", re.IGNORECASE),
    re.compile(r"(in ra|hiện ra|hiển thị|show|reveal|print|tiết lộ|cho\s+(tôi\s+|mình\s+)?(xem|coi))\s+.{0,30}"
              r"(api[\s_-]?key|secret\s*key|secret|token|mật khẩu)", re.IGNORECASE),
]

# Câu chữ LLM tự viết không được phép chứa: chuỗi giống secret, hoặc tuyên bố đã đặt/đã thanh toán —
# grounding và trạng thái đặt chỗ chỉ do luật tất định quyết định, LLM không được tự nói thay (NFR-SEC-01).
_SECRET_PATTERNS = [
    re.compile(r"sk-[a-zA-Z0-9]{10,}"),
    re.compile(r"bearer\s+[a-zA-Z0-9._-]{10,}", re.IGNORECASE),
    re.compile(r"AIzaSy[a-zA-Z0-9_-]{10,}"),
]
_BOOKING_CLAIM_PHRASES = ("đã đặt", "đã thanh toán", "đặt thành công", "booking confirmed")


def input_violation(query: str) -> str | None:
    """Mẫu chèn lệnh/đòi secret khớp đầu tiên trong `query`, hoặc `None` nếu câu sạch."""
    for pattern in _INPUT_PATTERNS:
        if pattern.search(query or ""):
            return pattern.pattern
    return None


def _llm_authored_text(response: dict) -> str:
    """Ba trường LLM tự viết chữ: `question` (`clarify`/`converse`), `error.message` (từ chối của `converse`) và
    `message` của `COMPLETED` (`narrate`). `message` của `NO_RESULTS`/`FALLBACK` là câu cố định, không quét.
    """
    parts = [response.get("question")]
    if response.get("status") == "COMPLETED":
        parts.append(response.get("message"))
    error = response.get("error")
    if isinstance(error, dict):
        parts.append(error.get("message"))
    return "\n".join(part for part in parts if part)


def output_violations(response: dict) -> list[str]:
    """Danh sách lý do vi phạm trong câu chữ LLM tự viết của `response`; rỗng nghĩa là sạch."""
    text = _llm_authored_text(response)
    lowered = text.lower()
    issues = [f"secret:{pattern.pattern}" for pattern in _SECRET_PATTERNS if pattern.search(text)]
    issues += [f"booking_claim:{phrase}" for phrase in _BOOKING_CLAIM_PHRASES if phrase in lowered]
    return issues


# --- Tầng 1: lọc tin nhắn rác (NFR-SEC-04) ---------------------------------------------------------------
# Luật chỉ chặn khi chắc chắn là rác: câu trả lời ngắn cho `clarify` ("2", "15/10", "ok", "5tr") phải đi qua.

UNCLEAR = "unclear"    # rác/gõ bậy → câu cố định "chưa hiểu", 200
ABUSIVE = "abusive"    # chỉ có tục tĩu → nhánh từ chối của guardrail, 400

_MIN_ALNUM_RATIO = 0.3     # chữ + số trên mọi ký tự không phải khoảng trắng
_MIN_VALID_TOKEN_RATIO = 0.5
_MIN_REPEAT_LENGTH = 4

# Âm tiết tiếng Việt = phụ âm đầu + vần, kiểm trên chữ đã bỏ dấu (nên câu không dấu cũng hợp lệ).
_ONSETS = ("ngh", "ng", "nh", "ch", "gh", "gi", "kh", "ph", "qu", "th", "tr",
           "b", "c", "d", "g", "h", "k", "l", "m", "n", "p", "r", "s", "t", "v", "x", "")
_RHYMES = (
    "a ai ao au ay ac ach am an ang anh ap at "
    "e eo ec em en eng ep et eu ech enh "
    "i ia iu ich im in inh ip it iec iem ien ieng iep iet ieu "
    "o oi oc om on ong op ot ooc oong "
    "u ua ui uc um un ung up ut uu uoc uoi uom uon uong uop uot uou "
    "y yen yet yeu yem "
    "oa oac oach oai oam oan oang oanh oao oap oat oay oe oen oeo oet oem "
    "uy uya uych uyen uyet uynh uyt uyu ue uenh uan uang uat uay uau uyp"
).split()
_SYLLABLE = re.compile(rf"^(?:{'|'.join(_ONSETS)})(?:{'|'.join(sorted(_RHYMES, key=len, reverse=True))})$|^gi$")

# Viết tắt/teencode và tên riêng không theo cấu trúc âm tiết; so trên chữ đã bỏ dấu.
_ABBREVIATIONS = frozenset(
    "ko kh khg hok hong dc ns mn mng ok oke okie oki tp hcm hn sg vn vs nma nhg ntn sao j z bn "
    "ae ace ad ac tr trieu cty kg km ks hk dl pq dn nt vt sp pleiku haha hihi hehe hic huhu kk kkk "
    "ui uhm um uk uh ah oh wow".split())
# Từ tiếng Anh thông dụng và từ du lịch — contract nhận cả `language=en`.
_ENGLISH = frozenset("""
a an the and or but if so to of in on at by for from with without about into over under near
i me my we our you your he she it they them this that these those there here what which who whom whose
when where why how is are was were be been being am do does did have has had can could will would should
may might must shall not no yes please thanks thank hello hi hey bye good great nice best cheap cheapest
want wanted need like love plan planning trip trips travel travelling traveling tour tours visit visiting
go going stay staying book booking day days night nights week weekend month morning afternoon evening
one two three four five six seven eight nine ten first next last more less some any all each every other
hotel hotels resort resorts homestay villa room rooms flight flights ticket tickets airport beach sea island
mountain city town center food restaurant spa pool golf combo package budget price prices cost family
kids kid children child adult adults people person couple friends honeymoon view wifi breakfast buffet
check checkin checkout show find search suggest recommend change replace instead also too only just
around nearby close far long short big small new old free available days
""".split())

# Tục tĩu: so trên chữ thường **giữ dấu**; bản không dấu chỉ đưa từ không trùng từ thường ("cac" trùng "các",
# "buoi" trùng "buổi", "deo" trùng "đeo" nên không có mặt).
_PROFANITY = frozenset(
    "địt đụ đéo đếch lồn buồi cặc đĩ dmm đmm đcm dcm đkm dkm đm dm vl vcl vkl vcc clgt loz ditme dume duma "
    "fuck fucking fucked shit bitch cunt dick asshole motherfucker bastard".split())
# Phần còn lại chỉ là lời gọi người nghe ("fuck you", "đm mày") vẫn là chửi thuần, không phải yêu cầu.
_ADDRESSEES = frozenset("you u ya mày mầy tao bot thằng con này".split())

_TOKEN = re.compile(r"[^\W\d_]+")
_REPEAT_RUN = re.compile(r"(.)\1{2,}")
_LAUGH = re.compile(r"^(?:ha|he|hi|ho|hu|k)+$")
_LATIN = re.compile(r"^[a-z]+$")
_CONSONANT_RUN = re.compile(r"[^aeiouy]{5,}")
_VOWEL_RUN = re.compile(r"[aeiouy]{4,}")  # "puaiegapoiga": không từ thật nào dồn ≥ 4 nguyên âm
_MAX_UNKNOWN_TOKEN_LENGTH = 14            # tên riêng/thương hiệu ngoài từ điển ngắn hơn; chuỗi gõ bậy thì dài
_KEYBOARD_ROWS = ("qwertyuiop", "asdfghjkl", "zxcvbnm")
_HOME_ROW = frozenset("asdfghjkl")


def _strip_marks(text: str) -> str:
    decomposed = unicodedata.normalize("NFD", text.replace("đ", "d").replace("Đ", "D"))
    return "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")


def _tokens(text: str) -> list[str]:
    """Token chữ, viết thường, đã gộp chuỗi lặp ≥ 3 ("đẹppppp" → "đẹp", "okkkk" → "ok")."""
    collapsed = _REPEAT_RUN.sub(r"\1", unicodedata.normalize("NFC", text.lower()))
    return _TOKEN.findall(collapsed)


def _keyboard_mash(bare: str) -> bool:
    """Gõ dọc một hàng phím ("qwerty", "lkjh") hoặc dồn hàng giữa ("ajsdhakjsd")."""
    if len(bare) >= 4 and any(bare in row or bare in row[::-1] for row in _KEYBOARD_ROWS):
        return True
    return len(bare) >= 6 and set(bare) <= _HOME_ROW


def _pronounceable(bare: str) -> bool:
    """Tên riêng, thương hiệu, từ tiếng Anh ngoài từ điển ("VinWonders", "Đray Nur"): có nguyên âm,
    không dồn ≥ 5 phụ âm liền nhau, không phải gõ dọc bàn phím."""
    return (any(ch in "aeiouy" for ch in bare) and len(bare) <= _MAX_UNKNOWN_TOKEN_LENGTH
            and not _CONSONANT_RUN.search(bare) and not _VOWEL_RUN.search(bare) and not _keyboard_mash(bare))


def _valid_token(token: str) -> bool:
    if len(token) == 1:  # "a", "ừ", và viết tắt một chữ như "n" (ngày), "đ", "k" (nghìn)
        return True
    bare = _strip_marks(token)
    if not _LATIN.match(bare):
        return True  # chữ không phải Latin (Hán, Thái...): không đủ căn cứ để gọi là gõ bậy
    if _SYLLABLE.match(bare) or bare in _ABBREVIATIONS or token in _ENGLISH or _LAUGH.match(bare):
        return True
    return _pronounceable(bare)


def _mostly_valid(tokens: list[str]) -> bool:
    return bool(tokens) and sum(map(_valid_token, tokens)) / len(tokens) >= _MIN_VALID_TOKEN_RATIO


def input_quality(query: str) -> tuple[str, str] | None:
    """(`UNCLEAR`|`ABUSIVE`, tên luật) nếu `query` là rác hiển nhiên, `None` nếu cho qua LLM.

    Tục tĩu lẫn trong một yêu cầu hợp lệ thì cho qua — chỉ chặn khi bỏ từ tục đi không còn gì có nghĩa.
    """
    text = (query or "").strip()
    if not text:
        return None
    chars = [ch for ch in text if not ch.isspace()]
    alnum = sum(ch.isalnum() for ch in chars)
    if alnum == 0:
        return UNCLEAR, "no_content"
    top_count = Counter(ch.lower() for ch in chars).most_common(1)[0][1]
    if len(chars) >= _MIN_REPEAT_LENGTH and top_count == len(chars):
        return UNCLEAR, "repeated_char"
    if alnum / len(chars) < _MIN_ALNUM_RATIO:
        return UNCLEAR, "low_alnum_ratio"
    tokens = _tokens(text)
    if not tokens:
        return None  # chỉ có số: số ngày, ngày đi, số người, ngân sách
    profane = [token for token in tokens if token in _PROFANITY or _strip_marks(token) in _PROFANITY]
    if profane:
        rest = [token for token in tokens if token not in profane and token not in _ADDRESSEES]
        return None if _mostly_valid(rest) else (ABUSIVE, "profanity")
    if not _mostly_valid(tokens):
        return UNCLEAR, "gibberish"
    return None
