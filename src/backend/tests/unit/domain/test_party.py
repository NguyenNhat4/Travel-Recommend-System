"""Số khách rút từ câu (`constraints.parse_party`; kiến trúc §6 occupancy, contract `travelContext.guests`): người lớn, trẻ em,
tổng — không lẫn số của giá / sao; thuần, không catalog."""
import pytest

from src.backend.app.domain.search.constraints import PartyParse, parse_numeric, parse_party


def consumed(text: str, spans) -> list[str]:
    return [text[s:e] for s, e in spans]


@pytest.mark.parametrize("q, adults, children, total, spans", [
    ("nơi ở Pleiku cho nhóm 4 người", None, None, 4, ["4 người"]),
    ("2 người lớn và 1 trẻ em", 2, 1, 3, ["2 người lớn và 1 trẻ em"]),
    ("gia đình 2 người lớn, 2 trẻ em ở Nha Trang", 2, 2, 4, ["2 người lớn, 2 trẻ em"]),
    ("2 nguoi lon 1 tre em", 2, 1, 3, ["2 nguoi lon 1 tre em"]),               # không dấu, không từ nối
    ("khách sạn cho gia đình 5 người", None, None, 5, ["5 người"]),
    ("đoàn 20 khách đi Hạ Long", None, None, 20, ["20 khách"]),
    ("Phòng 4 Người", None, None, 4, ["4 Người"]),                              # tên hạng phòng cũng ra tổng (chủ ý)
    ("3 người lớn", 3, None, 3, ["3 người lớn"]),
    ("resort cho 2 bé", None, 2, None, ["2 bé"]),                              # chỉ biết trẻ em → không bịa tổng
    ("1 em bé", None, 1, None, ["1 em bé"]),
    ("2 người lớn 1 trẻ nhỏ và 1 con", 2, 1, 3, ["2 người lớn 1 trẻ nhỏ và 1 con"]),   # trẻ em nêu lần đầu thắng
    ("gia đình 4 người gồm 2 người lớn 2 trẻ em", 2, 2, 4, ["4 người", "2 người lớn 2 trẻ em"]),
    ("nhóm 6 người, 2 người lớn", 2, None, 6, ["6 người, 2 người lớn"]),     # tổng nêu thẳng lớn hơn → giữ
])
def test_parse_party(q, adults, children, total, spans):
    r = parse_party(q, parse_numeric(q).spans)
    assert (r.adults, r.children, r.total) == (adults, children, total)
    assert consumed(q, r.spans) == spans


@pytest.mark.parametrize("q", [
    "khách sạn 4 sao dưới 2 triệu",
    "3 khách sạn ở Đà Nẵng",            # "khách sạn" không phải "khách"
    "resort có 2 bể bơi",               # "bể" fold ra "be" nhưng không phải "bé"
    "resort co 2 be boi",
    "về Côn Đảo 2 ngày",
    "hội trường 50 người",              # ngoài 1–30
    "đi 3 đêm",
    "bốn người",                        # số bằng chữ không nhận
])
def test_parse_party_traps(q):
    assert parse_party(q, parse_numeric(q).spans) == PartyParse()


def test_parse_party_never_mixes_price_and_star_numbers():
    q = "khách sạn 4 sao dưới 2 triệu cho 3 người"
    num = parse_numeric(q)
    r = parse_party(q, num.spans)
    assert (num.star_min, num.price_max) == (4, 2_000_000) and (r.adults, r.children, r.total) == (None, None, 3)
    assert consumed(q, r.spans) == ["3 người"] and not set(r.spans) & set(num.spans)


def test_parse_party_respects_protected_spans():
    assert parse_party("cho 3 người", protected=[(4, 5)]) == PartyParse()
    assert parse_party("cho 3 người", protected=[(6, 11)]) == PartyParse()     # đơn vị nằm trong span đã tiêu
    assert parse_party("cho 3 người").total == 3
