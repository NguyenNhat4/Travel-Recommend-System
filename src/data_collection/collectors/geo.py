"""Chuẩn hoá điểm đến (gom tên thành phố/phường/tỉnh/địa danh về một tên thống nhất) và tiện ích toạ độ."""

from __future__ import annotations

import math
import re
from urllib.parse import quote

from .textutil import fold

# Tên chuẩn → các cách viết thường gặp (so khớp không dấu, theo ranh giới từ). Gồm cả địa danh riêng hay có trong tên tour
# (Pù Luông, Lan Hạ, DMZ, Sơn Đoòng…, thêm 12/10/2026) để tour không mang tên tỉnh vẫn về đúng điểm đến.
# Thứ tự trong dict không quan trọng: xem cách chọn khi một chuỗi khớp nhiều alias trong normalise_destination().
DESTINATION_ALIASES: dict[str, list[str]] = {
    "Nha Trang": ["nha trang", "cam ranh", "hon tre", "hon tam", "vinwonders nha trang", "bai dai cam ranh", "khanh hoa"],
    "Phú Quốc": ["phu quoc", "duong dong", "an thoi", "ganh dau", "bai truong", "ham ninh", "cua can", "grand world", "kien giang"],
    "Hạ Long": ["ha long", "halong", "bai chay", "tuan chau", "hon gai", "quang ninh"],
    "Hội An": ["hoi an", "nam hoi an", "cua dai", "an bang", "thang binh", "thang an", "duy xuyen", "dien ban", "quang nam",
               "cham island", "cu lao cham", "my son sanctuary", "thanh dia my son"],
    "Đà Nẵng": ["da nang", "danang", "son tra", "ngu hanh son", "my khe", "ba na", "bana hills", "hai chau", "lien chieu", "thanh khe", "hoa vang"],
    "Hà Nội": ["ha noi", "hanoi", "hoan kiem", "ba dinh", "tay ho", "long bien", "cau giay", "dong da", "hai ba trung", "times city", "ocean park", "gia lam"],
    "TP. Hồ Chí Minh": ["ho chi minh", "tp hcm", "hcmc", "sai gon", "saigon", "thu duc", "binh thanh", "phu nhuan", "tan binh", "go vap", "can gio", "district 1", "quan 1"],
    "Đà Lạt": ["da lat", "dalat", "lam dong"],
    "Sa Pa": ["sa pa", "sapa", "lao cai", "fansipan", "cat cat"],
    "Huế": ["hue", "thua thien", "lang co"],
    "Quy Nhơn": ["quy nhon", "nhon ly", "ky co", "binh dinh"],
    "Phan Thiết": ["phan thiet", "mui ne", "ham tien", "ke ga", "binh thuan"],
    "Vũng Tàu": ["vung tau", "ba ria", "long hai", "ho tram"],
    "Côn Đảo": ["con dao", "con son"],
    "Cần Thơ": ["can tho", "cai rang"],
    "Hải Phòng": ["hai phong", "do son", "vinhomes imperia"],
    "Ninh Bình": ["ninh binh", "trang an", "tam coc", "hoa lu", "bai dinh"],
    "Quảng Bình": ["quang binh", "dong hoi"],
    "Nghệ An": ["nghe an", "cua lo", "cua hoi", "thanh pho vinh", "tp vinh"],
    "Hà Tĩnh": ["ha tinh", "cua sot", "thien cam"],
    "Bắc Ninh": ["bac ninh"],
    "Hà Giang": ["ha giang", "dong van", "meo vac", "ma pi leng", "lung cu"],
    "Mộc Châu": ["moc chau"],
    "Tam Đảo": ["tam dao"],
    "Tuy Hòa": ["tuy hoa", "phu yen"],
    "Phan Rang": ["phan rang", "ninh thuan", "vinh hy"],
    "Quảng Ngãi": ["quang ngai"],
    "Buôn Ma Thuột": ["buon ma thuot", "dak lak"],
    "Hà Nam": ["ha nam", "tam chuc"],
    "Thanh Hóa": ["thanh hoa", "pu luong"],
    "Mai Châu": ["mai chau", "hoa binh"],
    "Cao Bằng": ["cao bang", "ban gioc"],
    "Rạch Giá": ["rach gia"],
    "Châu Đốc": ["chau doc", "an giang", "tra su"],
    # Mở rộng 19/09/2026
    "Pleiku": ["pleiku", "gia lai"],
    "Kon Tum": ["kon tum", "mang den"],
    "Tây Ninh": ["tay ninh", "nui ba den", "ba den", "black virgin"],
    "Cà Mau": ["ca mau", "dat mui"],
    "Bến Tre": ["ben tre"],
    "Mỹ Tho": ["my tho", "tien giang", "cai be"],
    "Sóc Trăng": ["soc trang"],
    "Bạc Liêu": ["bac lieu"],
    "Điện Biên": ["dien bien", "thanh pho dien bien phu", "tp dien bien phu"],  # "Điện Biên Phủ" một mình là tên đường ở mọi thành phố
    "Lạng Sơn": ["lang son", "dong dang"],
    "Sơn La": ["son la", "ta xua"],
    "Biên Hòa": ["bien hoa", "dong nai"],
    "Vĩnh Long": ["vinh long"],
    "Đồng Tháp": ["dong thap", "sa dec", "cao lanh"],
    "Quảng Trị": ["quang tri", "dong ha", "dmz", "vinh moc", "khe sanh", "hien luong"],
    # Điểm đến nhỏ chỉ cào từ Booking (19/09/2026). Chỉ dùng tên riêng ít trùng tên phường/xã.
    "Cát Bà": ["cat ba", "lan ha"],
    "Lý Sơn": ["ly son"],
    "Sầm Sơn": ["sam son"],
    "Hà Tiên": ["ha tien"],
    "Bảo Lộc": ["bao loc"],
    "Phong Nha": ["phong nha", "paradise cave", "son doong", "ke bang"],
    "Vân Đồn": ["van don"],
    "Mù Cang Chải": ["mu cang chai", "yen bai"],
    "Thái Nguyên": ["thai nguyen"],
    "Nam Định": ["nam dinh"],
    "Vĩnh Phúc": ["vinh phuc", "vinh yen", "dai lai"],
    "Móng Cái": ["mong cai"],
    "Long Xuyên": ["long xuyen"],
    "Bắc Kạn": ["bac kan", "ba be"],
    "Trà Vinh": ["tra vinh"],
    "Tam Kỳ": ["tam ky"],
    "Gia Nghĩa": ["gia nghia", "dak nong"],
    "Thái Bình": ["thai binh"],
    "Tuyên Quang": ["tuyen quang"],  # "Vinpearl Onsen Resort Tuyên Quang" không có city → tên khách sạn từng thành điểm đến
}

