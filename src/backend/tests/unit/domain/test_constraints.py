"""Parser ràng buộc cứng Phase A (`domain/search/constraints.py`): giá/sao, phủ định tiện ích, ngành dọc, vai trò bay —
bảng câu gold + biến thể không dấu; thuần, không catalog."""
import pytest

from src.backend.app.domain.search.constraints import (VERTICAL_CUE_STRENGTH, VERTICAL_CUES, WEAK_VERTICAL_CUES,
                                                       DurationParse, FlightRoles, MustNot, NegationParse,
                                                       NumericParse, VerticalParse, parse_duration,
                                                       parse_flight_roles, parse_negation, parse_numeric,
                                                       parse_party, parse_vertical, remove_spans)
from src.backend.app.domain.search.lexical import fold
from src.backend.app.domain.search.normalize import QueryNormalizer

DESTINATIONS = ["Nha Trang", "Phú Quốc", "Đà Nẵng", "TP. Hồ Chí Minh", "Huế", "Hà Nội", "Buôn Ma Thuột", "Hạ Long",
                "Côn Đảo", "Quy Nhơn", "Hà Tĩnh", "Điện Biên"]
IATA = {"HAN": "Hà Nội", "SGN": "TP. Hồ Chí Minh", "DAD": "Đà Nẵng", "PQC": "Phú Quốc", "CXR": "Nha Trang"}


@pytest.fixture(scope="module")
def norm():
    return QueryNormalizer(DESTINATIONS, [])


def consumed(text: str, spans) -> list[str]:
    return [text[s:e] for s, e in spans]


# ------------------------------------------------------------------------------------------------ F6: giá / sao
@pytest.mark.parametrize("q, star, pmin, pmax", [
    ("khách sạn 5 sao ở Hà Tĩnh dưới 2 triệu", 5, None, 2_000_000),
    ("chỗ nghỉ Quy Nhơn từ 4 sao, giá không quá 1 triệu, còn lựa chọn nào?", 4, None, 1_000_000),
    ("KS 4 sao tại Hạ Long, ngân sách tối đa 1.5 triệu", 4, None, 1_500_000),
    ("tìm KS 3 sao tại Điện Biên, ngân sách tối đa 500 nghìn", 3, None, 500_000),
    ("KS 5 sao tại Hạ Long, ngân sách tối đa 9.5 triệu", 5, None, 9_500_000),
    ("khách sạn 3 sao ở Nha Trang dưới 500 nghìn", 3, None, 500_000),
    ("ks 4 sao duoi 2 trieu", 4, None, 2_000_000),                       # không dấu
    ("khách sạn 4.5 sao trở lên", 4.5, None, None),
    ("ít nhất 3 sao, tầm 800k", 3, None, 800_000),
    ("resort từ 1 đến 2 triệu", None, 1_000_000, 2_000_000),
    ("resort 1-2 triệu", None, 1_000_000, 2_000_000),
    ("từ 1 triệu đến 2 triệu", None, 1_000_000, 2_000_000),
    ("trên 3 triệu", None, 3_000_000, None),
    ("2tr trở xuống", None, None, 2_000_000),                            # chữ dính, chưa qua chuẩn hoá
    ("khách sạn <= 500.000", None, None, 500_000),                       # ký hiệu + phân cách nghìn
    ("khách sạn >= 1.500.000", None, 1_500_000, None),
    ("combo vui chơi Phú Quốc dưới 2 triệu", None, None, 2_000_000),
    ("khách sạn không dưới 4 sao", 4, None, None),
    ("giá rẻ", None, None, None),
    ("phòng cho 2 người 3 đêm", None, None, None),                       # số không phải tiền/sao
])
def test_parse_numeric_values(q, star, pmin, pmax):
    r = parse_numeric(q)
    assert (r.star_min, r.price_min, r.price_max) == (star, pmin, pmax)
    assert r.dropped == () and (r.unresolved == () or (star, pmin, pmax) == (None, None, None))


def test_parse_numeric_consumes_operator_number_unit():
    q = "khách sạn 5 sao ở Hà Tĩnh dưới 2 triệu"
    r = parse_numeric(q)
    assert consumed(q, r.spans) == ["5 sao", "dưới 2 triệu"]
    assert remove_spans(q, r.spans) == "khách sạn ở Hà Tĩnh"
    q = "chỗ nghỉ Quy Nhơn từ 4 sao, giá không quá 1 triệu, còn lựa chọn nào?"
    assert consumed(q, parse_numeric(q).spans) == ["từ 4 sao", "giá không quá 1 triệu"]
    q = "KS 4 sao tại Hạ Long, ngân sách tối đa 1.5 triệu"
    assert consumed(q, parse_numeric(q).spans) == ["4 sao", "ngân sách tối đa 1.5 triệu"]


