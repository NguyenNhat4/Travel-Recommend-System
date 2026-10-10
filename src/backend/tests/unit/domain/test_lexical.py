import unicodedata

from src.backend.app.domain.search import STOPWORDS, coverage, fold, query_tokens, tokens


def test_fold_strips_accents_case_and_punctuation():
    assert fold("Vinpearl Resort & Spa Nha Trang Bay") == "vinpearl resort spa nha trang bay"
    assert fold("Đà Nẵng") == "da nang"
    assert fold("VinWonders") == "vinwonders"
    assert fold(unicodedata.normalize("NFD", "Hội An")) == "hoi an"  # dấu tổ hợp (NFD) fold về cùng chuỗi
    assert fold("  ") == "" and tokens("") == []


def test_query_tokens_keep_short_place_syllables_and_drop_function_words():
    assert query_tokens("khách sạn ở Cà Mau") == ["khach", "san", "ca", "mau"]
    assert query_tokens("vé VinWonders cho gia đình") == ["ve", "vinwonders", "gia", "dinh"]
    assert query_tokens("VinWonders VinWonders") == ["vinwonders"]
    assert "cho" in STOPWORDS and "khach" not in STOPWORDS


def test_coverage_rescues_names_not_single_syllable_overlaps():
    assert coverage(query_tokens("VinWonders"), set(tokens("[VinWonders Nha Trang] Vé vào cửa"))) == 1.0
    assert coverage(query_tokens("melia vinpearl hue"), set(tokens("Meliá Vinpearl Hai Phong Rivera"))) == 2 / 3
    assert coverage(query_tokens("khách sạn ở Cà Mau"), set(tokens("Hoa Mau Don Homestay"))) == 0.25
    assert coverage([], set(tokens("Resort A"))) == 0.0


def test_is_unaccented_detects_full_queries_without_diacritics_only():
    from src.backend.app.domain.search import is_unaccented
    assert is_unaccented("khach san o da lat co nha hang")                 # 6 token sau khi bỏ từ chức năng
    assert is_unaccented("tim khach san o nha trang co ho boi gia tot")
    assert not is_unaccented("khách sạn ở Đà Lạt có nhà hàng")              # có dấu
    assert not is_unaccented("KS ở NT")                                     # có dấu ("ở")
    assert is_unaccented("resort Nha Trang 2tr")                            # 3 token chữ không dấu; "2tr" không tính
    assert not is_unaccented("VinWonders") and not is_unaccented("Sun World")   # câu thương hiệu ngắn (< 3 token)
    assert not is_unaccented("2024 2025 2026") and not is_unaccented("")      # không có chữ cái / toàn số
    assert is_unaccented("khach san ha long", min_tokens=4) and not is_unaccented("khach san ha long", min_tokens=5)
