"""Lượt cào lớn làm mới cả catalog (setting `refresh.existing`) và các chốt chống "một chỗ hỏng chết cả lượt".

Bối cảnh (08/10/2026): lượt full chỉ cào top N khách sạn mỗi điểm đến trong `@deep`, 65% catalog (snapshot 23/09) không bao giờ
được cào lại; tìm Booking trả 0 ở mọi điểm đến mà lượt vẫn "Xong"; một bước quá giờ hay một dòng lỗi làm chết cả lượt.
"""
import asyncio
import contextlib
import json
import os
import signal
import subprocess
import sys
import time
from collections import Counter
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

import alerts
import fresh_catalog as job
import fresh_settings
import normalise as nm
import pipeline_runtime
from collectors.agoda_api import AgodaCollector, AgodaOptions
from collectors.booking_hotels import REFRESH_PRIORITY, BookingHotels
from collectors.common import Paths, StateDB
from collectors.plan import DEFAULT_BUDGET, select_destinations
from fresh_catalog_db import prepare_rows, refresh_targets_from_rows
from normalise import product_id

DEEP = select_destinations("@deep")


# ---------------------------------------------------------------------------------------------- danh sách làm mới từ DB


def prop(ref, destination="Nha Trang", **attrs):
    return {"source_ref": ref, "taxonomy": "hotel", "destination": destination,
            "attributes": {"level": "property", **attrs}}


def test_refresh_targets_take_own_and_merged_rows_oldest_first():
    rows = [
        prop("booking:hotel:1", url="https://www.booking.com/hotel/vn/a.vi.html", lastSeenAt="2026-10-07"),
        prop("booking:hotel:2", url="https://www.booking.com/hotel/vn/b.html"),  # snapshot cũ: chưa thấy lần nào
        # dòng Vinpearl đã gộp ref Booking và Agoda: lấy bookingUrl/agodaUrl
        prop("vinpearl:hotel:x", url="https://vinpearl.com/x", sameAs=["booking:hotel:3", "agoda:hotel:c:nha-trang"],
             bookingUrl="https://www.booking.com/hotel/vn/c.vi.html?aid=1",
             agodaUrl="https://www.agoda.com/vi-vn/c/hotel/nha-trang-vn.html", lastSeenAt="2026-10-01"),
        prop("agoda:hotel:d:phu-quoc-island", "Phú Quốc", url="https://www.agoda.com/vi-vn/d/hotel/phu-quoc-island-vn.html",
             agodaHotelId="237061", lastSeenAt="2026-10-08"),
        prop("agoda:hotel:e:hue", "Huế", url="https://www.agoda.com/vi-vn/e/hotel/hue-vn.html", mergedInto="p1"),  # đã gộp
        # Agoda đánh số bản trùng bằng '_' (lượt thử local 08/10: 5 khách sạn Nha Trang bị bỏ sót vì regex không nhận '_')
        prop("agoda:hotel:the-anam_4:nha-trang", url="https://www.agoda.com/vi-vn/the-anam_4/hotel/nha-trang-vn.html",
             lastSeenAt="2026-10-02"),
        {"source_ref": "booking:hotel:1:room:9", "taxonomy": "hotel", "destination": "Nha Trang",
         "attributes": {"level": "room", "url": "https://www.booking.com/hotel/vn/a.vi.html"}},  # phòng: không lấy
        prop("booking:hotel:4", url=None),  # thiếu URL: bỏ, không đoán
    ]
    out = refresh_targets_from_rows(rows)
    assert [x["url"] for x in out["booking"]] == ["https://www.booking.com/hotel/vn/b.vi.html",
                                                 "https://www.booking.com/hotel/vn/c.vi.html",
                                                 "https://www.booking.com/hotel/vn/a.vi.html"]
    assert [(x["slug"], x["city"], x["hotelId"], x["destination"]) for x in out["agoda"]] == [
        ("c", "nha-trang", None, "Nha Trang"), ("the-anam_4", "nha-trang", None, "Nha Trang"),
        ("d", "phu-quoc-island", 237061, "Phú Quốc")]


# ---------------------------------------------------------------------------------------------- Agoda