@pytest.mark.parametrize("q, dropped, unresolved", [
    ("không nhất thiết 5 sao", ("không nhất thiết 5 sao",), ()),
    ("resort không cần 4 sao", ("không cần 4 sao",), ()),
    ("khách sạn 2 triệu", (), ("2 triệu",)),                 # không toán tử → không lọc
    ("khách sạn 2 triệu đồng", (), ("2 triệu đồng",)),       # đuôi tiền tệ nằm trong span unresolved
    ("dưới 4 sao", (), ("dưới 4 sao",)),
])
def test_parse_numeric_dropped_and_unresolved(q, dropped, unresolved):
    r = parse_numeric(q)
    assert r == NumericParse(None, None, None, r.spans, dropped, unresolved)
    assert consumed(q, r.spans) == list(dropped + unresolved)


@pytest.mark.parametrize("q", [
    "khách sạn cách biển dưới 500 m",      # "m" tách rời = mét, không phải triệu
    "cách biển không quá 500 m",
    "khoảng 300 m từ biển",
    "resort cách sân bay dưới 10 km",
])
def test_parse_numeric_spaced_metre_is_distance_not_money(q):
    assert parse_numeric(q) == NumericParse()


def test_parse_numeric_attached_m_suffix_is_million():
    # "2m" dính liền vẫn là 2 triệu (viết tắt phổ biến); chỉ "m" đứng tách mới là mét
    r = parse_numeric("phòng dưới 2m")
    assert (r.price_min, r.price_max) == (None, 2_000_000) and consumed("phòng dưới 2m", r.spans) == ["dưới 2m"]
    assert parse_numeric("dưới 2 triệu").price_max == 2_000_000


@pytest.mark.parametrize("q, pmin, pmax, span", [
    ("dưới 2 triệu đồng", None, 2_000_000, "dưới 2 triệu đồng"),
    ("khoảng 2 triệu/đêm", None, 2_000_000, "khoảng 2 triệu/đêm"),
    ("2 triệu đồng trở xuống", None, 2_000_000, "2 triệu đồng trở xuống"),
    ("tầm 1.5 triệu một đêm", None, 1_500_000, "tầm 1.5 triệu một đêm"),
    ("từ 1 triệu đồng đến 2 triệu đồng", 1_000_000, 2_000_000, "từ 1 triệu đồng đến 2 triệu đồng"),
    ("khách sạn 500.000 VND trở lên", 500_000, None, "500.000 VND trở lên"),
])
def test_parse_numeric_absorbs_currency_and_per_night_tail(q, pmin, pmax, span):
    r = parse_numeric(q)
    assert (r.price_min, r.price_max, r.unresolved) == (pmin, pmax, ())
    assert consumed(q, r.spans) == [span]
    assert remove_spans(q, r.spans) in ("", "khách sạn")


# ------------------------------------------------------------------------------------------------ F3: phủ định
@pytest.mark.parametrize("q, keys", [
    ("khách sạn Côn Đảo không có hồ bơi view đẹp", ["pool"]),
    ("chỗ nghỉ tại TP. Hồ Chí Minh không ghi nhận bếp riêng", ["kitchen"]),
    ("Khách sạn Hạ Long không có ban công", ["balcony"]),
    ("chỗ nghỉ tại Đà Nẵng không ghi nhận nhà hàng", ["restaurant"]),
    ("khách sạn Hạ Long không ghi nhận xe đưa đón sân bay", ["shuttle"]),
    ("khach san da nang khong co ho boi", ["pool"]),                      # không dấu
    ("khong co ho boi va nha hang", ["pool", "restaurant"]),
    ("không có hồ bơi, nhà hàng nhưng có spa", ["pool", "restaurant"]),
    ("không có sẵn hồ bơi", ["pool"]),                                    # token đệm
    ("khách sạn không hồ bơi", ["pool"]),                                 # "khong" trần + tiện ích ngay sau
    ("resort không gồm bữa sáng", ["breakfast"]),
    ("resort ngoại trừ sân golf", ["golf"]),
])
def test_parse_negation_must_not(q, keys):
    r = parse_negation(q, parse_numeric(q).spans)
    assert [m.key for m in r.must_not] == keys and r.must_not_keys == frozenset(keys)
    assert r.soft_dropped == () and r.must_not_brands == ()
    for m in r.must_not:
        assert q[m.span[0]:m.span[1]] == m.phrase


def test_parse_negation_phrase_and_spans():
    q = "khách sạn Côn Đảo không có hồ bơi view đẹp"
    r = parse_negation(q)
    assert r.must_not == (MustNot("pool", "hồ bơi", (27, 33)),)
    assert consumed(q, r.spans) == ["không có hồ bơi"]
    assert remove_spans(q, r.spans) == "khách sạn Côn Đảo view đẹp"


@pytest.mark.parametrize("q", [
    "không nhất thiết 5 sao",         # parse_numeric đã tiêu (dropped)
    "không quá 2 triệu",
    "khách sạn không dưới 4 sao",
    "Vinpearl Resort Nha Trang",
    "khách sạn không xa trung tâm",
    "không gian rộng",                 # "khong" trần không theo tiện ích
    "nơi lưu trú Đà Lạt",              # "tru" trong "lưu trú"
])
def test_parse_negation_traps_do_not_fire(q):
    r = parse_negation(q, parse_numeric(q).spans)
    assert r == NegationParse()


