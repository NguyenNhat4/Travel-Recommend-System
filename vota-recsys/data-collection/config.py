"""Load, validate and query config.yaml.

Precedence (spec sections 8 and 11 together):

* Environment variables override config.yaml **except** ``rate_limit_rps`` and
  ``concurrency``. Spec section 8 makes config.yaml the authority for the
  politeness ceiling, so an env var may only *lower* those, never raise them.
  Without that asymmetry a stray ``RATE_LIMIT_RPS=5`` in a shell profile would
  quietly breach the rule the spec is most insistent about.
* ``config.yaml`` supplies everything else.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

from ids import lookup_key

log = logging.getLogger("config")

HERE = Path(__file__).resolve().parent
DEFAULT_CONFIG_PATH = HERE / "config.yaml"

# Reserved `crawl_runs.source` values for commands that are not a crawl.
# Enumerated here, in one place, because `report` and the preflight both need to
# know them: preflight must not try to resolve them through the collector
# registry, and crawl statistics must not count them as sources.
SENTINEL_SOURCES = frozenset(
    {"__normalise__", "__dedup__", "__load__", "__manual_review__", "__seed__"}
)

TAXONOMIES = ("hotel", "flight", "combo", "attraction", "golf")


class ConfigError(Exception):
    """config.yaml is missing something, or says something impossible."""


# =============================================================================
# source view
# =============================================================================
@dataclass(frozen=True)
class SourceConfig:
    name: str
    raw: dict[str, Any]
    user_agent: str
    rate_limit_rps: float
    concurrency: int

    @property
    def enabled(self) -> bool:
        return bool(self.raw.get("enabled", False))

    @property
    def parser_version(self) -> str:
        return str(self.raw["parser_version"])

    @property
    def source_priority(self) -> int:
        return int(self.raw.get("source_priority", 0))

    @property
    def respect_robots(self) -> bool:
        return bool(self.raw.get("respect_robots", True))

    @property
    def base_url(self) -> str:
        return str(self.raw.get("base_url", ""))

    @property
    def hosts(self) -> tuple[str, ...]:
        return tuple(self.raw.get("hosts", ()))

    @property
    def description_policy(self) -> str:
        return str(self.raw.get("description_policy", "keep"))

    def get(self, key: str, default: Any = None) -> Any:
        return self.raw.get(key, default)


@dataclass
class Destination:
    name: str
    aliases: tuple[str, ...]
    iata: tuple[str, ...]
    lat: float | None
    lon: float | None


# =============================================================================
# config
# =============================================================================
@dataclass
class Config:
    raw: dict[str, Any]
    path: Path
    sha256: str
    _dest_index: dict[str, str] = field(default_factory=dict, repr=False)
    _destinations: dict[str, Destination] = field(default_factory=dict, repr=False)

    # -- generic access ----------------------------------------------------
    def __getitem__(self, key: str) -> Any:
        return self.raw[key]

    def get(self, key: str, default: Any = None) -> Any:
        return self.raw.get(key, default)

    def section(self, key: str) -> dict[str, Any]:
        value = self.raw.get(key) or {}
        if not isinstance(value, dict):
            raise ConfigError(f"config section {key!r} must be a mapping")
        return value

    # -- sources -----------------------------------------------------------
    def source(self, name: str) -> SourceConfig:
        sources = self.section("sources")
        if name not in sources:
            known = ", ".join(sorted(sources))
            raise ConfigError(f"unknown source {name!r}. Known sources: {known}")
        raw = sources[name] or {}
        rl = self.section("ratelimit")
        rps_cap = float(rl.get("max_rps_cap", 0.5))
        conc_cap = int(rl.get("max_concurrency_cap", 2))

        rps = float(raw.get("rate_limit_rps", rl.get("default_rps", 0.5)))
        conc = int(raw.get("concurrency", 1))

        # Env may only lower these two (see module docstring).
        env_rps = _env_float("RATE_LIMIT_RPS")
        if env_rps is not None:
            rps = min(rps, env_rps)
        env_conc = _env_int("MAX_CONCURRENCY")
        if env_conc is not None:
            conc = min(conc, env_conc)

        return SourceConfig(
            name=name,
            raw=raw,
            user_agent=self.user_agent,
            rate_limit_rps=min(rps, rps_cap),
            concurrency=max(1, min(conc, conc_cap)),
        )

    def source_names(self) -> list[str]:
        return sorted(self.section("sources"))

    def enabled_sources(self) -> list[str]:
        return [n for n in self.source_names() if self.source(n).enabled]

    def source_priority_map(self) -> dict[str, int]:
        return {n: self.source(n).source_priority for n in self.source_names()}

    # -- http --------------------------------------------------------------
    @property
    def user_agent(self) -> str:
        ua = os.environ.get("USER_AGENT") or self.section("http").get("user_agent", "")
        ua = ua.strip()
        if not ua:
            raise ConfigError(
                "USER_AGENT is empty. Spec section 11 requires an honest identity with a "
                "contact email; set it in .env or config.yaml http.user_agent."
            )
        if "mozilla" in ua.lower():
            # Not a style preference: a browser UA on a crawler is anti-bot
            # evasion, which spec section 1 forbids outright.
            raise ConfigError(
                f"USER_AGENT must not impersonate a browser (got {ua!r}). "
                "Spec section 1: do not circumvent anti-bot measures."
            )
        return ua

    def assert_contactable_user_agent(self) -> None:
        """Refuse to send requests with a placeholder contact address.

        Called by the network commands only, so offline work and the test suite
        still run against the config default.

        Spec section 11 asks for a User-Agent that states who we are and how to
        reach us. A UA carrying ``you@example.com`` satisfies the letter of that
        (there is an address) and none of its purpose: the operator of a site we
        are crawling has no way to tell us to stop. The check exists because the
        failure is silent — if ``.env`` is missing or in an unexpected place, the
        placeholder from config.yaml is used and nothing looks wrong.
        """
        ua = self.user_agent
        lowered = ua.lower()
        if any(p in lowered for p in PLACEHOLDER_CONTACTS):
            where = env_file_used()
            raise ConfigError(
                f"USER_AGENT still has a placeholder contact address: {ua!r}\n"
                "Spec section 11 requires a real identity and a working contact "
                "address, because it is how a site operator asks us to stop.\n"
                f"  .env loaded from: {where or 'NOT FOUND'}\n"
                f"  searched: {', '.join(str(p) for p in ENV_SEARCH_PATHS)}\n"
                "Set USER_AGENT in .env to something like:\n"
                "  USER_AGENT=VOTA-RecSys-Internship/0.1 (+mailto:your.real@email)"
            )

    @property
    def database_url(self) -> str:
        url = os.environ.get("DATABASE_URL", "").strip()
        if not url:
            user = os.environ.get("POSTGRES_USER", "vota")
            pwd = os.environ.get("POSTGRES_PASSWORD", "")
            host = os.environ.get("POSTGRES_HOST", "localhost")
            port = os.environ.get("POSTGRES_PORT", "5432")
            db = os.environ.get("POSTGRES_DB", "vota")
            if not pwd:
                searched = ", ".join(str(x) for x in ENV_SEARCH_PATHS)
                raise ConfigError(
                    "No DATABASE_URL and no POSTGRES_PASSWORD.\n"
                    f"  .env loaded from: {env_file_used() or 'NOT FOUND'}\n"
                    f"  searched: {searched}\n"
                    "Copy .env.example to .env in any of those locations and fill it in."
                )
            url = f"postgresql+psycopg://{user}:{pwd}@{host}:{port}/{db}"
        if url.startswith("postgresql://"):
            # A bare postgresql:// URL makes SQLAlchemy look for psycopg2, which
            # is not a dependency of this project.
            url = url.replace("postgresql://", "postgresql+psycopg://", 1)
        return url

    # -- paths -------------------------------------------------------------
    @property
    def data_root(self) -> Path:
        return HERE / self.section("paths").get("data_root", "data")

    @property
    def reports_dir(self) -> Path:
        return HERE / self.section("paths").get("reports_dir", "data/reports")

    @property
    def manual_dir(self) -> Path:
        return HERE / self.section("paths").get("manual_dir", "data/manual")

    # -- quote contexts (spec section 5.5) ---------------------------------
    @property
    def anchor_date(self) -> dt.date | None:
        v = self.section("quote_contexts").get("anchor_date")
        if v in (None, ""):
            return None
        if isinstance(v, dt.date):
            return v
        return dt.date.fromisoformat(str(v))

    def require_anchor_date(self) -> dt.date:
        """Called by `discover` before it writes any target.

        Deriving check-in from ``today + 30`` would give a Monday discover and a
        Wednesday discover different ``quote_ctx`` values. Since
        ``crawl_targets`` is UNIQUE on ``(source, url_hash, quote_ctx)``, every
        target would be re-inserted as pending and the whole crawl would repeat
        at 0.5 rps — and prices from sources crawled on different days would no
        longer be comparable, which is the entire purpose of section 5.5.
        """
        d = self.anchor_date
        if d is None:
            raise ConfigError(
                "quote_contexts.anchor_date is null. Pin it (e.g. "
                f"{date_hint()}) and commit config.yaml before the first discover, "
                "otherwise every discover run invents a new quote_ctx and re-crawls "
                "everything."
            )
        return d

    def enabled_quote_contexts(self) -> list[str]:
        qc = self.section("quote_contexts")
        return list(qc.get("enabled") or ["base"])

    def resolve_quote_context(self, name: str) -> dict[str, Any]:
        """Turn a context name into concrete parameters.

        The value stored in ``crawl_targets.quote_ctx`` is the bare NAME
        (``'base'``), matching the section 4.1 comment. The resolved parameters
        go into ``raw_pages.meta`` and ``crawl_runs.stats``, so the dates are
        recoverable for README section 12 item 4 without encoding them into a
        composite key that would break the uniqueness constraint.
        """
        qc = self.section("quote_contexts")
        contexts = qc.get("contexts") or {}
        if name not in contexts:
            raise ConfigError(f"unknown quote context {name!r}")
        spec = contexts[name]
        anchor = self.require_anchor_date()
        checkin = anchor + dt.timedelta(days=int(spec["checkin_offset_days"]))
        nights = int(spec.get("nights", 1))
        return {
            "name": name,
            "anchor_date": anchor.isoformat(),
            "checkin": checkin.isoformat(),
            "checkout": (checkin + dt.timedelta(days=nights)).isoformat(),
            "nights": nights,
            "adults": int(spec.get("adults", 2)),
            "rooms": int(spec.get("rooms", 1)),
        }

    # -- destinations (spec section 6.1) -----------------------------------
    @property
    def destinations(self) -> dict[str, Destination]:
        return self._destinations

    @property
    def canonical_destination_names(self) -> list[str]:
        return list(self._destinations)

    @property
    def destination_index(self) -> dict[str, str]:
        """``lookup_key(alias) -> canonical name``.

        Built once at load time. The matching itself lives in
        ``normalise.map_destination`` so there is exactly one implementation of
        the section 6.1 rule; this is only the data it matches against.
        """
        return self._dest_index

    def canonical_destination(self, *fields: str | None) -> tuple[str, str]:
        """Convenience wrapper over ``normalise.map_destination``."""
        from normalise import map_destination  # local import: avoids a cycle

        return map_destination(list(fields), self)

    def iata_to_destination(self) -> dict[str, str]:
        out: dict[str, str] = {}
        for d in self._destinations.values():
            for code in d.iata:
                out[code.upper()] = d.name
        return out

    # -- fx (spec sections 6.2, 12 item 3) ---------------------------------
    def fx_provenance(self) -> dict[str, Any]:
        fx = self.section("fx_rates")
        return {
            "as_of": str(fx.get("as_of", "")),
            "source": str(fx.get("source", "")),
            "base": str(fx.get("base", "VND")),
            "rates": dict(fx.get("rates") or {}),
        }


def date_hint() -> str:  # pragma: no cover - message text only
    return dt.date.today().isoformat()


# =============================================================================
# loading + validation
# =============================================================================
#: Where ``.env`` may live, nearest first. Searched rather than fixed because
#: the file legitimately sits at a couple of different levels depending on how
#: someone has arranged the checkout, and a hard-coded path fails in the worst
#: possible way: ``USER_AGENT`` silently falls back to the placeholder in
#: config.yaml, so the crawler goes out with a fake contact address (spec
#: section 11 requires a real one) and every DB command fails separately.
ENV_SEARCH_PATHS: tuple[Path, ...] = (
    HERE / ".env",           # data-collection/.env
    HERE.parent / ".env",    # vota-recsys/.env
    HERE.parent.parent / ".env",  # repository root
)

#: Contact addresses that mean "nobody filled this in".
PLACEHOLDER_CONTACTS = ("you@example.com", "@example.com", "example.org", "changeme")

_env_file_used: Path | None = None


def load_env_file() -> Path | None:
    """Load the first ``.env`` found in :data:`ENV_SEARCH_PATHS`.

    ``override=False`` throughout, so a variable already exported in the shell
    keeps precedence over the file.
    """
    global _env_file_used
    for candidate in ENV_SEARCH_PATHS:
        if candidate.exists():
            load_dotenv(candidate, override=False)
            _env_file_used = candidate
            log.debug("loaded environment from %s", candidate)
            return candidate
    log.warning(
        "no .env found; looked in %s. DATABASE_URL and USER_AGENT will fall back to "
        "defaults, and the defaults are not usable for a real run.",
        ", ".join(str(p) for p in ENV_SEARCH_PATHS),
    )
    return None


def env_file_used() -> Path | None:
    return _env_file_used


_loaded: Config | None = None


def load_config(path: str | Path | None = None, *, reload: bool = False) -> Config:
    global _loaded
    if _loaded is not None and not reload and path is None:
        return _loaded

    load_env_file()

    p = Path(path) if path else DEFAULT_CONFIG_PATH
    if not p.exists():
        raise ConfigError(f"config not found: {p}")
    text = p.read_text(encoding="utf-8")
    raw = yaml.safe_load(text)
    if not isinstance(raw, dict):
        raise ConfigError(f"{p} did not parse to a mapping")

    cfg = Config(raw=raw, path=p, sha256=hashlib.sha256(text.encode("utf-8")).hexdigest())
    _build_destination_index(cfg)
    validate(cfg)
    if path is None:
        _loaded = cfg
    return cfg


def _build_destination_index(cfg: Config) -> None:
    dests = cfg.section("destinations")
    canonical = dests.get("canonical") or []
    if not canonical:
        raise ConfigError("destinations.canonical is empty")

    ambiguous = {lookup_key(a) for a in (dests.get("ambiguous_aliases") or [])}
    index: dict[str, str] = {}
    objects: dict[str, Destination] = {}

    for entry in canonical:
        name = str(entry["name"])
        centroid = entry.get("centroid") or {}
        aliases = tuple(str(a) for a in (entry.get("aliases") or []))
        iata = tuple(str(c).upper() for c in (entry.get("iata") or []))
        objects[name] = Destination(
            name=name,
            aliases=aliases,
            iata=iata,
            lat=_as_float(centroid.get("lat")),
            lon=_as_float(centroid.get("lon")),
        )
        for alias in (name, *aliases, *iata):
            key = lookup_key(alias)
            if not key or key in ambiguous:
                continue
            existing = index.get(key)
            if existing and existing != name:
                # Two canonical destinations claiming one alias makes the
                # mapping order-dependent, which is exactly the kind of silent
                # wrongness that puts products in the wrong city.
                raise ConfigError(
                    f"alias {alias!r} is claimed by both {existing!r} and {name!r}. "
                    "Remove it from one of them or add it to "
                    "destinations.ambiguous_aliases."
                )
            index[key] = name

    cfg._dest_index = index
    cfg._destinations = objects


def validate(cfg: Config) -> None:
    """Fail loudly at startup rather than subtly at 0.5 rps."""
    problems: list[str] = []

    rl = cfg.section("ratelimit")
    rps_cap = float(rl.get("max_rps_cap", 0.5))
    conc_cap = int(rl.get("max_concurrency_cap", 2))
    if rps_cap > 0.5:
        problems.append(
            f"ratelimit.max_rps_cap is {rps_cap}, but spec section 8 caps it at 0.5 "
            "rps/domain with no exemption (API sources included)."
        )
    if conc_cap > 2:
        problems.append(
            f"ratelimit.max_concurrency_cap is {conc_cap}, but spec section 8 caps "
            "concurrency at 2."
        )

    sources = cfg.section("sources")
    if not sources:
        problems.append("sources is empty")
    semver = re.compile(r"^[a-z0-9_]+-\d+\.\d+\.\d+$")
    for name, raw in sources.items():
        raw = raw or {}
        pv = str(raw.get("parser_version", ""))
        if not semver.match(pv):
            # normalize has to order staging rows by parser_version to pick the
            # current payload; mixing a date form like "vinpearl-2026.09.1" into
            # a tuple comparison mis-sorts (2026 > 1) or throws.
            problems.append(
                f"sources.{name}.parser_version must be '<source>-<major>.<minor>.<patch>' "
                f"(got {pv!r})"
            )
        declared_rps = raw.get("rate_limit_rps")
        if declared_rps is not None and float(declared_rps) > rps_cap:
            problems.append(
                f"sources.{name}.rate_limit_rps={declared_rps} exceeds "
                f"ratelimit.max_rps_cap={rps_cap}"
            )
        policy = str(raw.get("robots_policy", "robots_txt"))
        if policy not in ("robots_txt", "api_terms"):
            problems.append(
                f"sources.{name}.robots_policy must be 'robots_txt' or 'api_terms', "
                f"got {policy!r}"
            )
        if policy == "api_terms" and not str(raw.get("usage_policy_url", "")).strip():
            # The exception has to point at the policy it is claiming to follow,
            # or it is just respect_robots: false with extra steps.
            problems.append(
                f"sources.{name}.robots_policy is 'api_terms' but usage_policy_url is "
                "empty. Name the published usage policy being followed, and record the "
                "decision in docs/decisions/."
            )

        base_url = str(raw.get("base_url", ""))
        hosts = [h.lower() for h in (raw.get("hosts") or [])]
        if base_url and hosts:
            from urllib.parse import urlsplit

            host = urlsplit(base_url).netloc.lower()
            if host and host not in hosts:
                # If the limiter keys on `hosts` but traffic goes elsewhere, the
                # token bucket protects a host we never call and the real one is
                # effectively unlimited.
                problems.append(
                    f"sources.{name}: base_url host {host!r} is not listed in hosts "
                    f"{hosts!r}; the rate limiter would key on the wrong host."
                )

    for tax in cfg.section("dod").get("required_taxonomies", TAXONOMIES):
        if tax not in TAXONOMIES:
            problems.append(f"dod.required_taxonomies contains unknown taxonomy {tax!r}")

    q = cfg.section("quality")
    weights = q.get("weights") or {}
    total = sum(float(v) for v in weights.values())
    if weights and abs(total - 1.0) > 1e-6:
        problems.append(f"quality.weights must sum to 1.0 (got {total:.4f})")

    dest_count = len(cfg.destinations)
    dod = cfg.section("dod")
    if dest_count < int(dod.get("destinations_min", 10)):
        problems.append(
            f"destinations.canonical has {dest_count} entries but dod.destinations_min "
            f"is {dod.get('destinations_min')}"
        )

    merge = cfg.section("merge")
    known = set(sources)
    for key in ("content_order", "ota_order"):
        for s in merge.get(key) or []:
            if s not in known:
                problems.append(f"merge.{key} references unknown source {s!r}")

    if problems:
        raise ConfigError(
            "config.yaml has "
            + f"{len(problems)} problem(s):\n  - "
            + "\n  - ".join(problems)
        )


# =============================================================================
# small helpers
# =============================================================================
def _as_float(v: Any) -> float | None:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _env_float(key: str) -> float | None:
    v = os.environ.get(key, "").strip()
    if not v:
        return None
    try:
        return float(v)
    except ValueError:
        log.warning("ignoring non-numeric %s=%r", key, v)
        return None


def _env_int(key: str) -> int | None:
    f = _env_float(key)
    return int(f) if f is not None else None