def agoda_item(slug, city, dest, hotel_id=None):
    return {"url": f"https://www.agoda.com/vi-vn/{slug}/hotel/{city}-vn.html", "slug": slug, "city": city,
            "destination": dest, "hotelId": hotel_id}


def test_agoda_refresh_joins_scope_beyond_per_city_and_outside_plan(tmp_path):
    paths = Paths(tmp_path).ensure()
    refresh = (agoda_item("a", "nha-trang", "Nha Trang", 11),       # đã có trong phạm vi tìm mới
               agoda_item("b", "phan-thiet", "Phan Thiết", 22),      # ngoài @deep: vẫn làm mới
               agoda_item("c", "nha-trang", "Nha Trang"),            # chưa biết hotel_id: mở trang để lấy
               agoda_item("gone", "hue", "Huế"))                     # trang đã gỡ ở lần trước
    c = AgodaCollector(paths, AgodaOptions(destinations=DEEP, per_city=1, refresh=refresh))
    with c.state.db:
        c.state.db.execute("INSERT INTO hotels (url, slug, city, rank, hotel_id) VALUES (?, 'a', 'nha-trang', 1, 11)",
                           (refresh[0]["url"],))
        c.state.db.execute("INSERT INTO hotels (url, slug, city, rank, id_status) VALUES (?, 'gone', 'hue', 2, 'gone')",
                           (refresh[3]["url"],))
    scope = c.add_refresh(c.select_scope())
    assert [row[1] for row in scope] == ["a", "b", "c"]
    assert scope[1][3:] == ("Phan Thiết", 22)  # điểm đến và hotel_id lấy từ DB
    assert c.state.db.execute("SELECT COUNT(*) FROM hotels WHERE refresh = 1").fetchone()[0] == 4
    # xuất interim: plan mang via=refresh để chuẩn hoá không cắt theo per_city/điểm đến
    with c.state.db:
        c.state.db.execute("UPDATE hotels SET static_json = '{\"name\": \"B\", \"rooms\": {}}' WHERE slug = 'b'")
    c.export(date(2026, 10, 8))
    record = json.loads((paths.interim / "agoda_api.jsonl").read_text().splitlines()[0])
    assert record["plan"] == {"destination": "Phan Thiết", "via": "refresh"}
    c.state.close()


def test_agoda_state_from_before_refresh_gets_the_column(tmp_path):
    import sqlite3
    paths = Paths(tmp_path).ensure()
    old = sqlite3.connect(paths.state / "agoda_api.sqlite")
    old.execute("CREATE TABLE hotels (url TEXT PRIMARY KEY, slug TEXT NOT NULL, city TEXT NOT NULL, destination TEXT, "
                "rank INTEGER, first_seen TEXT, last_seen TEXT, hotel_id INTEGER, id_status TEXT, static_json TEXT, static_at TEXT)")
    old.commit(); old.close()
    c = AgodaCollector(paths, AgodaOptions(destinations=DEEP))
    assert "refresh" in {row[1] for row in c.state.db.execute("PRAGMA table_info(hotels)")}
    c.state.close()


# ---------------------------------------------------------------------------------------------- Booking


def test_booking_search_url_encodes_spaces_as_percent_20():
    url = BookingHotels(checkin=date(2026, 11, 6)).search_url("Nha Trang", 0)
    assert "ss=Nha%20Trang" in url and "+" not in url
    assert "checkin=2026-11-06" in url


CARD = ('<div data-testid="property-card"><a data-testid="title-link" href="/hotel/vn/{slug}.vi.html">'
        '<div data-testid="title">{slug}</div></a></div>')


def booking_discover(tmp_path, pages, refresh):
    paths = Paths(tmp_path).ensure()
    state = StateDB(paths)
    src = BookingHotels(checkin=date(2026, 11, 6))
    queue = iter(pages)

    async def load(ctx, query, want):
        return next(queue), True

    ctx = SimpleNamespace(paths=paths, state=state, cache=SimpleNamespace(write=lambda *a, **k: None),
                          done=lambda key: False, mark_done=lambda key, found: None,
                          opts=SimpleNamespace(destinations=select_destinations("Nha Trang,Hà Nội"),
                                               budget=DEFAULT_BUDGET, refresh=refresh))
    with patch.object(BookingHotels, "_load_results", lambda self, c, q, w: load(c, q, w)):
        asyncio.run(src.discover_plan(ctx))
    return paths, state