def test_parse_negation_without_protected_still_ignores_numbers():
    assert parse_negation("không nhất thiết 5 sao") == NegationParse()
    assert parse_negation("không quá 2 triệu") == NegationParse()


@pytest.mark.parametrize("q", [
    "nơi lưu trú gần biển",            # "trú" fold ra "tru" nhưng không phải "trừ"
    "chỗ lưu trú view biển",
    "cư trú gần biển",
    "lưu trú hồ bơi",
    "noi luu tru gan bien",            # không dấu: "tru" sau "luu" không phải "trừ"
    "cu tru gan bien",
    "khống chế hồ bơi",                # "khống" không phải "không"
])
def test_parse_negation_bare_cue_checks_raw_token(q):
    assert parse_negation(q) == NegationParse()


@pytest.mark.parametrize("q, keys, brands, span", [
    ("resort trừ Vinpearl", [], ("Vinpearl",), "trừ Vinpearl"),
    ("khách sạn trừ hồ bơi", ["pool"], (), "trừ hồ bơi"),
    ("khach san tru ho boi", ["pool"], (), "tru ho boi"),       # không dấu, không đứng sau "luu"/"cu"
])
def test_parse_negation_bare_tru_still_fires(q, keys, brands, span):
    r = parse_negation(q)
    assert [m.key for m in r.must_not] == keys and r.must_not_brands == brands and consumed(q, r.spans) == [span]


@pytest.mark.parametrize("q, soft", [
    ("không nhất thiết phải có hồ bơi", "không nhất thiết phải có hồ bơi"),     # cue 4 token + "có" dẫn đầu
    ("khách sạn không bắt buộc phải có hồ bơi", "không bắt buộc phải có hồ bơi"),
    ("khách sạn không nhất thiết có hồ bơi gần biển", "không nhất thiết có hồ bơi"),
    ("không cần phải gần biển", "không cần phải gần biển"),
])
def test_parse_negation_soft_cue_steps_over_leading_co(q, soft):
    r = parse_negation(q)
    assert r == NegationParse(soft_dropped=(soft,), spans=r.spans) and consumed(q, r.spans) == [soft]
    assert "có hồ bơi" not in remove_spans(q, r.spans)


@pytest.mark.parametrize("q, soft", [
    ("resort không cần gần biển", "không cần gần biển"),
    ("khách sạn không bắt buộc hồ bơi", "không bắt buộc hồ bơi"),
    ("không cần đẹp ở Nha Trang", "không cần đẹp"),              # dừng trước "ở"
])
def test_parse_negation_soft_cues_drop_condition_only(q, soft):
    r = parse_negation(q)
    assert r.must_not == () and r.soft_dropped == (soft,) and consumed(q, r.spans) == [soft]


def test_parse_negation_unresolved_never_invents_key():
    r = parse_negation("khách sạn không có view đẹp")
    assert r.must_not == () and r.unresolved == ("view đẹp",)
    r = parse_negation("không có gì đặc biệt, có hồ bơi")
    assert r.must_not == () and r.unresolved == ("gì đặc biệt",)


def test_parse_negation_brand():
    q = "resort Nha Trang không phải Vinpearl"
    r = parse_negation(q)
    assert r.must_not == () and r.must_not_brands == ("Vinpearl",) and consumed(q, r.spans) == ["không phải Vinpearl"]


# ------------------------------------------------------------------------------------------------ F3: phủ định loại sản phẩm
@pytest.mark.parametrize("q, taxonomies, flags, taxonomy", [
    ("vé lẻ VinWonders Nam Hội An, không lấy combo", ("combo",), (), "attraction"),     # gold c0703 (rubric v4 #10)
    ("ve le vinwonders khong lay combo", ("combo",), (), "attraction"),                # không dấu
    ("vé lẻ VinWonders Nha Trang", ("combo",), (), "attraction"),                       # "vé lẻ" dương = loại combo
    ("vé VinWonders không muốn combo", ("combo",), (), "attraction"),
    ("khách sạn không phải combo", ("combo",), (), "hotel"),
    ("resort Phú Quốc không lấy vé máy bay", ("flight",), (), "hotel"),                # không có combo → loại cả loại
    ("không lấy vé tham quan, chỉ cần khách sạn Huế", ("attraction",), (), "hotel"),
    ("combo Phú Quốc không gồm vé máy bay", (), ("includesFlight",), "combo"),         # kiến trúc §4: includes_flight=false
    ("combo Đà Nẵng không kèm khách sạn", (), ("includesHotel",), "combo"),
    ("combo Phú Quốc không bao gồm vé máy bay và khách sạn", (), ("includesFlight", "includesHotel"), "combo"),
])
def test_parse_negation_taxonomy_and_composition(q, taxonomies, flags, taxonomy):
    r = parse_negation(q, parse_numeric(q).spans)
    assert (r.must_not_taxonomies, r.must_not_flags) == (taxonomies, flags)
    assert r.must_not == () and r.must_not_brands == () and r.unresolved == ()
    assert parse_vertical(q, excluded=r.spans).taxonomy == taxonomy     # cue trong scope phủ định không tính là loại dương


