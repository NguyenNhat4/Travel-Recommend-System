import unicodedata

import pytest

from src.backend.app.domain.search import QueryNormalizer

DESTINATIONS = ["Nha Trang", "Phú Quốc", "Đà Nẵng", "TP. Hồ Chí Minh", "Huế", "Hội An", "Đà Lạt", "Phan Thiết",
                "Hà Nội", "Hạ Long"]
# vinpearl DF 4, trang DF 4 (đủ ngưỡng 3); "Xyzzy" DF 1 không bao giờ là đích sửa; "Centre" là token tiếng Anh hợp lệ.
NAMES = ["Vinpearl Resort Nha Trang", "Vinpearl Luxury Nha Trang", "Vinpearl Golf Nha Trang", "Meliá Vinpearl Hue",
         "VinWonders Nha Trang", "Khách sạn Mường Thanh Đà Nẵng", "Xyzzy Homestay", "Centre Hotel Hội An",
         "Vinpearl Safari Phú Quốc", "Bãi biển Trần Phú", "Sun World Bà Nà Hills"]


@pytest.fixture(scope="module")
def norm():
    return QueryNormalizer(DESTINATIONS, NAMES)


GOLD_ABBREV_TYPO = [   # slice abbrev_typo của gold (src/evaluation/search_bench/gold/drafts.txt)
    ("KS ở PQ có hồ bơi", "khách sạn ở Phú Quốc có hồ bơi"),
    ("KDL NT cho gia đình", "khu du lịch nghỉ dưỡng Nha Trang cho gia đình"),
    ("KS trung tâm ĐN có wifi", "khách sạn trung tâm Đà Nẵng có wifi"),
    ("tìm vé VW Nha Trang", "tìm vé VinWonders Nha Trang"),
    ("resort Phu Quoc gan bien giá tốt", "resort Phú Quốc gan bien giá tốt"),
    ("khach san Nha Trnag co ban cong", "khach san Nha Trang co ban cong"),
    ("Vinpeal Resort Nha Trang", "Vinpearl Resort Nha Trang"),
    ("KS HN gần điểm vui chơi", "khách sạn Hà Nội gần điểm vui chơi"),
    ("combo vui chơi PQ dưới 2tr", "combo vui chơi Phú Quốc dưới 2 triệu"),
    ("ve may bay SG di DN", "ve may bay TP. Hồ Chí Minh di Đà Nẵng"),
    ("khach san Da Lat co bep rieng", "khach san Đà Lạt co bep rieng"),
    ("resort Hoi An cho gd co tre nho", "resort Hội An cho gia đình co tre nho"),
    ("ve Safari PQ", "ve Safari Phú Quốc"),
    ("KS HL nhin ra bien", "khách sạn Hạ Long nhin ra bien"),
    ("KDL Phan Thiet nghi duong", "khu du lịch nghỉ dưỡng Phan Thiết nghi duong"),
]


@pytest.mark.parametrize("q,expected", GOLD_ABBREV_TYPO)
def test_gold_abbrev_typo_cases(norm, q, expected):
    assert norm(q).text == expected


@pytest.mark.parametrize("q,_", GOLD_ABBREV_TYPO)
def test_idempotent(norm, q, _):
    once = norm(q)
    assert norm(once.text).text == once.text


def test_multi_token_destination_aliases_and_punctuation(norm):
    assert norm("khách sạn tp hcm").text == "khách sạn TP. Hồ Chí Minh"
    assert norm("vé máy bay Sài Gòn đi Huế").text == "vé máy bay TP. Hồ Chí Minh đi Huế"
    assert norm("KS ở PQ, có hồ bơi!").text == "khách sạn ở Phú Quốc, có hồ bơi!"   # dấu câu giữ nguyên
    assert norm("da nang").destinations == ("Đà Nẵng",)


def test_whole_token_only(norm):
    assert norm("KSAN PQC 3N2Đ").text == "KSAN PQC 3N2Đ"


def test_spelling_guards_and_records(norm):
    assert norm("cong view xyzzq").text == "cong view xyzzq"          # âm tiết Việt / ngắn / không có ứng viên
    assert norm("centre hotel").text == "centre hotel"                 # có trong từ vựng → không đụng
    r = norm("Vinpeal Resort")
    assert r.text == "Vinpearl Resort" and r.corrections == (("Vinpeal", "Vinpearl"),)
    assert QueryNormalizer(DESTINATIONS, NAMES, spelling=False)("Vinpeal Resort").text == "Vinpeal Resort"


def test_alias_to_destination_missing_from_catalog_is_dropped():
    n = QueryNormalizer(["Nha Trang"], NAMES)
    assert n("KS HL gần biển").text == "khách sạn HL gần biển"
    assert n("KS NT gần biển").text == "khách sạn Nha Trang gần biển"


def test_nfd_input_is_handled(norm):
    assert norm(unicodedata.normalize("NFD", "KS ở Đà Nẵng")).text == "khách sạn ở Đà Nẵng"


@pytest.mark.parametrize("q,expected,party", [
    ("chỗ nghỉ Đà Lạt đi cùng bạn gái", "chỗ nghỉ Đà Lạt đi cùng cặp đôi", "COUPLE"),
    ("di cung ban trai", "di cung cặp đôi", "COUPLE"),
    ("đi du lịch biển 1 mình ở Nha Trang", "đi du lịch biển một mình ở Nha Trang", "SOLO"),
    ("resort Hoi An cho gd co tre nho", "resort Hội An cho gia đình co tre nho", "FAMILY"),
    ("nơi ở Đà Lạt cho nhóm 4 người", "nơi ở Đà Lạt cho nhóm 4 người", "FRIENDS"),
    ("khách sạn Hà Nội đi cùng công ty", "khách sạn Hà Nội đi cùng công tác", "BUSINESS"),
    ("team building Hạ Long", "công tác Hạ Long", "BUSINESS"),
    ("chỗ nghỉ yên tĩnh cho cặp đôi", "chỗ nghỉ yên tĩnh cho cặp đôi", "COUPLE"),
    ("phòng cho 2 người", "phòng cho 2 người", None),
])
def test_party_phrases(norm, q, expected, party):
    r = norm(q)
    assert (r.text, r.party) == (expected, party)
    assert norm(r.text).text == r.text


def test_destination_spans_point_into_final_text(norm):
    r = norm("ve may bay SG di DN")
    assert r.text == "ve may bay TP. Hồ Chí Minh di Đà Nẵng"
    assert r.destinations == ("TP. Hồ Chí Minh", "Đà Nẵng")
    assert [name for _, _, name in r.destination_spans] == ["TP. Hồ Chí Minh", "Đà Nẵng"]
    assert all(r.text[s:e] == name for s, e, name in r.destination_spans)
    assert norm("khách sạn gần biển").destination_spans == ()
    # địa danh lặp: `destinations` không lặp, `destination_spans` giữ từng lần xuất hiện
    twice = norm("Hà Nội đi Đà Nẵng về Hà Nội")
    assert twice.destinations == ("Hà Nội", "Đà Nẵng") and len(twice.destination_spans) == 3
