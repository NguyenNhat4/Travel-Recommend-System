"""Từ vựng tiện ích (`domain/search/amenities.py`): chuỗi catalog → khoá, cụm câu hỏi → khoá; thuần, không catalog."""
import pytest

from src.backend.app.domain.search.amenities import (AMENITIES, KEYS, MAX_CUE_TOKENS, QUERY_CUES, amenity_keys,
                                                     keys_of_string)


@pytest.mark.parametrize("raw, expected", [
    ("Sân gôn (tại chỗ nghỉ)", {"golf"}),
    ("sân golf", {"golf"}),
    ("Sân gôn nhỏ", set()),                       # mini golf không phải sân golf
    ("Sân gôn (trong vòng 3 km)", set()),         # gần, không phải của khách sạn
    ("Sài Gòn 880 m", set()),                     # POI kèm khoảng cách, "sai gon" không chứa token "gon" riêng
    ("Sân golf Đà Lạt 570 m", set()),             # POI kèm khoảng cách
    ("Hồ bơi ngoài trời", {"pool"}),
    ("Bể bơi trong nhà", {"pool"}),
    ("Hồ bơi riêng", {"pool", "privatePool"}),
    ("Quầy bar cạnh bể bơi", {"pool", "bar"}),
    ("Bơi với ống thở", set()),
    ("Nhà hàng phục vụ bữa sáng", {"restaurant", "breakfast"}),
    ("Xe đưa đón sân bay", {"shuttle"}),
    ("Phí đưa đón sân bay 350000 VND", {"shuttle"}),
    ("Chỗ đỗ xe miễn phí", {"parking"}),
    ("Spa (trung tâm chăm sóc sức khỏe)", {"spa"}),
    ("Mát xa", {"spa"}),
    ("Trung tâm thể dục", {"gym"}),
    ("Có thể lên các tầng trên bằng thang máy", {"elevator"}),
    ("Không có thang máy (thang máy)", set()),    # chuỗi tự phủ định
    ("WiFi miễn phí", {"wifi"}),
    ("Nhìn ra biển", {"seaView"}),
    ("Giáp biển", {"nearBeach"}),
    ("Bãi biển riêng", {"nearBeach", "privateBeach"}),
    ("Ban công", {"balcony"}),
    ("Sân hiên", {"terrace"}),
    ("Bồn tắm hoặc vòi sen", set()),              # tuỳ chọn, không chắc có bồn tắm
    ("Bồn tắm nước nóng", {"bathtub"}),
    ("Bếp riêng", {"kitchen"}),
    ("Bếp chung", set()),
    ("Vật dụng nhà bếp và bộ đồ ăn được vệ sinh", set()),
    ("CLB trẻ em", {"kidsClub"}),
    ("Ghế ăn dặm cho trẻ em", set()),
    ("Phòng gia đình", {"familyRoom"}),
    ("Công viên nước", {"waterPark"}),
    ("Phòng họp", {"meetingRoom"}),
    ("Máy điều hòa", set()),
])
def test_keys_of_string(raw, expected):
    assert set(keys_of_string(raw)) == expected


def test_amenity_keys_unions_property_and_room_strings_and_ignores_empty():
    keys = amenity_keys(["Hồ bơi ngoài trời", None, "", "Ban công", "Bếp riêng"])
    assert keys == frozenset({"pool", "balcony", "kitchen"})
    assert amenity_keys([]) == frozenset()


def test_vocabulary_is_consistent():
    assert len({a.key for a in AMENITIES}) == len(AMENITIES)            # khoá duy nhất
    for a in AMENITIES:
        assert a.catalog and a.query
        for ph in (*a.catalog, *a.query, *a.exclude):
            assert ph == ph.strip() and "  " not in ph and ph.lower() == ph   # đã fold
    assert set(QUERY_CUES.values()) <= KEYS
    assert QUERY_CUES["ho boi"] == "pool" and QUERY_CUES["ho boi rieng"] == "privatePool"
    assert QUERY_CUES["san gon"] == "golf" and QUERY_CUES["bep rieng"] == "kitchen"
    assert MAX_CUE_TOKENS >= 4   # "xe dua don san bay"