def test_parse_negation_taxonomy_scope_is_consumed_but_single_ticket_phrase_is_not():
    q = "vé lẻ VinWonders Nam Hội An, không lấy combo"
    r = parse_negation(q)
    assert consumed(q, r.spans) == ["không lấy combo"]
    assert remove_spans(q, r.spans) == "vé lẻ VinWonders Nam Hội An"


@pytest.mark.parametrize("q, keys", [
    ("khách sạn không có hồ bơi, phòng rộng", ["pool"]),       # cue loại sau tiện ích → kết thúc phạm vi, như trước
    ("khách sạn không có phòng gym", ["gym"]),                  # tiện ích khớp trước cue "phòng"
    ("resort ngoại trừ sân golf", ["golf"]),                     # "sân golf" là tiện ích, không phải ngành golf
    ("khách sạn không muốn hồ bơi", ["pool"]),                   # cue cứng mới
    ("còn phòng không, khách sạn ở Đà Nẵng", []),               # dấu phẩy tách cue và cue loại → không phủ định
    ("về lễ hội Huế", []),                                       # "về lễ" fold cũng ra "ve le" nhưng không phải "vé lẻ"
])
def test_parse_negation_taxonomy_cues_do_not_change_amenity_scopes(q, keys):
    r = parse_negation(q)
    assert [m.key for m in r.must_not] == keys and r.must_not_taxonomies == () and r.must_not_flags == ()


# ------------------------------------------------------------------------------------------------ F4: ngành dọc
CROSS_VERTICAL = [   # câu dựng tay; "combo khách sạn và vé máy bay Phú Quốc" chuyển sang luật combo đứng đầu (rubric v4 c0706)
    "khách sạn, vé máy bay và vé tham quan ở Buôn Ma Thuột",
    "vé máy bay và khách sạn Đà Nẵng",
    "resort và sân golf Nha Trang",
    "khách sạn gần biển và vé VinWonders",
    "chuyến bay Hà Nội và khách sạn Hạ Long",
    "voucher golf và khách sạn Hội An",
    "vé tham quan và chỗ nghỉ Huế",
    "homestay và vé vào cửa Grand World",
    "trọn gói và vé máy bay Đà Lạt",            # cue combo là một mục của danh sách ("và" ngay sau) → không phải đầu combo
]
GOLD_CROSS_VERTICAL = [   # đủ 10 câu slice cross_vertical của gold (src/evaluation/search_bench/gold/drafts.txt)
    "khách sạn, vé máy bay và vé tham quan ở Buôn Ma Thuột",
    "mình cần khách sạn, vé máy bay, vé tham quan và combo du lịch ở Cần Thơ",
    "khách sạn, vé máy bay, vé tham quan và combo du lịch ở Huế",
    "tìm khách sạn, vé máy bay, vé tham quan và combo du lịch ở Hà Nội",
    "mình cần khách sạn, vé tham quan và combo du lịch ở Hà Tĩnh",
    "khách sạn, vé tham quan và combo du lịch ở Hạ Long",
    "tìm khách sạn, vé máy bay, vé tham quan, sân golf và combo du lịch ở Hải Phòng",
    "mình cần khách sạn, vé tham quan, sân golf và combo du lịch ở Hội An",
    "khách sạn, vé máy bay, vé tham quan và combo du lịch ở Nghệ An",
    "tìm khách sạn, vé máy bay, vé tham quan, sân golf và combo du lịch ở Nha Trang",
]


@pytest.mark.parametrize("q", CROSS_VERTICAL + GOLD_CROSS_VERTICAL)
def test_parse_vertical_multi(q):
    r = parse_vertical(q)
    assert r.taxonomy is None and r.skipped == "multi" and len(r.verticals) >= 2 and r.strength is None


@pytest.mark.parametrize("q, taxonomy, skipped", [
    ("combo vé máy bay và khách sạn Đà Lạt", "combo", None),       # gold c0706: thành phần của combo, không phải multi
    ("combo khách sạn và vé máy bay Phú Quốc", "combo", None),
    ("combo gồm vé máy bay và khách sạn", "combo", None),
    ("trọn gói khách sạn và vé VinWonders Nha Trang", "combo", None),
    ("trọn gói và vé máy bay Đà Lạt", None, "multi"),             # combo đứng thành một mục của danh sách
    ("combo, khách sạn Huế", None, "multi"),
    ("combo golf và khách sạn", None, "multi"),                    # golf không phải thành phần combo
    ("khách sạn và combo Phú Quốc", None, "multi"),                 # combo không đứng đầu
])
def test_parse_vertical_combo_head_takes_components(q, taxonomy, skipped):
    r = parse_vertical(q)
    assert (r.taxonomy, r.skipped) == (taxonomy, skipped) and len(r.verticals) >= 2
    if taxonomy:   # chỉ cue combo bị cắt khỏi BM25 — thành phần ("vé máy bay", "khách sạn") vẫn xếp hạng tên combo
        assert [VERTICAL_CUES[fold(q[s:e])] for s, e in r.spans] == ["combo"] * len(r.spans)