def test_booking_refresh_queued_after_search_and_marked(tmp_path):
    refresh = ({"url": "https://www.booking.com/hotel/vn/old.vi.html", "destination": "Phan Thiết"},
               {"url": "https://www.booking.com/hotel/vn/new1.vi.html", "destination": "Nha Trang"})
    paths, state = booking_discover(tmp_path, [CARD.format(slug="new1"), CARD.format(slug="new2")], refresh)
    pending = state.pending("booking_hotels", 3)
    assert pending == ["https://www.booking.com/hotel/vn/new1.vi.html", "https://www.booking.com/hotel/vn/new2.vi.html",
                       "https://www.booking.com/hotel/vn/old.vi.html"]
    # tìm thấy rồi thì giữ plan của lần tìm (thứ hạng), chỉ khách sạn chỉ có trong DB mang via=refresh
    assert state.plan_of("booking_hotels", pending[0])["via"] == "booking-search"
    assert state.plan_of("booking_hotels", pending[2]) == {"destination": "Phan Thiết", "via": "refresh"}
    priority = state.conn.execute("SELECT priority FROM items WHERE url = ?", (pending[2],)).fetchone()[0]
    assert priority == REFRESH_PRIORITY
    report = json.loads((paths.interim / "booking_hotels.search.json").read_text())
    assert report == {"destinations": {"Nha Trang": 1, "Hà Nội": 1}}
    state.close()


def test_booking_empty_search_is_reported_per_destination(tmp_path):
    empty = "<html><title>Kết quả tìm kiếm: Nha+Trang</title><body>0 chỗ nghỉ</body></html>"
    paths, state = booking_discover(tmp_path, [empty, empty], ())
    assert json.loads((paths.interim / "booking_hotels.search.json").read_text()) == {
        "destinations": {"Nha Trang": 0, "Hà Nội": 0}}
    state.close()


# ---------------------------------------------------------------------------------------------- chuẩn hoá


def hotel(src, dest, rank=None, via=None):
    plan = {"destination": dest, **({"rank": rank} if rank else {}), **({"via": via} if via else {})}
    name = f"{src}-{dest}-{rank}-{via}"
    return nm.make_product(meta={"src": src, "plan": plan}, name=name, taxonomy="hotel", destination=dest,
                           description="x", attributes={"level": "property"}, unitPrice=1, currency="VND",
                           available=True, imageUrl=None, sourceRef=f"{src}:hotel:{name}")


def test_apply_plan_keeps_refreshed_hotels_beyond_cap_and_outside_plan():
    budget = DEFAULT_BUDGET.__class__(booking_hotels=1, agoda_hotels=1)
    products = [hotel("booking", "Nha Trang", 1), hotel("booking", "Nha Trang", 2),
                hotel("booking", "Nha Trang", via="refresh"), hotel("booking", "Phan Thiết", via="refresh"),
                hotel("agoda", "Phan Thiết")]
    dropped = Counter()
    kept = nm.apply_plan(products, {"Nha Trang"}, budget, dropped)
    assert sorted(p["name"] for p in kept) == ["booking-Nha Trang-1-None", "booking-Nha Trang-None-refresh",
                                               "booking-Phan Thiết-None-refresh"]
    assert dropped["booking: vượt 1/điểm đến"] == 1 and dropped["agoda: ngoài 1 điểm đến kế hoạch"] == 1


# ---------------------------------------------------------------------------------------------- nạp DB: tách dòng lỗi


def fresh_row(ref, parent=None, name="KS"):
    attrs = {"level": "room" if parent else "property", **({"parentProductId": parent} if parent else {})}
    return {"productId": product_id(ref), "name": name, "taxonomy": "hotel", "destination": "Nha Trang",
            "description": "x", "attributes": attrs, "unitPrice": 100, "currency": "VND", "available": True,
            "availableFrom": None, "availableTo": None, "imageUrl": None, "sourceRef": ref}


def db_row(pid, ref):
    return {"product_id": pid, "source_ref": ref, "name": "cũ", "taxonomy": "hotel", "destination": "Nha Trang",
            "description": "x", "attributes": {"level": "property"}, "unit_price": 1, "currency": "VND",
            "available": True, "available_from": None, "available_to": None, "image_url": None}