# Tên tỉnh / thành cấp tỉnh: yếu hơn tên thành phố, địa danh. Sau sáp nhập 2025 nhiều địa chỉ ghi
# "Hội An, TP Đà Nẵng" hay "Phú Quốc, An Giang" → tên cụ thể xuất hiện trước phải thắng.
PROVINCE_ALIASES = {
    "khanh hoa", "kien giang", "quang ninh", "quang nam", "lam dong", "lao cai", "binh dinh", "binh thuan",
    "thua thien", "ba ria", "nghe an", "ha tinh", "dak lak", "hoa binh", "an giang", "ninh thuan", "phu yen",
    "quang ngai", "quang binh", "ninh binh", "da nang", "hai phong", "ha noi", "ho chi minh", "can tho", "bac ninh",
    "gia lai", "tien giang", "dong thap", "dong nai", "quang tri", "son la", "dien bien", "lang son", "soc trang",
    "bac lieu", "ca mau", "ben tre", "vinh long", "yen bai", "dak nong",
}

_ALIAS_TABLE: list[tuple[re.Pattern, str, bool]] = [
    (re.compile(rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])"), canonical, alias in PROVINCE_ALIASES)
    for canonical, aliases in DESTINATION_ALIASES.items()
    for alias in aliases
]


# Tên đường trùng tên địa danh ("Đường Hai Bà Trưng", "Phố Huế", "Bien Hoa Street") không phải nơi cơ sở toạ lạc.
_STREET_BEFORE = re.compile(r"(?<![a-z0-9])(?<!thanh )(?:duong|pho|ngo|hem)\s$")  # "thành phố" không phải "phố"
_STREET_AFTER = re.compile(r"^\s(?:street|st|road|rd|avenue|ave)(?![a-z0-9])")
# "Điện Biên Phủ" không kèm "thành phố" là con đường (135 Điện Biên Phủ, Hải Phòng), không phải tỉnh Điện Biên.
_NOT_FOLLOWED_BY = {"Điện Biên": re.compile(r"^ phu(?![a-z0-9])")}