def test_vertical_cue_strength_table_covers_every_cue():
    assert set(VERTICAL_CUE_STRENGTH) == set(VERTICAL_CUES) and set(VERTICAL_CUE_STRENGTH.values()) == {"strong", "weak"}
    assert WEAK_VERTICAL_CUES <= set(VERTICAL_CUES)
    assert {c for c, s in VERTICAL_CUE_STRENGTH.items() if s == "weak"} == WEAK_VERTICAL_CUES


@pytest.mark.parametrize("q, taxonomy, strength", [
    ("resort Phú Quốc", "hotel", "strong"),
    ("khu nghỉ dưỡng Phú Quốc", "hotel", "strong"),                # danh từ chỗ nghỉ: mạnh từ 06/10 (dev/test 100 %)
    ("nơi ở Pleiku cho nhóm 4 người", "hotel", "strong"),
    ("nghỉ dưỡng Phú Quốc", "hotel", "weak"),
    ("VinWonders Nha Trang", "attraction", "weak"),               # tên điểm vui chơi: yếu (combo chứa vé được nhãn 2)
    ("vé vui chơi VinWonders Nha Trang", "attraction", "strong"),
    ("phòng cho 2 người", "hotel", "weak"),
    ("resort nghỉ dưỡng Phú Quốc", "hotel", "strong"),             # có một cue mạnh là đủ
    ("điểm tham quan Huế", "attraction", "strong"),
    ("tham quan Huế", "attraction", "weak"),
    ("gói du lịch Đà Nẵng", "combo", "weak"),
    ("combo vé máy bay và khách sạn Đà Lạt", "combo", "strong"),
    ("đi chơi Đà Lạt", None, None),
])
def test_parse_vertical_strength(q, taxonomy, strength):
    r = parse_vertical(q)
    assert (r.taxonomy, r.strength) == (taxonomy, strength)


@pytest.mark.parametrize("q, taxonomy", [
    ("voucher golf tại Hội An", "golf"),
    ("sân golf ở Nha Trang", "golf"),
    ("tìm vé VinWonders Nha Trang", "attraction"),
    ("vé vào cửa Grand World", "attraction"),
    ("resort có sân golf", "hotel"),                 # tiện ích kèm, không phải ngành dọc
    ("khách sạn gần VinWonders", "hotel"),
    ("khu du lịch nghỉ dưỡng Nha Trang", "hotel"),
    ("khach san da nang khong co ho boi", "hotel"),
    ("chuyến bay Hà Nội", "flight"),
    ("ve may bay TP. Hồ Chí Minh di Đà Nẵng", "flight"),
    ("combo vui chơi Phú Quốc", "combo"),
    ("phòng cho 2 người", "hotel"),
    ("vé Hà Nội", None),                            # "ve" trần không là cue
    ("đi chơi Đà Lạt", None),
])
def test_parse_vertical_single(q, taxonomy):
    r = parse_vertical(q)
    assert (r.taxonomy, r.skipped) == (taxonomy, None)
    assert all(fold(q[s:e]) in VERTICAL_CUES for s, e in r.spans)


@pytest.mark.parametrize("q, taxonomy, skipped", [
    ("khách sạn Grand World Phú Quốc", "hotel", None),      # tên điểm vui chơi sau cue chỗ nghỉ = định vị
    ("khách sạn VinWonders Nha Trang", "hotel", None),
    ("resort Safari Phú Quốc", "hotel", None),
    ("tìm vé VinWonders Nha Trang", "attraction", None),
    ("khách sạn gần biển và vé VinWonders", None, "multi"),  # có "vé" → ngành dọc thứ hai thật
    ("khách sạn, Safari Phú Quốc", None, "multi"),          # dấu phẩy tách hai ý
    ("khách sạn, vé máy bay và vé tham quan ở Buôn Ma Thuột", None, "multi"),
])
def test_parse_vertical_poi_brand_after_hotel_is_location_modifier(q, taxonomy, skipped):
    r = parse_vertical(q)
    assert (r.taxonomy, r.skipped) == (taxonomy, skipped)
    if taxonomy == "hotel":
        assert len(r.spans) == 1 and fold(q[r.spans[0][0]:r.spans[0][1]]) in ("khach san", "resort")


def test_parse_vertical_excluded_and_brands():
    q = "resort Nha Trang không có sân golf"
    neg = parse_negation(q)
    assert parse_vertical(q, excluded=neg.spans) == VerticalParse(("hotel",), "hotel", None, ((0, 6),), "strong")
    assert parse_vertical("golf valley hotel Đà Lạt", brand_names=["Golf Valley Hotel"]).taxonomy is None
    assert parse_vertical("khách sạn Golf Valley Hotel", brand_names=["Golf Valley Hotel"]).taxonomy == "hotel"
    assert parse_vertical("Vinpearl Golf Nha Trang").taxonomy == "golf"