def test_conflicting_row_and_its_new_rooms_are_quarantined_others_load():
    good = fresh_row("booking:hotel:1")
    bad = fresh_row("booking:hotel:2")
    bad_room = fresh_row("booking:hotel:2:room:1", parent=bad["productId"])
    good_room = fresh_row("booking:hotel:1:room:1", parent=good["productId"])
    existing = [db_row(good["productId"], "booking:hotel:1"),
                db_row(bad["productId"], "agoda:hotel:khac:nha-trang")]  # cùng ID, ref khác: trước đây hỏng cả lượt
    with pytest.raises(ValueError, match="ID conflict"):
        prepare_rows([good, bad, bad_room, good_room], existing, set(), "2026-10-08")
    quarantine = []
    rows, counts = prepare_rows([good, bad, bad_room, good_room], existing, set(), "2026-10-08", quarantine=quarantine)
    assert [q["sourceRef"] for q in quarantine] == ["booking:hotel:2"]  # phòng cha có trong DB: phòng vẫn nạp
    assert {r["source_ref"] for r in rows} == {"booking:hotel:1", "booking:hotel:2:room:1", "booking:hotel:1:room:1"}
    assert counts["quarantined"] == 1 and counts["refreshed"] == 1 and counts["new"] == 2


def test_two_fresh_rows_claiming_one_db_row_keep_the_first_and_its_rooms():
    """Booking và Agoda của cùng khách sạn chưa được chuẩn hoá gộp, nhưng dòng DB đã ghi ref Agoda vào sameAs: cả hai ghép vào
    một dòng DB → trùng sourceRef chuẩn. Dòng sau bị tách ra; phòng của nó vẫn nạp dưới dòng DB."""
    booking = fresh_row("booking:hotel:9")
    agoda = fresh_row("agoda:hotel:z:nha-trang")
    agoda_room = fresh_row("agoda:hotel:z:nha-trang:room:1", parent=agoda["productId"])
    kept = db_row(booking["productId"], "booking:hotel:9")
    kept["attributes"]["sameAs"] = ["agoda:hotel:z:nha-trang"]
    with pytest.raises(ValueError, match="canonical"):
        prepare_rows([booking, agoda, agoda_room], [kept], set(), "2026-10-08")
    quarantine = []
    rows, counts = prepare_rows([booking, agoda, agoda_room], [kept], set(), "2026-10-08", quarantine=quarantine)
    assert [q["sourceRef"] for q in quarantine] == ["agoda:hotel:z:nha-trang"]
    assert "trùng sourceRef chuẩn" in quarantine[0]["reason"]
    room = next(r for r in rows if r["source_ref"].endswith(":room:1"))
    assert room["attributes"]["parentProductId"] == kept["product_id"]
    assert counts["quarantined"] == 1


# ---------------------------------------------------------------------------------------------- độ phủ làm mới


def write_jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r) + "\n" for r in rows))


def test_refresh_coverage_flags_sources_below_minimum_and_empty_search(tmp_path):
    write_jsonl(tmp_path / "refresh" / "booking-hotels.jsonl", [{"url": f"b{i}"} for i in range(10)])
    write_jsonl(tmp_path / "interim" / "booking_hotels.jsonl", [{"url": f"b{i}"} for i in range(8)] + [{"url": "new"}])
    write_jsonl(tmp_path / "refresh" / "agoda-hotels.jsonl", [{"url": "a1"}, {"url": "a2"}])
    write_jsonl(tmp_path / "interim" / "agoda_api.jsonl", [{"url": "a1"}, {"url": "a2"}])
    (tmp_path / "interim" / "booking_hotels.search.json").write_text(json.dumps({"destinations": {"Nha Trang": 0, "Huế": 0}}))
    targets = [{"trip_hotel_id": "1"}, {"trip_hotel_id": "2", "refresh": True}, {"trip_hotel_id": "3", "refresh": True}]
    report, problems = job.refresh_coverage(tmp_path, targets, [{"hotelId": 2}, {"hotelId": 1}], 90)
    assert report["booking-hotels"] == {"requested": 10, "refreshed": 8, "percent": 80.0}
    assert report["agoda-hotels"]["percent"] == 100.0
    assert report["trip-hotels.prices"] == {"requested": 2, "refreshed": 1, "percent": 50.0}
    assert set(problems) == {"booking-hotels", "trip-hotels.prices", "booking-hotels.search"}
    assert "0 khách sạn ở cả 2 điểm đến" in problems["booking-hotels.search"]
    assert job.refresh_coverage(tmp_path, targets, [{"hotelId": 2}], 0)[1] == {
        "booking-hotels.search": problems["booking-hotels.search"]}  # 0 = tắt ngưỡng %, tìm 0 vẫn báo


