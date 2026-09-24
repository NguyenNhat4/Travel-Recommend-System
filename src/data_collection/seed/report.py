"""Human-readable seed report and README marker updater."""
from __future__ import annotations

import hashlib
from datetime import date
from pathlib import Path

import psycopg

START = "<!-- seed-report:start -->"
END = "<!-- seed-report:end -->"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def collect(vota_url: str, insider_url: str) -> dict[str, int]:
    with psycopg.connect(vota_url) as conn:
        products, profiles, events, combos, search_units = conn.execute("""
            SELECT (SELECT count(*) FROM cdp.products),
                   (SELECT count(*) FROM cdp.profiles),
                   (SELECT count(*) FROM cdp.events),
                   (SELECT count(*) FROM catalog.combo_items),
                   (SELECT count(*) FROM catalog.product_meta WHERE is_search_unit)
        """).fetchone()
    with psycopg.connect(insider_url) as conn:
        insider_profiles, insider_events, channel_events = conn.execute("""
            SELECT (SELECT count(*) FROM insider_profiles),
                   (SELECT count(*) FROM insider_events),
                   (SELECT count(*) FROM channel_events)
        """).fetchone()
    return {
        "products": products, "profiles": profiles, "events": events, "combo_items": combos,
        "search_units": search_units, "insider_profiles": insider_profiles,
        "insider_events": insider_events, "channel_events": channel_events,
    }


def render(products_path: Path, as_of: date, seed: int, counts: dict[str, int]) -> str:
    repo_root = Path(__file__).resolve().parents[3]
    try:
        source = products_path.resolve().relative_to(repo_root).as_posix()
    except ValueError:
        source = str(products_path)
    return "\n".join([
        START,
        f"### Snapshot seed gần nhất — `{as_of.isoformat()}`",
        "",
        f"- Nguồn catalog: `{source}` — SHA-256 `{sha256(products_path)}`.",
        f"- Seed `{seed}`: {counts['products']:,} products · {counts['profiles']:,} profiles · {counts['events']:,} events · {counts['combo_items']:,} combo items.",
        f"- Search units: {counts['search_units']:,}; vector nằm ngoài PostgreSQL và được index sang Weaviate bằng `make index-vectors`.",
        f"- Insider clone: {counts['insider_profiles']:,} profiles · {counts['insider_events']:,} events · {counts['channel_events']:,} channel events.",
        "- Purchase thiếu `event_group_id` là edge case được sinh có chủ đích khoảng 3%; không xoá purchase.",
        END,
    ])


def update_readme(readme: Path, block: str) -> None:
    text = readme.read_text(encoding="utf-8")
    if START in text and END in text:
        before, rest = text.split(START, 1)
        _, after = rest.split(END, 1)
        updated = before.rstrip() + "\n\n" + block + after
    else:
        updated = text.rstrip() + "\n\n" + block + "\n"
    readme.write_text(updated, encoding="utf-8")