# ------------------------------------------------------------------------------------------------ F5: vai trò bay
@pytest.mark.parametrize("q, origin, dest, direction", [
    ("Vé máy bay Buôn Ma Thuột - Hà Nội", "Buôn Ma Thuột", "Hà Nội", "explicit"),
    ("ve may bay SG di DN", "TP. Hồ Chí Minh", "Đà Nẵng", "explicit"),
    ("vé máy bay từ Hà Nội vào Đà Nẵng", "Hà Nội", "Đà Nẵng", "explicit"),
    ("ve may bay tu ha noi vao da nang", "Hà Nội", "Đà Nẵng", "explicit"),
    ("vé máy bay Hà Nội → Đà Nẵng", "Hà Nội", "Đà Nẵng", "explicit"),
    ("bay Hà Nội Đà Nẵng", "Hà Nội", "Đà Nẵng", "explicit"),
    ("HAN DAD", "Hà Nội", "Đà Nẵng", "explicit"),
    ("SGN - PQC", "TP. Hồ Chí Minh", "Phú Quốc", "explicit"),
    ("vé máy bay HAN đi Phú Quốc", "Hà Nội", "Phú Quốc", "explicit"),
    ("đến Đà Nẵng từ Hà Nội", "Hà Nội", "Đà Nẵng", "explicit"),
    ("vé máy bay đến Hà Nội", None, "Hà Nội", "destination_only"),
    ("đường bay tới Huế", None, "Huế", "destination_only"),
    ("vé về Hà Nội", None, "Hà Nội", "destination_only"),
    ("khởi hành từ Hà Nội", "Hà Nội", None, "origin_only"),
    ("vé máy bay Hà Nội", None, None, None),           # một địa danh, không toán tử → không suy
    ("vé Hà Nội", None, None, None),                    # "vé" không phải "về"
    ("khách sạn Hà Nội", None, None, None),
])
def test_parse_flight_roles(norm, q, origin, dest, direction):
    nq = norm(q)
    r = parse_flight_roles(nq.text, nq.destination_spans, IATA, q)
    assert (r.origin, r.destination, r.direction, r.skipped) == (origin, dest, direction, None)


def test_parse_flight_roles_ambiguous_and_hand_built_places():
    text = "khách sạn Hà Nội hoặc Hạ Long"
    places = [(10, 16, "Hà Nội"), (22, 29, "Hạ Long")]
    assert parse_flight_roles(text, places) == FlightRoles(skipped="ambiguous")
    text = "ve may bay tu ha noi vao da nang"
    r = parse_flight_roles(text, [(14, 20, "Hà Nội"), (25, 32, "Đà Nẵng")])
    assert (r.origin, r.destination) == ("Hà Nội", "Đà Nẵng") and consumed(text, r.spans) == ["tu ha noi vao da nang"]
    assert parse_flight_roles("gì cũng được", []) == FlightRoles()


def places_of(text: str, *names: str) -> list[tuple[int, int, str]]:
    """Span địa danh dựng tay cho câu test (không qua QueryNormalizer)."""
    return [(text.index(n), text.index(n) + len(n), n) for n in names]


@pytest.mark.parametrize("text, span", [
    ("từ Hà Nội bay đến Đà Nẵng", "từ Hà Nội bay đến Đà Nẵng"),            # 1 token đệm trước toán tử đích
    ("từ Hà Nội bay thẳng tới Đà Nẵng", "từ Hà Nội bay thẳng tới Đà Nẵng"),  # 2 token đệm
    ("từ Hà Nội khứ hồi về Đà Nẵng", "từ Hà Nội khứ hồi về Đà Nẵng"),
])
def test_parse_flight_roles_from_with_fillers_before_to_op(text, span):
    r = parse_flight_roles(text, places_of(text, "Hà Nội", "Đà Nẵng"))
    assert (r.origin, r.destination, r.direction, r.skipped) == ("Hà Nội", "Đà Nẵng", "explicit", None)
    assert consumed(text, r.spans) == [span]


def test_parse_flight_roles_from_with_too_many_fillers_stays_ambiguous():
    text = "từ Hà Nội và khách sạn đẹp đến Đà Nẵng"
    assert parse_flight_roles(text, places_of(text, "Hà Nội", "Đà Nẵng")) == FlightRoles(skipped="ambiguous")


@pytest.mark.parametrize("text, dest, span", [
    ("bay ra Hà Nội", "Hà Nội", "ra Hà Nội"),
    ("đi sang Đà Nẵng", "Đà Nẵng", "sang Đà Nẵng"),
    ("vé máy bay bay ra Hà Nội", "Hà Nội", "ra Hà Nội"),
])
def test_parse_flight_roles_ra_sang_after_move_verb(text, dest, span):
    r = parse_flight_roles(text, places_of(text, dest))
    assert (r.origin, r.destination, r.direction) == (None, dest, "destination_only") and consumed(text, r.spans) == [span]