def test_refresh_problems_make_run_partial_and_raise_alert(tmp_path):
    rec = SimpleNamespace(data={"steps": [], "counts": {"refreshProblems": {"booking-hotels": "làm mới 1/10"}}})
    assert job.incomplete_sources(rec, tmp_path) == {"booking-hotels": "làm mới 1/10"}
    data = {"id": "full-x", "status": "partial", "steps": [],
            "counts": {"refreshProblems": {"booking-hotels.search": "tìm 0"}, "database": {"quarantined": 2}}}
    out = alerts.run_alerts(data, tmp_path)
    assert [(a["level"], a["kind"], a["step"]) for a in out] == [("error", "coverage", "booking-hotels"),
                                                                  ("warning", "record", "db")]


def test_source_command_passes_the_runs_refresh_list(tmp_path):
    values = {f.key: f.default for f in fresh_settings.FIELDS}
    assert "--refresh-list" not in job.source_command(tmp_path, "booking-hotels", "@deep", values)
    write_jsonl(tmp_path / "refresh" / "booking-hotels.jsonl", [{"url": "u"}])
    write_jsonl(tmp_path / "refresh" / "agoda-hotels.jsonl", [{"url": "u"}])
    for source in ("booking-hotels", "agoda-hotels"):
        command = job.source_command(tmp_path, source, "@deep", values)
        assert command[command.index("--refresh-list") + 1] == str(tmp_path / "refresh" / f"{source}.jsonl")
    assert "--refresh-list" not in job.source_command(tmp_path, "trip-flights", "@deep", values)


def test_refresh_lists_come_from_maintenance_and_survive_its_failure(tmp_path):
    assert job.write_refresh_lists(tmp_path, {}) == {}  # bảo trì lỗi: không danh sách, lượt vẫn chạy
    assert not (tmp_path / "refresh").exists()
    targets = {"booking": [{"url": "b1"}, {"url": "b2"}], "agoda": []}
    assert job.write_refresh_lists(tmp_path, targets) == {"booking-hotels": 2, "agoda-hotels": 0}
    assert (tmp_path / "refresh" / "booking-hotels.jsonl").read_text().count("\n") == 2
    seen = {}

    def maintain(url, **kw):
        kw["refresh_out"].update(targets)
        return {}
    rec = SimpleNamespace(set_counts=lambda **k: None, stop_event=SimpleNamespace(is_set=lambda: True))
    values = {f.key: f.default for f in fresh_settings.FIELDS}
    with patch.object(job, "maintain_catalog", maintain), \
            patch.object(job, "crawl_and_load", lambda *a, **kw: seen.update(kw) or 0):
        assert job.execute("full", rec, values, tmp_path, tmp_path, "postgresql://x", None) == 0
    assert seen["refresh"] == targets


def test_booking_runs_last_so_it_cannot_starve_agoda():
    assert [name for name, _ in job.SITE_GROUPS] == ["trip", "vinpearl", "agoda", "booking"]


# ---------------------------------------------------------------------------------------------- supervisor


WORKER = '''
import json,os,subprocess,sys,time
from pathlib import Path
state,runs,mode=Path(sys.argv[1]),Path(sys.argv[2]),sys.argv[3]
child=subprocess.Popen([sys.executable,'-c','import time; time.sleep(120)'])
(state/'child').write_text(str(child.pid))
run=runs/'full-test';run.mkdir()
step={'name':'booking-hotels','status':'running','startedAt':'2026-01-01T00:00:00+00:00','detail':{'pid':child.pid}}
data={'id':'full-test','status':'running','steps':[step]}
(run/'run.json').write_text(json.dumps(data))
(state/'running.json').write_text(json.dumps({'pid':os.getpid(),'runId':'full-test'}))
if mode=='oom':
    os.kill(os.getpid(),9)
child.wait()
if mode=='recover':  # như crawl_sites: nguồn chết thì ghi bước quá giờ rồi chạy tiếp nguồn sau
    step.update(status='timeout');(run/'run.json').write_text(json.dumps(data))
    (state/'after').write_text('next source ran')
    sys.exit(0)
time.sleep(120)
'''


