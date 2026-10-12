"""Tối ưu tổng quãng đường của chuyến và đổi khách sạn giữa chuyến (AC-AGT-04, chốt 2026-10-07). Thuần Python.

Quãng đường của chuyến (`route_cost`), với `H_d` là khách sạn đêm thứ d và S_đến/S_đi là sân bay của chặng bay đã chọn
(`flights.airports`, chốt 2026-10-09):
- ngày 1: S_đến → H₁, rồi H₁ → A → B → H₁ (về nhận phòng trước khi đi chơi); không có sân bay thì A → B → H₁;
- ngày d giữa chuyến: H(d−1) → A → B → H_d;
- ngày cuối: H(n−1) → A → B → S_đi (không còn đêm nào sau nó); không có sân bay thì dừng ở B.
Chuyến 1 ngày vẫn có 1 đêm (`max(1, days − 1)`) nên ngày đó kết thúc ở khách sạn: A → B → H₁ (có sân bay đến thì thêm
S_đến → H₁ ở đầu ngày). Điểm chưa rõ vị trí bị bỏ qua khi cộng chặng (không cộng, không đoán).

`optimize` chọn khách sạn từng đêm, điểm nào đi ngày nào và thứ tự buổi để chi phí = quãng đường + phạt đổi khách sạn
nhỏ nhất; có ngân sách thì chỉ trong các lịch vừa ngân sách (chốt 2026-10-08). Kèm tối đa `MAX_OPTIONS` phương án khác
(đổi khách sạn: đắt hơn mà gần hơn, hoặc rẻ hơn mà xa hơn) để người dùng tự cân. Số chỗ mỗi ngày (luật rải ngày, giờ bay, hoạt động cả ngày) do `planning.compose_plan` quyết trước và giữ nguyên.
Gán điểm vào ngày giải chính xác bằng quy hoạch động trên tập con khi có tối đa `EXACT_LIMIT` điểm; nhiều hơn thì tìm kiếm
cục bộ (đổi chỗ hai điểm giữa hai ngày) từ cách xếp ban đầu, nên chỉ gần tối ưu.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from itertools import combinations

from .geo import Point, band, haversine_km, medoid
from .types import Product

# Đổi khách sạn (AC-AGT-04): chuyến từ 5 ngày (4 đêm), tối đa 1 lần, mỗi khách sạn ít nhất 2 đêm, phạt 15 km mỗi lần.
STAY_CHANGE_MIN_DAYS = 5
STAY_MIN_NIGHTS = 2
STAY_CHANGE_PENALTY_KM = 15.0
# Giới hạn để giải chính xác: 2^10 trạng thái. Chuyến 6–7 ngày đủ chỗ (12–14 điểm) dùng tìm kiếm cục bộ.
EXACT_LIMIT = 10
# Số khách sạn đem ra so: gần các điểm nhất (một khách sạn), và gần mỗi cụm nhất (khi đổi khách sạn).
TOP_STAYS = 6
TOP_STAYS_PER_CLUSTER = 4
# Thay một điểm đã chọn bằng điểm bị bỏ chỉ khi quãng đường giảm ít nhất một mức khoảng cách (2 km).
SWAP_MIN_GAIN_KM = 2.0
# Số chuỗi khách sạn được giải chính xác, sau khi xếp hạng mọi chuỗi bằng tìm kiếm cục bộ (giữ thời gian dưới ~200 ms).
EXACT_SHORTLIST = 3
SWAP_ROUNDS = 2
# Thêm khách sạn rẻ nhất vào danh sách đem ra so, để phía "rẻ hơn, xa hơn" của phương án khác có lịch để chọn.
CHEAP_STAYS = 3
# Phương án khác (chốt 2026-10-08): chênh ít nhất một mức khoảng cách; tối đa 3, mỗi phía tối đa 2, phía gần hơn trước.
OPTION_MIN_KM = 2.0
MAX_OPTIONS = 3
OPTIONS_PER_SIDE = 2
_EPS = 1e-9


Airports = tuple[Point | None, Point | None]
NO_AIRPORTS: Airports = (None, None)


def day_ends(nights: Sequence[Point | None], days_count: int,
             airports: Airports = NO_AIRPORTS) -> tuple[list[tuple[Point | None, Point | None]], float]:
    """(điểm đầu và điểm cuối của từng ngày, km cố định của chặng sân bay → khách sạn đêm 1).

    Ngày 1 có sân bay đến và khách sạn đêm 1 thì xuất phát từ khách sạn (đã về nhận phòng), chặng sân bay → khách sạn cộng
    riêng vì không phụ thuộc điểm nào đi ngày 1; không có khách sạn thì xuất phát từ sân bay. Ngày cuối không có đêm sau
    thì kết thúc ở sân bay đi."""
    arrival, departure = airports
    ends = [(nights[index - 1] if 1 <= index <= len(nights) else None,
             nights[index] if index < len(nights) else None) for index in range(days_count)]
    fixed = 0.0
    if ends and arrival is not None:
        hotel = nights[0] if nights else None
        if hotel is not None:
            fixed = haversine_km(arrival, hotel)
        ends[0] = (hotel if hotel is not None else arrival, ends[0][1])
    if ends and departure is not None and ends[-1][1] is None:
        ends[-1] = (ends[-1][0], departure)
    return ends, fixed


def route_cost(days: Sequence[Sequence[Point | None]], nights: Sequence[Point | None],
               airports: Airports = NO_AIRPORTS) -> float:
    """Quãng đường (km) của chuyến; `days[d]` là toạ độ các điểm của ngày d theo thứ tự buổi, `nights[j]` là khách sạn
    đêm j (đêm của ngày j + 1), `airports` là (sân bay đến, sân bay đi). Toạ độ None bị bỏ qua."""
    ends, total = day_ends(nights, len(days), airports)
    for (start, end), points in zip(ends, days):
        legs = [p for p in (start, *points, end) if p is not None]
        total += sum(haversine_km(a, b) for a, b in zip(legs, legs[1:]))
    return total


@dataclass(frozen=True)
class DayShape:
    """Số điểm của một ngày và ngày đó có dành cho hoạt động cả ngày không (do `compose_plan` quyết)."""

    capacity: int
    full_day: bool


@dataclass(frozen=True)
class Stay:
    product: Product
    from_night: int
    nights: int


@dataclass(frozen=True)
class Route:
    days: list[list[Product]]
    stays: list[Stay]
    cost_km: float

    @property
    def stay_change(self) -> bool:
        return len(self.stays) > 1


@dataclass(frozen=True)
class Option:
    """Một phương án khác: các khách sạn theo đêm, chênh km và chênh tiền so với lịch được chọn (dương = nhiều hơn), và
    số tiền vượt ngân sách (None khi không vượt hoặc không có ngân sách)."""

    stays: list[Stay]
    km_delta: float
    money_delta: int
    over_budget: int | None
    route: Route  # lịch đã giải của phương án (điểm theo ngày, khách sạn theo đêm), để dựng lịch đầy đủ


@dataclass(frozen=True)
class Planned:
    route: Route
    options: list[Option]


def _two_medoids(points: dict[str, Point]) -> list[dict[str, Point]]:
    """Chia các điểm thành 2 cụm (k-medoids, khởi tạo tất định: medoid chung và điểm xa nó nhất)."""
    first = medoid(points)
    if first is None or len(points) < 2:
        return [points]
    second = points[max(sorted(points), key=lambda key: haversine_km(points[key], first))]
    centres = [first, second]
    for _ in range(10):
        groups: list[dict[str, Point]] = [{}, {}]
        for key in sorted(points):
            nearest = min((0, 1), key=lambda c: (haversine_km(points[key], centres[c]), c))
            groups[nearest][key] = points[key]
        if not all(groups):
            return [points]
        updated = [medoid(group) for group in groups]
        if updated == centres:
            break
        centres = updated
    return groups


class _Solver:
    """Gán điểm vào ngày cho một chuỗi khách sạn cố định. Đánh chỉ số theo productId để kết quả không phụ thuộc thứ tự
    ứng viên. Khoảng cách và chi phí từng ngày được nhớ theo productId suốt một lần `optimize`, vì các chuỗi khách sạn
    và các lần thử thay điểm dùng chung chúng."""

    def __init__(self, positions: dict[str, Point]):
        self.positions = positions
        self._km: dict[tuple[Point, Point], float] = {}
        self._day_cache: dict[tuple, tuple[float, tuple[str, ...]]] = {}
        self.items: list[Product] = []

    def load(self, items: list[Product]) -> None:
        self.items = sorted(items, key=lambda p: p["productId"])
        self._ids = [p["productId"] for p in self.items]
        self._index = {pid: i for i, pid in enumerate(self._ids)}

    def _distance(self, a: Point, b: Point) -> float:
        key = (a, b) if a <= b else (b, a)
        if key not in self._km:
            self._km[key] = haversine_km(a, b)
        return self._km[key]

    def _legs(self, start: Point | None, order: tuple[str, ...], end: Point | None) -> float:
        legs = [p for p in (start, *(self.positions.get(pid) for pid in order), end) if p is not None]
        return sum(self._distance(a, b) for a, b in zip(legs, legs[1:]))

    def best_day(self, start: Point | None, end: Point | None, ids: list[str]) -> float:
        """Quãng đường nhỏ nhất của một ngày gồm đúng các điểm này (thử hai thứ tự)."""
        orders = [tuple(ids)] if len(ids) < 2 else [tuple(ids), tuple(reversed(ids))]
        return min(self._legs(start, order, end) for order in orders)

    def day(self, start: Point | None, end: Point | None, chosen: tuple[int, ...]) -> tuple[float, tuple[int, ...]]:
        ids = tuple(self._ids[i] for i in chosen)
        key = (start, end, ids)
        if key not in self._day_cache:
            orders = [ids] if len(ids) < 2 else [ids, tuple(reversed(ids))]
            self._day_cache[key] = min(((self._legs(start, order, end), order) for order in orders),
                                       key=lambda item: item[0] - _EPS * (item[1] == ids))
        cost, order = self._day_cache[key]
        return cost, tuple(self._index[pid] for pid in order)

    def exact(self, ends: list[tuple[Point | None, Point | None]], shapes: list[DayShape],
              full: set[int]) -> tuple[float, list[tuple[int, ...]]]:
        states: dict[int, tuple[float, tuple[tuple[int, ...], ...]]] = {0: (0.0, ())}
        indexes = range(len(self.items))
        for (start, end), shape in zip(ends, shapes):
            pool = [i for i in indexes if (i in full) == shape.full_day]
            following: dict[int, tuple[float, tuple[tuple[int, ...], ...]]] = {}
            for mask, (cost, chosen_days) in states.items():
                free = [i for i in pool if not mask >> i & 1]
                for chosen in combinations(free, shape.capacity):
                    day_cost, order = self.day(start, end, chosen)
                    bits = mask
                    for i in chosen:
                        bits |= 1 << i
                    value = cost + day_cost
                    known = following.get(bits)
                    if known is None or value < known[0] - _EPS:
                        following[bits] = (value, chosen_days + (order,))
            states = following
        if not states:
            raise ValueError("day shapes do not match the selected activities")
        cost, orders = min(states.values(), key=lambda item: item[0])
        return cost, list(orders)

    def local(self, ends: list[tuple[Point | None, Point | None]], start_days: list[list[int]],
              full: set[int]) -> tuple[float, list[tuple[int, ...]]]:
        """Đổi chỗ hai điểm giữa hai ngày khi tổng giảm; quét tiếp sau mỗi lần đổi, dừng khi một lượt quét không đổi gì."""
        days = [tuple(sorted(day)) for day in start_days]
        scored = [self.day(start, end, chosen) for (start, end), chosen in zip(ends, days)]
        improved = True
        while improved:
            improved = False
            for first in range(len(days)):
                for second in range(first + 1, len(days)):
                    for i in range(len(days[first])):
                        for j in range(len(days[second])):
                            a, b = days[first][i], days[second][j]
                            if (a in full) != (b in full):
                                continue
                            one = tuple(sorted(days[first][:i] + (b,) + days[first][i + 1:]))
                            two = tuple(sorted(days[second][:j] + (a,) + days[second][j + 1:]))
                            new_one, new_two = self.day(*ends[first], one), self.day(*ends[second], two)
                            if new_one[0] + new_two[0] < scored[first][0] + scored[second][0] - _EPS:
                                days[first], days[second] = one, two
                                scored[first], scored[second] = new_one, new_two
                                improved = True
        return sum(score for score, _ in scored), [order for _, order in scored]

    def solve(self, ends, shapes, initial: list[list[Product]], *, exact: bool = True) -> tuple[float, list[list[Product]]]:
        index = {p["productId"]: i for i, p in enumerate(self.items)}
        full = {index[p["productId"]] for day, shape in zip(initial, shapes) if shape.full_day for p in day}
        if exact and len(self.items) <= EXACT_LIMIT:
            cost, orders = self.exact(ends, shapes, full)
        else:
            cost, orders = self.local(ends, [sorted(index[p["productId"]] for p in day) for day in initial], full)
        return cost, [[self.items[i] for i in order] for order in orders]


def _stay_plans(hotels: list[Product], positions: dict[str, Point], activity_points: dict[str, Point],
                nights: int, days_count: int, rank: Callable[[Product], tuple]) -> list[list[Product]]:
    """Các chuỗi khách sạn theo đêm đem ra so (mỗi chuỗi dài `nights`)."""

    def nearest(points: dict[str, Point], limit: int) -> list[Product]:
        def mean(hotel: Product) -> float:
            own = positions[hotel["productId"]]
            return sum(haversine_km(own, p) for p in points.values()) / len(points)
        return sorted(hotels, key=lambda h: (band(mean(h)), *rank(h)))[:limit]

    def cheapest(limit: int) -> list[Product]:
        priced = [h for h in hotels if isinstance(h.get("unitPrice"), (int, float))]
        return sorted(priced, key=lambda h: (h["unitPrice"], *rank(h)))[:limit]

    singles = nearest(activity_points, TOP_STAYS)
    singles += [h for h in cheapest(CHEAP_STAYS) if h not in singles]
    premium = sorted((h for h in hotels if (h.get("attributes") or {}).get("starRating", 0) >= 4),
                     key=_premium_order)
    singles += [h for h in premium[:2] if h not in singles]
    plans = [[hotel] * nights for hotel in singles]
    if days_count < STAY_CHANGE_MIN_DAYS or nights < 2 * STAY_MIN_NIGHTS:
        return plans
    clusters = _two_medoids(activity_points)
    if len(clusters) < 2:
        return plans
    near = [nearest(cluster, TOP_STAYS_PER_CLUSTER) for cluster in clusters]
    for first, second in ((0, 1), (1, 0)):
        for h1 in near[first]:
            for h2 in near[second]:
                if _parent(h1) == _parent(h2):
                    continue
                for split in range(STAY_MIN_NIGHTS, nights - STAY_MIN_NIGHTS + 1):
                    plans.append([h1] * split + [h2] * (nights - split))
    return plans


def _full(product: Product) -> bool:
    duration = (product.get("attributes") or {}).get("durationMinutes")
    return isinstance(duration, (int, float)) and duration >= 360


def _parent(product: Product) -> str:
    return (product.get("attributes") or {}).get("parentProductId") or product["productId"]


def _stays(sequence: list[Product]) -> list[Stay]:
    stays: list[Stay] = []
    for night, hotel in enumerate(sequence, start=1):
        if stays and stays[-1].product["productId"] == hotel["productId"]:
            stays[-1] = Stay(hotel, stays[-1].from_night, stays[-1].nights + 1)
        else:
            stays.append(Stay(hotel, night, 1))
    return stays


def optimize(initial: list[list[Product]], shapes: list[DayShape], spare: list[Product], hotels: list[Product],
             positions: dict[str, Point], days_count: int, money: Callable[[list[Stay], list[Product]], tuple[int, int]],
             rank: Callable[[Product], tuple], budget_left: int | None = None,
             airports: Airports = NO_AIRPORTS) -> Planned:
    """Lịch tốt nhất và các phương án khác; so bằng khoá tất định để cùng ứng viên luôn ra cùng lịch.

    `initial`: điểm đã chọn theo ngày (cách xếp của luật rải ngày); `shapes`: số chỗ mỗi ngày; `spare`: điểm bị bỏ, theo
    thứ tự ưu tiên, được thử thay vào nếu đỡ đi ít nhất `SWAP_MIN_GAIN_KM`; `hotels`: khách sạn rõ vị trí cùng mức nguồn
    tốt nhất (rỗng thì lịch không có khách sạn); `money(stays, activities)`: `(số sản phẩm chưa rõ giá, tổng tiền đã
    biết)`; `rank(product)`: thứ tự ưu tiên cũ (nguồn, giá, sao, mã) để phá hoà; `budget_left`: ngân sách trừ vé máy bay,
    None khi không có ngân sách; `airports`: (sân bay đến, sân bay đi) của chặng bay đã chọn, cộng vào quãng đường nên
    cũng ảnh hưởng khách sạn được chọn và chênh km của phương án khác.

    Khoá: không có ngân sách thì (mức khoảng cách, tiền, mã) — gần trước, rẻ sau. Có ngân sách thì lịch vừa ngân sách
    (giá biết đủ và tổng ≤ `budget_left`) đứng trước và so như trên; không lịch nào vừa thì lịch rẻ nhất thắng.
    """
    nights = max(1, days_count - 1)
    solver = _Solver(positions)

    def fits(cash: tuple[int, int]) -> bool:
        return cash[0] == 0 and budget_left is not None and cash[1] <= budget_left

    def scored(selected: list[list[Product]], sequence: list[Product], *,
               exact: bool) -> tuple[tuple, Route, tuple[int, int]]:
        """Chấm một chuỗi khách sạn; `solver` phải đã `load` đúng các điểm của `selected`."""
        ends, fixed = day_ends([positions[h["productId"]] for h in sequence], days_count, airports)
        km, days = solver.solve(ends, shapes, selected, exact=exact)
        km += fixed
        stays = _stays(sequence)
        cost = km + STAY_CHANGE_PENALTY_KM * max(0, len(stays) - 1)
        cash = money(stays, [p for day in days for p in day])
        ids = (tuple(s.product["productId"] for s in stays), tuple(s.nights for s in stays),
               tuple(tuple(p["productId"] for p in day) for day in days))
        if budget_left is None:
            key = (band(cost), cash, *ids)
        elif fits(cash):
            key = (0, band(cost), cash, *ids)
        else:
            key = (1, cash, band(cost), *ids)
        return key, Route(days, stays, km), cash

    def evaluate(selected: list[list[Product]], sequences: list[list[Product]], *,
                 exact: bool = True) -> tuple[tuple, Route, tuple[int, int]]:
        """Phương án tốt nhất trong các chuỗi khách sạn. Nhiều chuỗi thì xếp hạng trước bằng tìm kiếm cục bộ (nhanh),
        rồi chỉ giải chính xác `EXACT_SHORTLIST` chuỗi đứng đầu."""
        solver.load([p for day in selected for p in day])
        if len(sequences) > EXACT_SHORTLIST:
            rough = sorted((scored(selected, sequence, exact=False)[0], index)
                           for index, sequence in enumerate(sequences))
            sequences = [sequences[index] for _, index in rough[:EXACT_SHORTLIST]]
        return min((scored(selected, sequence, exact=exact) for sequence in sequences), key=lambda item: item[0])

    def sequences_for(selected: list[list[Product]]) -> list[list[Product]]:
        points = {p["productId"]: positions[p["productId"]] for day in selected for p in day
                  if p["productId"] in positions}
        if not hotels or not points:
            return [[]] if not hotels else [[sorted(hotels, key=rank)[0]] * nights]
        return _stay_plans(hotels, positions, points, nights, days_count, rank)

    selected = [list(day) for day in initial]
    _, route, cash = evaluate(selected, sequences_for(selected))
    for _ in range(SWAP_ROUNDS):
        selected = [list(day) for day in route.days]
        sequence = [s.product for s in route.stays for _ in range(s.nights)]
        ends, _ = day_ends([positions[h["productId"]] for h in sequence], days_count, airports)
        changed = False
        for day_index in range(len(selected)):
            start, end = ends[day_index]
            for position in range(len(selected[day_index])):
                for candidate in list(spare):
                    current = selected[day_index][position]
                    if rank(candidate)[0] != rank(current)[0] or _full(candidate) != _full(current):
                        continue
                    # Lọc rẻ: thay vào đúng ngày đó mà ngày không ngắn đi thì bỏ qua, khỏi đánh giá lại cả lịch.
                    before = [p["productId"] for p in route.days[day_index]]
                    after = [candidate["productId"] if pid == current["productId"] else pid for pid in before]
                    if solver.best_day(start, end, after) >= solver.best_day(start, end, before) - _EPS:
                        continue
                    trial = [list(day) for day in selected]
                    trial[day_index][position] = candidate
                    _, trial_route, trial_cash = evaluate(trial, [sequence], exact=False)
                    # Có ngân sách: không đổi một lịch đang vừa ngân sách thành lịch vượt ngân sách.
                    if fits(cash) and not fits(trial_cash):
                        continue
                    if trial_route.cost_km <= route.cost_km - SWAP_MIN_GAIN_KM:
                        spare = [p for p in spare if p is not candidate] + [current]
                        route, cash = trial_route, trial_cash
                        selected = [list(day) for day in route.days]
                        changed = True
        if not changed:
            break
        _, route, cash = evaluate(selected, sequences_for(selected))
    return Planned(route, _options(route, cash, sequences_for(route.days), solver, scored, budget_left))


def _signature(stays: list[Stay]) -> tuple:
    return tuple((s.product["productId"], s.nights) for s in stays)


def _premium_order(product: Product) -> tuple:
    rating = product.get("rating") or 0
    reviews = product.get("reviewCount") or 0
    stars = (product.get("attributes") or {}).get("starRating") or 0
    return (0 if rating >= 4.5 and reviews >= 50 else 1, -rating, -reviews, -stars,
            product.get("unitPrice") or float("inf"), product["productId"])


def _options(route: Route, cash: tuple[int, int], sequences: list[list[Product]], solver: _Solver,
             scored: Callable[..., tuple[tuple, Route, tuple[int, int]]], budget_left: int | None) -> list[Option]:
    """Phương án đại diện cho giá, khoảng cách và cao cấp; giữ lịch đang chọn.

    Giữ cùng các hoạt động. Chỉ giải chính xác các phương án đại diện;
    không tạo thẻ trùng khi một khách sạn thắng nhiều tiêu chí. AC-AGT-04, chốt 12/10.
    """
    if cash[0] or not route.stays:
        return []
    selected = [list(day) for day in route.days]
    solver.load([p for day in selected for p in day])
    main = _signature(route.stays)
    main_sequence = [stay.product for stay in route.stays for _ in range(stay.nights)]
    pool = {main: (route.cost_km, cash[1], main_sequence)}
    for sequence in sequences:
        _, rough, rough_cash = scored(selected, sequence, exact=False)
        if not rough_cash[0]:
            pool.setdefault(_signature(rough.stays), (rough.cost_km, rough_cash[1], sequence))
    entries = list(pool.values())
    picks = [min(entries, key=lambda e: (e[1], e[0])), min(entries, key=lambda e: (e[0], e[1]))]
    premium = [entry for entry in entries if all((p.get("attributes") or {}).get("starRating", 0) >= 4
                                                for p in entry[2])]
    if premium:
        picks.append(min(premium, key=lambda e: max(_premium_order(p) for p in e[2])))
    seen = {main}
    options = []
    for _, _, sequence in picks:
        if _signature(_stays(sequence)) in seen:
            continue
        _, solved, solved_cash = scored(selected, sequence, exact=True)
        signature = _signature(solved.stays)
        if signature in seen:
            continue
        seen.add(signature)
        total = solved_cash[1]
        over = total - budget_left if budget_left is not None and total > budget_left else None
        options.append(Option(solved.stays, solved.cost_km - route.cost_km, total - cash[1], over, solved))
    return options[:MAX_OPTIONS]


__all__ = ["Airports", "DayShape", "EXACT_LIMIT", "MAX_OPTIONS", "NO_AIRPORTS", "OPTION_MIN_KM", "Option", "Planned",
           "Route", "STAY_CHANGE_MIN_DAYS", "STAY_CHANGE_PENALTY_KM", "STAY_MIN_NIGHTS", "Stay", "day_ends", "optimize",
           "route_cost"]