@pytest.mark.parametrize("text", ["ra Hà Nội", "vé ra Hà Nội", "sang Đà Nẵng chơi"])
def test_parse_flight_roles_ra_sang_without_verb_do_not_fire(text):
    assert parse_flight_roles(text, places_of(text, "Hà Nội" if "Hà Nội" in text else "Đà Nẵng")) == FlightRoles()


def test_iata_codes_only_uppercase_and_only_in_raw_text():
    assert parse_flight_roles("han dad", [], IATA) == FlightRoles()            # chữ thường trùng âm tiết Việt
    assert parse_flight_roles("HAN DAD", [], IATA, raw_text="han dad") == FlightRoles()
    assert parse_flight_roles("HAN DAD", [], IATA, raw_text="HAN DAD").origin == "Hà Nội"


# ------------------------------------------------------------------------------------------------ remove_spans
def test_remove_spans_drops_exactly_consumed_phrases(norm):
    q = "khách sạn 5 sao ở Hà Tĩnh không có hồ bơi dưới 2 triệu"
    num = parse_numeric(q)
    neg = parse_negation(q, num.spans)
    assert consumed(q, num.spans) == ["5 sao", "dưới 2 triệu"] and consumed(q, neg.spans) == ["không có hồ bơi"]
    assert remove_spans(q, num.spans + neg.spans) == "khách sạn ở Hà Tĩnh"
    nq = norm("vé máy bay từ Hà Nội vào Đà Nẵng")
    fr = parse_flight_roles(nq.text, nq.destination_spans, IATA)
    assert remove_spans(nq.text, fr.spans) == "vé máy bay"
    assert remove_spans("a  b", []) == "a b" and remove_spans("x, y", [(0, 1)]) == "y"


# ------------------------------------------------------------------ 06/10: lỗi parse loại tìm qua parse_accuracy trên 154 câu
def test_cue_inside_product_name_counts_when_it_is_the_units_own_type():
    name = "Vinpearl Resort & Golf Nam Hội An"
    tax = {"vinpearl resort golf nam hoi an": "hotel"}
    r = parse_vertical(f"tìm {name}", brand_names=[name], brand_taxonomy=tax)
    assert (r.taxonomy, r.skipped) == ("hotel", None)                     # "resort" (đúng loại unit) tính, "golf" bỏ
    assert parse_vertical(f"tìm {name}", brand_names=[name]).taxonomy is None   # không có bảng loại → như cũ
    assert parse_vertical("Vinpearl Hotel Bắc Ninh").taxonomy == "hotel"


def test_existential_co_nao_keeps_the_lodging_cue():
    assert parse_vertical("Quy Nhơn có nơi lưu trú nào có ban công").taxonomy == "hotel"
    assert parse_vertical("resort có sân golf").taxonomy == "hotel"        # "có sân golf" vẫn là tiện ích gắn sau "có"


def test_diem_vui_choi_is_a_weak_attraction_cue():
    r = parse_vertical("điểm vui chơi ở Phú Quốc")
    assert (r.taxonomy, r.strength) == ("attraction", "weak")


def test_remove_spans_keeps_punctuation_after_cut():
    # Chuỗi thay thế từng là byte 0x01 thay vì `\1`: dấu câu sau đoạn cắt bị nuốt và để lại ký tự điều khiển.
    q = "khách sạn cho 2 người lớn, gần biển"
    span = (q.index("2"), q.index(","))
    assert remove_spans(q, [span]) == "khách sạn cho, gần biển"


# ------------------------------------------------------------------------------------------------ F7: thời lượng
def duration_of(q: str) -> DurationParse:
    """Như tầng gọi trong query plan: số trong span giá/sao và số khách không bao giờ là thời lượng."""
    num = parse_numeric(q)
    party = parse_party(q, num.spans)
    return parse_duration(q, (*num.spans, *party.spans))