def supervised(tmp_path, mode, **kw):
    state, runs = tmp_path / 'state', tmp_path / 'runs'
    state.mkdir(); runs.mkdir()
    killed = []
    code = pipeline_runtime.supervise([sys.executable, '-c', WORKER, str(state), str(runs), mode], state, runs,
                                      max_seconds=60, step_seconds={'booking-hotels': 1}, poll=.05,
                                      on_killed=lambda run_id, stopped: killed.append((run_id, stopped)), **kw)
    from fresh_run_log import _alive
    return code, killed, state, _alive(int((state / 'child').read_text()))


def test_overdue_source_is_killed_alone_and_the_run_continues(tmp_path):
    code, killed, state, child_alive = supervised(tmp_path, 'recover')
    assert code == 0 and killed == [] and not child_alive
    assert (state / 'after').read_text() == 'next source ran'


def test_run_is_killed_only_when_the_source_stays_running_past_grace(tmp_path):
    with patch.object(pipeline_runtime, 'SOURCE_KILL_GRACE', 0.3):
        started = time.monotonic()
        code, killed, state, child_alive = supervised(tmp_path, 'hang')
    assert code == 3 and killed == [('full-test', False)] and not child_alive
    assert time.monotonic() - started < 10
    data = json.loads((tmp_path / 'runs' / 'full-test' / 'run.json').read_text())
    assert data['status'] == 'failed'


def test_worker_killed_by_signal_reports_for_auto_resume(tmp_path):
    code, killed, state, _ = supervised(tmp_path, 'oom')
    assert code == -signal.SIGKILL and killed == [('full-test', False)]
    with contextlib.suppress(ProcessLookupError):  # con mồ côi của worker bị giết (máy tải nặng: có thể đã tự thoát)
        os.kill(int((state / 'child').read_text()), signal.SIGKILL)


# ---------------------------------------------------------------------------------------------- tự chạy tiếp


def run_main(tmp_path, monkeypatch, first, argv=('full',), settings=None):
    monkeypatch.setenv('CATALOG_STATE_DIR', str(tmp_path / 'state'))
    monkeypatch.setenv('CATALOG_RUN_ROOT', str(tmp_path / 'runs'))
    (tmp_path / 'state').mkdir(exist_ok=True)
    if settings:
        fresh_settings.save(tmp_path / 'state', settings)
    calls = []

    def fake(command, state, runs, **kw):
        calls.append(command)
        if len(calls) == 1:
            return first(kw.get('on_killed'))
        return 0
    with patch.object(pipeline_runtime, 'supervise', fake):
        code = job.main(list(argv))
    return code, calls


def test_killed_full_run_resumes_once_from_normalise(tmp_path, monkeypatch):
    def killed(on_killed):
        on_killed('full-20261008T150000Z-7', False)
        return 3
    code, calls = run_main(tmp_path, monkeypatch, killed, argv=('full', '--trigger', 'schedule'))
    assert code == 0 and len(calls) == 2
    assert calls[1][2:] == ['resume', 'full-20261008T150000Z-7', '--from', 'normalise', '--trigger', 'schedule', '--worker']


@pytest.mark.parametrize('case', ['stopped', 'daily', 'disabled', 'clean'])
def test_no_auto_resume_for_stop_daily_disabled_or_clean_exit(tmp_path, monkeypatch, case):
    def first(on_killed):
        if case != 'clean':
            on_killed('daily-20261008T150000Z-7' if case == 'daily' else 'full-20261008T150000Z-7', case == 'stopped')
        return 0 if case == 'clean' else 3
    code, calls = run_main(tmp_path, monkeypatch, first,
                           settings={'run.autoResume': False} if case == 'disabled' else None)
    assert len(calls) == 1 and code == (0 if case == 'clean' else 3)