def destination_in_text(text: str | None) -> str | None:
    """Điểm đến nêu trong chuỗi (tên thành phố/địa danh thắng tên tỉnh, cùng cấp thì cái xuất hiện trước), hoặc None.
    Bỏ qua chỗ tên địa danh chỉ là tên đường (đứng sau "đường/phố/ngõ/hẻm" hoặc trước "street/road")."""
    f = fold(text)
    if not f:
        return None
    # "Nguyễn Huệ" là tên đường ở hầu hết các thành phố, không phải Huế.
    f = re.sub(r"(?<![a-z0-9])nguyen hue(?![a-z0-9])", " ", f)
    hits = []
    for pat, canonical, is_province in _ALIAS_TABLE:
        for m in pat.finditer(f):
            if _STREET_BEFORE.search(f[max(0, m.start() - 12):m.start()]) or _STREET_AFTER.match(f[m.end():m.end() + 8]):
                continue
            if canonical in _NOT_FOLLOWED_BY and _NOT_FOLLOWED_BY[canonical].match(f[m.end():m.end() + 6]):
                continue
            hits.append((is_province, m.start(), -len(m.group(0)), canonical))
            break
    return min(hits)[3] if hits else None


def normalise_destination(*candidates: str | None) -> str | None:
    """Thử lần lượt các chuỗi (cụ thể nhất trước). Không khớp alias nào thì trả lại chuỗi đầu tiên không rỗng."""
    for c in candidates:
        found = destination_in_text(c)
        if found:
            return found
    for c in candidates:
        if c and c.strip():
            return c.strip()
    return None


# ---------------------------------------------------------------------- toạ độ