DURATION_VALUES = [   # bảng bảo đảm plan 07/10 Bước 4b: (câu, ngày, đêm); None = không nhận
    ("VinWonders 3 ngày 2 đêm", 3, 2),
    ("VinWonders 3 ngay 2 dem", 3, 2),                                   # không dấu
    ("combo 3N2Đ Phú Quốc", 3, 2),                                       # dạng viết tắt là một token, fold "3n2d"
    ("3n2d", 3, 2),
    ("vé VinWonders Nha Trang 2 ngày", 2, None),                         # không suy nửa thiếu
    ("phòng cho 2 người 3 đêm", None, 3),                                # "2 người" thuộc party
    ("resort 2 triệu/đêm Phú Quốc", None, None),                         # "/đêm" nằm trong span giá
    ("tầm 1.5 triệu một đêm", None, None),                               # "một đêm" nằm trong span giá
    ("Gói dịch vụ VIP Tour VinWonders Phú Quốc (3 tiếng)", None, None),  # gold c0372: giờ không phải ngày
    ("qua đêm ở Sapa", None, None),
    ("ban đêm", None, None),
    ("chợ đêm Đà Lạt", None, None),
    ("khách sạn ngay trung tâm", None, None),                             # "ngay" không có số đứng trước
    ("2 ngày 1 đêm", 2, 1),
    ("2 đêm 3 ngày", 3, 2),                                              # thứ tự đảo
    ("3 ngày, 2 đêm", 3, 2),
    ("3 ngày và 2 đêm", 3, 2),
    ("3 days 2 nights", 3, 2),                                           # tiếng Anh
    ("khách sạn 3 sao 2 đêm", None, 2),                                  # "3 sao" thuộc numeric, "2 đêm" còn tự do
    ("45 ngày", None, None),                                             # ngoài 1–30
    ("0 đêm", None, None),
    ("ngày 15/10 đến 17/10", None, None),                                # đơn vị đứng TRƯỚC số = ngày tháng
    ("vé máy bay Hà Nội Đà Nẵng 3 ngày 2 đêm", 3, 2),
]


@pytest.mark.parametrize("q, days, nights", DURATION_VALUES)
def test_parse_duration_values(q, days, nights):
    r = duration_of(q)
    assert (r.days, r.nights) == (days, nights)
    assert bool(r.spans) == ((days, nights) != (None, None))          # không nhận thì không tiêu gì


@pytest.mark.parametrize("q, spans, rest", [
    ("VinWonders 3 ngày 2 đêm", ["3 ngày 2 đêm"], "VinWonders"),
    ("VinWonders 3 ngay 2 dem", ["3 ngay 2 dem"], "VinWonders"),
    ("combo 3N2Đ Phú Quốc", ["3N2Đ"], "combo Phú Quốc"),
    ("vé VinWonders Nha Trang 2 ngày", ["2 ngày"], "vé VinWonders Nha Trang"),
    ("phòng cho 2 người 3 đêm", ["3 đêm"], "phòng cho 2 người"),            # span party không bị đụng
    ("khách sạn 3 sao 2 đêm", ["2 đêm"], "khách sạn 3 sao"),
    ("vé máy bay Hà Nội Đà Nẵng 3 ngày 2 đêm", ["3 ngày 2 đêm"], "vé máy bay Hà Nội Đà Nẵng"),   # tuyến giữ nguyên
    ("2 ngày 1 đêm", ["2 ngày 1 đêm"], ""),                                 # đúng MỘT span gộp
    ("2 đêm 3 ngày", ["2 đêm 3 ngày"], ""),
    ("3 ngày, 2 đêm", ["3 ngày, 2 đêm"], ""),
    ("3 ngày - 2 đêm", ["3 ngày - 2 đêm"], ""),
    ("3 ngày/2 đêm", ["3 ngày/2 đêm"], ""),
    ("3 ngày và 2 đêm", ["3 ngày và 2 đêm"], ""),
    ("3 days 2 nights", ["3 days 2 nights"], ""),
])
def test_parse_duration_spans(q, spans, rest):
    r = duration_of(q)
    assert consumed(q, r.spans) == spans
    assert remove_spans(q, r.spans) == rest


@pytest.mark.parametrize("q", [
    "resort 2 triệu/đêm Phú Quốc",
    "tầm 1.5 triệu một đêm",
    "Gói dịch vụ VIP Tour VinWonders Phú Quốc (3 tiếng)",
    "qua đêm ở Sapa", "ban đêm", "chợ đêm Đà Lạt", "khách sạn ngay trung tâm",
    "45 ngày", "0 đêm", "ngày 15/10 đến 17/10",
])
def test_parse_duration_traps_do_not_fire(q):
    assert duration_of(q) == DurationParse()


def test_parse_duration_protected_is_what_keeps_per_night_price_out():
    # Không có `protected` thì "/đêm" của giá sẽ bị đọc thành số đêm — tầng gọi PHẢI truyền span của parse_numeric
    q = "resort 2 triệu/đêm Phú Quốc"
    assert parse_duration(q).nights is None                     # "2" đứng trước "triệu", không phải đơn vị
    q = "khách sạn 2 đêm giá 1 triệu 1 đêm"
    assert parse_duration(q, parse_numeric(q).spans) == DurationParse(None, 2, ((10, 15),))
    assert consumed(q, parse_duration(q).spans) == ["2 đêm", "1 đêm"]     # không protected: cả hai, lần đầu thắng


def test_parse_duration_first_value_wins_but_every_match_is_consumed():
    q = "3 ngày 2 đêm hoặc 4 ngày 3 đêm"
    r = duration_of(q)
    assert (r.days, r.nights) == (3, 2)
    assert consumed(q, r.spans) == ["3 ngày 2 đêm", "4 ngày 3 đêm"]     # "hoặc" không phải từ nối → hai span
    assert remove_spans(q, r.spans) == "hoặc"