def test_resume_seals_half_written_interim_before_normalise(tmp_path):
    (tmp_path / 'interim').mkdir()
    (tmp_path / 'interim' / 'booking_hotels.jsonl').write_text('{"url": "a"}\n{"url": "b", "na')
    (tmp_path / 'interim' / 'vinpearl.jsonl.tmp').write_text('{"k": 1}\n')
    rec = SimpleNamespace(data={'id': 'full-x', 'mode': 'full', 'steps': [], 'counts': {}, 'startedAt': 'x'},
                          stop_event=SimpleNamespace(is_set=lambda: True), save=lambda: None)
    seen = {}

    def normalise_step(run_dir, destinations, merge_only=False):
        seen['booking'] = (run_dir / 'interim' / 'booking_hotels.jsonl').read_text()
        seen['vinpearl'] = (run_dir / 'interim' / 'vinpearl.jsonl').is_file()
        raise RuntimeError('stop here')
    values = {f.key: f.default for f in fresh_settings.FIELDS}
    with patch.object(job, 'normalise_step', normalise_step), pytest.raises(RuntimeError, match='stop here'):
        job.resume_run(rec, values, tmp_path, tmp_path, 'normalise', 'postgresql://x', None)
    assert seen == {'booking': '{"url": "a"}\n', 'vinpearl': True}


# ---------------------------------------------------------------------------------------------- Trip: lượt full hỏi mọi ID


def test_full_run_prices_every_known_trip_id_oldest_first(tmp_path):
    state = tmp_path / 'state'
    state.mkdir()
    (state / 'trip_targets.json').write_text(json.dumps({'hotels': [
        {'trip_hotel_id': '1', 'city_id': '1777', 'destination': 'Nha Trang'},
        {'trip_hotel_id': '2', 'city_id': '1777', 'destination': 'Nha Trang'},
        {'trip_hotel_id': '9', 'city_id': '1777', 'destination': 'Nha Trang'}]}))
    (state / 'trip_schedule.json').write_text(json.dumps({'version': 1, 'hotels': {
        '1': {'lastAttemptAt': '2026-10-07T00:00:00+00:00'}, '2': {'lastAttemptAt': '2026-09-29T00:00:00+00:00'}}}))
    run_dir = tmp_path / 'run'
    run_dir.mkdir()
    priced = {}

    async def discover(paths, cities, scan, new, known):
        return [{'trip_hotel_id': '9', 'city_id': '1777', 'destination': 'Nha Trang'},
                {'trip_hotel_id': '50', 'city_id': '1777', 'destination': 'Nha Trang'}], []

    def crawl_sites(run_dir, destinations, groups, parallel, previewer=None, deadline=None):
        for name, steps in groups:
            for item in steps:
                if callable(item) and getattr(item, '__name__', '') == 'find_hotels':
                    item()
                elif callable(item):
                    priced['targets'] = [dict(t) for t in TARGETS()]
                    raise RuntimeError('stop after selecting targets')
        return {}
    values = {f.key: f.default for f in fresh_settings.FIELDS}
    values.update({'sources.booking': False, 'sources.agoda': False, 'sources.vinpearl': False,
                   'sources.tripFlights': False, 'sources.tripAttractions': False, 'normalise.preview': False})
    holder = {}
    TARGETS = lambda: json.loads((run_dir / job.RUN_TARGETS).read_text())['hotels']  # noqa: E731
    rec = SimpleNamespace(data={'startedAt': 'x', 'counts': {}}, set_counts=lambda **k: holder.update(k),
                          check_stop=lambda: None, save=lambda: None)
    with patch.object(job, 'discover', discover), patch.object(job, 'crawl_sites', crawl_sites), \
            pytest.raises(RuntimeError, match='stop after'):
        job.crawl_and_load('full', rec, values, state, run_dir, 'postgresql://x')
    ids = [(t['trip_hotel_id'], bool(t.get('refresh'))) for t in priced['targets']]
    # mới tìm trước (kể cả ID đã biết tìm lại được), rồi ID đã biết: chưa thử → thử lâu nhất → mới thử
    assert ids == [('9', False), ('50', False), ('2', True), ('1', True)]