# Tâm (trung tâm thành phố/thị trấn đại diện) của mỗi điểm đến, chỉ dùng để phát hiện toạ độ lệch nên sai vài km không sao.
# Nguồn: OpenStreetMap qua photon.komoot.io (15/09/2026). Vinh, Hà Tĩnh, Thanh Hóa, Cao Bằng lấy theo Wikipedia vì
# OSM đã đổi các điểm này thành tên phường sau sáp nhập 2025.
DESTINATION_CENTERS: dict[str, tuple[float, float]] = {
    "Nha Trang": (12.2472, 109.1892),
    "Phú Quốc": (10.2163, 103.9588),
    "Hạ Long": (20.9454, 107.1073),
    "Hội An": (15.8796, 108.3319),
    "Đà Nẵng": (16.0680, 108.2120),
    "Hà Nội": (21.0283, 105.8540),
    "TP. Hồ Chí Minh": (10.7737, 106.7166),
    "Đà Lạt": (11.9402, 108.4376),
    "Sa Pa": (22.3334, 103.8427),
    "Huế": (16.4639, 107.5863),
    "Quy Nhơn": (13.7772, 109.2264),
    "Phan Thiết": (10.9296, 108.1044),
    "Vũng Tàu": (10.3482, 107.0753),
    "Côn Đảo": (8.7003, 106.6068),
    "Cần Thơ": (10.0362, 105.7873),
    "Hải Phòng": (20.8831, 106.6790),
    "Ninh Bình": (20.2573, 105.9719),
    "Quảng Bình": (17.4598, 106.6122),   # Đồng Hới
    "Nghệ An": (18.6670, 105.6670),      # Vinh
    "Hà Tĩnh": (18.3330, 105.9000),
    "Bắc Ninh": (21.1781, 106.0710),
    "Hà Giang": (22.8156, 104.9818),
    "Mộc Châu": (20.8450, 104.6410),
    "Tam Đảo": (21.4560, 105.6445),
    "Tuy Hòa": (13.0867, 109.3072),
    "Phan Rang": (11.5770, 108.9865),
    "Quảng Ngãi": (15.1232, 108.8038),
    "Buôn Ma Thuột": (12.6797, 108.0447),
    "Hà Nam": (20.5377, 105.9347),       # Phủ Lý
    "Thanh Hóa": (19.8075, 105.7764),
    "Mai Châu": (20.6648, 105.0833),
    "Cao Bằng": (22.6667, 106.2583),
    "Rạch Giá": (10.0107, 105.0833),
    "Châu Đốc": (10.7102, 105.1175),
    # Mở rộng 19/09/2026: trung tâm thành phố/thị xã tỉnh lỵ (sai vài km không ảnh hưởng, chỉ để phát hiện toạ độ lệch)
    "Pleiku": (13.9833, 108.0000),
    "Kon Tum": (14.3500, 108.0000),
    "Tây Ninh": (11.3100, 106.0980),
    "Cà Mau": (9.1769, 105.1500),
    "Bến Tre": (10.2434, 106.3756),
    "Mỹ Tho": (10.3600, 106.3600),
    "Sóc Trăng": (9.6025, 105.9739),
    "Bạc Liêu": (9.2940, 105.7216),
    "Điện Biên": (21.3860, 103.0230),
    "Lạng Sơn": (21.8530, 106.7610),
    "Sơn La": (21.3270, 103.9140),
    "Biên Hòa": (10.9574, 106.8427),
    "Vĩnh Long": (10.2537, 105.9722),
    "Đồng Tháp": (10.4600, 105.6330),    # Cao Lãnh
    "Quảng Trị": (16.8163, 107.1003),    # Đông Hà
    "Cát Bà": (20.7267, 107.0489),
    "Lý Sơn": (15.3833, 109.1167),
    "Sầm Sơn": (19.7381, 105.9086),
    "Hà Tiên": (10.3833, 104.4833),
    "Bảo Lộc": (11.5475, 107.8078),
    "Phong Nha": (17.5911, 106.2836),
    "Vân Đồn": (21.0700, 107.4300),
    "Mù Cang Chải": (21.8531, 104.0833),
    "Thái Nguyên": (21.5928, 105.8442),
    "Nam Định": (20.4388, 106.1621),
    "Vĩnh Phúc": (21.3089, 105.6049),    # Vĩnh Yên
    "Móng Cái": (21.5333, 107.9667),
    "Long Xuyên": (10.3865, 105.4352),
    "Bắc Kạn": (22.1470, 105.8348),
    "Trà Vinh": (9.9347, 106.3452),
    "Tam Kỳ": (15.5736, 108.4740),
    "Gia Nghĩa": (12.0037, 107.6876),
    "Thái Bình": (20.4463, 106.3366),
}

# Bán kính hợp lý quanh tâm (km). Xa hơn thì toạ độ (hoặc chính điểm đến) đáng ngờ. Rộng hơn mặc định khi alias
# của điểm đến phủ vùng xa trung tâm: Cam Ranh (Nha Trang), Cần Giờ/Củ Chi (TP.HCM), Lăng Cô (Huế), Bản Giốc (Cao Bằng)…
DEFAULT_RADIUS_KM = 40.0
DESTINATION_RADIUS_KM: dict[str, float] = {
    "Nha Trang": 55, "TP. Hồ Chí Minh": 60, "Huế": 60, "Quảng Bình": 60, "Cao Bằng": 70, "Hạ Long": 50, "Hà Nội": 50,
    "Hải Phòng": 50, "Vũng Tàu": 50, "Hội An": 30, "Đà Nẵng": 30, "Nghệ An": 30, "Sa Pa": 30,
    "Ninh Bình": 30, "Côn Đảo": 25, "Cà Mau": 60,   # Đất Mũi cách thành phố Cà Mau ~90 km
    "Hà Tĩnh": 50,   # khu resort ven biển (Thiên Cầm, Xuân Thành, Vinpearl Hà Tĩnh) cách thành phố Hà Tĩnh 34–45 km
    "Cát Bà": 25, "Lý Sơn": 15, "Sầm Sơn": 20, "Hà Tiên": 30, "Bảo Lộc": 30, "Phong Nha": 40, "Vân Đồn": 40,
    "Mù Cang Chải": 40, "Móng Cái": 30, "Bắc Kạn": 60, "Tam Kỳ": 30,   # Ba Bể cách TP Bắc Kạn ~55 km
}

# Sân bay có đường bay thường lệ. Nguồn toạ độ: OurAirports (public domain), tải 15/09/2026.
AIRPORTS: dict[str, tuple[str, float, float]] = {
    "HAN": ("Sân bay quốc tế Nội Bài", 21.221201, 105.806999),
    "SGN": ("Sân bay quốc tế Tân Sơn Nhất", 10.8188, 106.652),
    "DAD": ("Sân bay quốc tế Đà Nẵng", 16.0439, 108.198997),
    "CXR": ("Sân bay quốc tế Cam Ranh", 11.9982, 109.219002),
    "PQC": ("Sân bay quốc tế Phú Quốc", 10.169783, 103.99353),
    "HPH": ("Sân bay quốc tế Cát Bi", 20.817428, 106.724315),
    "HUI": ("Sân bay quốc tế Phú Bài", 16.400581, 107.704094),
    "VCA": ("Sân bay quốc tế Cần Thơ", 10.083397, 105.709371),
    "VDO": ("Sân bay quốc tế Vân Đồn", 21.120693, 107.41539),
    "VII": ("Sân bay Vinh", 18.7376003265, 105.67099762),
    "DLI": ("Sân bay Liên Khương", 11.750556, 108.366997),
    "UIH": ("Sân bay Phù Cát", 13.955, 109.042),
    "BMV": ("Sân bay Buôn Ma Thuột", 12.668299675, 108.120002747),
    "CAH": ("Sân bay Cà Mau", 9.177667, 105.177778),
    "DIN": ("Sân bay Điện Biên Phủ", 21.3974990845, 103.008003235),
    "PXU": ("Sân bay Pleiku", 14.004500389099121, 108.01699829101562),
    "TBB": ("Sân bay Tuy Hòa", 13.0496, 109.334),
    "VCS": ("Sân bay Côn Đảo", 8.73183, 106.633003),
    "VDH": ("Sân bay Đồng Hới", 17.515, 106.590556),
    "VKG": ("Sân bay Rạch Giá", 9.95802997234, 105.132379532),
    "THD": ("Sân bay Thọ Xuân", 19.901667, 105.467778),
    "VCL": ("Sân bay Chu Lai", 15.4033, 108.706001),
}

# Khung Việt Nam (đất liền + đảo gần bờ, không gồm Hoàng Sa/Trường Sa): toạ độ ngoài khung là lỗi nguồn.
_VN_LAT = (8.0, 23.6)
_VN_LNG = (102.0, 109.7)


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lng2 - lng1)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 6371.0 * 2 * math.asin(math.sqrt(h))


def _in_vn(lat: float, lng: float) -> bool:
    return _VN_LAT[0] <= lat <= _VN_LAT[1] and _VN_LNG[0] <= lng <= _VN_LNG[1]


def clean_coords(lat, lng) -> tuple[float | None, float | None]:
    """Toạ độ hợp lệ trong Việt Nam, hoặc (None, None). Nguồn ghi đảo vĩ độ/kinh độ thì đảo lại."""
    try:
        lat, lng = float(lat), float(lng)
    except (TypeError, ValueError):
        return None, None
    if _in_vn(lat, lng):
        return lat, lng
    if _in_vn(lng, lat):
        return lng, lat
    return None, None


def destination_radius_km(destination: str | None) -> float:
    return float(DESTINATION_RADIUS_KM.get(destination or "", DEFAULT_RADIUS_KM))


def km_from_destination(destination: str | None, lat: float | None, lng: float | None) -> float | None:
    center = DESTINATION_CENTERS.get(destination or "")
    if center is None or lat is None or lng is None:
        return None
    return haversine_km(center[0], center[1], lat, lng)


def destination_bbox(destination: str, radius_km: float | None = None) -> tuple[float, float, float, float] | None:
    """(min_lng, min_lat, max_lng, max_lat) quanh tâm điểm đến."""
    center = DESTINATION_CENTERS.get(destination)
    if center is None:
        return None
    r = radius_km or destination_radius_km(destination)
    dlat = r / 111.0
    dlng = r / (111.0 * math.cos(math.radians(center[0])))
    return center[1] - dlng, center[0] - dlat, center[1] + dlng, center[0] + dlat


def maps_url(lat: float | None, lng: float | None) -> str:
    """Link mở toạ độ trên Google Maps (Maps URLs, không cần API key)."""
    if lat is None or lng is None:
        return ""
    return "https://www.google.com/maps/search/?api=1&query=" + quote(f"{lat:.6f},{lng:.6f}")
