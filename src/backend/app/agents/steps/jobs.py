"""Execute structured, read-only jobs. Full products/cursors stay in code, never in LLM output."""
from __future__ import annotations

import asyncio
from copy import deepcopy
import json
from time import time

from src.backend.app.application.ports.itinerary_tools import ToolError
from src.backend.app.domain.itinerary import exploration as rules
from src.backend.app.domain.itinerary.geo import coords, haversine_km
from src.backend.app.domain.itinerary.normalization import fold

from ..models import FareQuestion, Job
from . import fares, shown
from .classification import vietnam_today

MAX_TOOL_CALLS = 10
PAGE_SIZE = 50
BRIEF_ITEMS = 8
BRIEF_CHARS = 1500
ROUND_CHARS = 3000


class BudgetTools:
    """One shared counter for parallel jobs; reserve before awaiting a call."""
    def __init__(self, tools, count: int, deadline: float, timeout: float):
        self.tools, self.count, self.deadline, self.timeout = tools, count, deadline, timeout
        self.supports_catalog = bool(tools and getattr(tools, "supports_catalog", False))

    async def _call(self, name, *args):
        remaining = self.deadline - time()
        if self.tools is None:
            raise ToolError("CATALOG_NOT_CONFIGURED")
        if self.count >= MAX_TOOL_CALLS or remaining <= 0:
            raise ToolError("JOB_BUDGET_EXHAUSTED")
        self.count += 1
        return await asyncio.wait_for(getattr(self.tools, name)(*args), min(self.timeout, remaining))

    async def execute(self, call):
        return await self._call("execute", call)

    async def list_products(self, params):
        return await self._call("list_products", params)

    async def get_product_detail(self, product_id):
        return await self._call("get_product_detail", product_id)

    async def list_destinations(self):
        return await self._call("list_destinations")


def _scope_items(state: dict, job: dict) -> list[dict]:
    rows = shown.current(state)["items"]
    references = set(job.get("refers_to") or [])
    if references:
        return [row for ref, row in shown.by_ref(shown.current(state)).items() if ref in references]
    rows = [row for row in rows if (not job.get("destination") or fold(row.get("place")) == fold(job["destination"]))
            and (not job.get("taxonomy") or row.get("taxonomy") == job["taxonomy"])
            and row.get("taxonomy") != "flight"]
    latest = max((row["turn"] for row in rows), default=0)
    return [row for row in rows if row["turn"] == latest]


def inherited(state: dict, job: dict) -> dict:
    """Keep scope/query/near/sort from the job which actually produced the referenced cards."""
    if job.get("kind") != "explore" or job.get("intent") not in ("more", "cheaper", "dearer"):
        return deepcopy(job)
    rows = _scope_items(state, job)
    previous = (rows[-1].get("via") or {}) if rows else {}
    result = {**previous, **{key: value for key, value in job.items() if value is not None}}
    # Default relevance does not silently remove a previous ordering.
    if job.get("sort") == "relevance" and previous.get("sort"):
        result["sort"] = previous["sort"]
    for key in ("destination", "taxonomy", "query", "near"):
        result[key] = job.get(key) or previous.get(key)
    if rows:
        result["destination"] = result.get("destination") or rows[-1].get("place")
        result["taxonomy"] = result.get("taxonomy") or rows[-1].get("taxonomy")
    return result


def signature(job: dict, previous: list[dict]) -> str:
    if job.get("continue_from"):
        source = next((row for row in previous if row["job"] == job["continue_from"]), {})
        root = source.get("source_job", source.get("job"))
        source = next((row for row in previous if row["job"] == root), source)
        value = {"continue_from": root, "cursor": source.get("cursor", 0),
                 "offset": source.get("offset", 0), "source_more": source.get("source_more", False)}
    else:
        value = {key: val for key, val in job.items() if key != "replaces"}
    return json.dumps(value, sort_keys=True, ensure_ascii=False)


async def _page(row: dict, tools: BudgetTools) -> dict:
    job, offset = row["spec"], row.get("offset", 0)
    params = {"destination": job.get("destination"), "taxonomy": job.get("taxonomy"),
              "availableOnly": job.get("taxonomy") == "hotel", "limit": PAGE_SIZE, "offset": offset}
    params = {key: value for key, value in params.items() if value is not None}
    if job.get("sort") in ("price_asc", "price_desc"):
        payload = await tools.list_products({**params, "sort": job["sort"]})
    else:
        payload = await tools.execute({"id": f"job-{row['job']}-{offset}", "name": "search_products",
                                      "args": {**params, "query": job.get("query") or "điểm tham quan và khách sạn"}})
        if payload.get("error"):
            raise ToolError(payload["error"]["code"])
        payload = payload.get("data") or {}
    products = [item.get("product", item) for item in payload.get("results", []) if isinstance(item, dict)]
    row["offset"] = offset + len(products)
    row["source_more"] = bool(products) and row["offset"] < int(payload.get("total", len(products)))
    # Request filters are checked again; an upstream fallback must not widen the user's scope.
    products = [product for product in products if product.get("productId")
                and (not job.get("destination") or fold(product.get("destination")) == fold(job["destination"]))
                and (not job.get("taxonomy") or product.get("taxonomy") == job["taxonomy"])
                and product.get("taxonomy") != "flight"
                and (product.get("taxonomy") != "hotel" or product.get("available") is True)]
    if "query_ids" in row:
        products = [product for product in products if product["productId"] in row["query_ids"]]
    if job.get("intent") == "more":
        products = [product for product in products if product["productId"] not in row.get("excluded", [])]
    anchor = row.get("anchor_product")
    if job.get("near"):
        location = row.get("near_product") or anchor
        if not location or coords(location) is None:
            products = []
        elif job.get("taxonomy") == "hotel":
            products = rules.within_km(products, location, 1.5)
        else:
            products = [card["product"] for card in rules.near_cards(products, location, len(products))]
    if job.get("intent") in ("cheaper", "dearer"):
        base = rules.price(anchor or {})
        products = [product for product in products if base is not None and rules.price(product) is not None
                    and product.get("priceUnit") == anchor.get("priceUnit")
                    and product.get("currency") == anchor.get("currency")
                    and (rules.price(product) < base if job["intent"] == "cheaper" else rules.price(product) > base)]
    products = rules.distinct_places(products)
    existing = {product["productId"] for product in row["products"]}
    row["products"].extend(product for product in products if product["productId"] not in existing)
    return row


async def _explore(state: dict, spec: dict, number: int, tools: BudgetTools) -> dict:
    row = {"job": number, "kind": "explore", "intent": spec["intent"], "spec": spec, "status": "ok",
           "products": [], "cursor": 0, "offset": 0, "source_more": False, "listed": [], "anchor": None}
    references = shown.by_ref(shown.current(state))
    if spec["intent"] == "about_shown":
        selected = [references[ref] for ref in spec.get("refers_to") or [] if ref in references]
        for item in selected:
            product = await tools.get_product_detail(item["productId"])
            if product.get("productId") == item["productId"]:
                row["products"].append(product)
        row["allowed_ids"] = [item["productId"] for item in selected]
        row["status"] = "ok" if row["products"] else "empty"
        return row
    names = state.get("supported_destinations") or []
    destination = fares._place(spec.get("destination"), names)
    if spec.get("destination") and destination is None:
        return {**row, "status": "empty", "note": "điểm đến không có trong catalog"}
    spec["destination"] = destination
    if destination in (state.get("rejected_destinations") or []):
        return {**row, "status": "empty", "note": "điểm đến đã bị chê trong hội thoại"}
    if not destination and not spec.get("query") and not spec.get("near"):
        return {**row, "status": "empty", "note": "chưa rõ phạm vi cần tìm"}
    if spec["intent"] == "more":
        memory = shown.current(state)
        all_seen = [{"productId": pid, **item} for pid, item in (memory.get("seen") or {}).items()] or memory["items"]
        row["excluded"] = [item["productId"] for item in all_seen
                           if (not destination or fold(item.get("place")) == fold(destination))
                           and (not spec.get("taxonomy") or item.get("taxonomy") == spec["taxonomy"])]
        row["note"] = f"đã loại {len(row['excluded'])} thẻ đã xem trong cả hội thoại theo điểm đến + loại"
    if spec["intent"] in ("cheaper", "dearer"):
        selected = _scope_items(state, spec)
        fresh = [await tools.get_product_detail(item["productId"]) for item in selected]
        priced = [product for product in fresh if rules.price(product) is not None]
        # Prices with different units cannot be compared.
        if not priced or len({(product.get("priceUnit"), product.get("currency")) for product in priced}) != 1:
            return {**row, "status": "empty", "note": "không có mốc giá cùng đơn vị để so"}
        anchor = (min if spec["intent"] == "cheaper" else max)(priced, key=rules.price)
        row["anchor_product"] = anchor
        row["anchor"] = shown.ref_of(shown.current(state), anchor["productId"])
    if spec.get("near"):
        if spec["near"] in references:
            anchor = await tools.get_product_detail(references[spec["near"]]["productId"])
        else:
            response = await tools.execute({"id": f"anchor-{number}", "name": "search_products",
                                           "args": {"query": spec["near"], "destination": destination,
                                                    "availableOnly": False, "limit": PAGE_SIZE}})
            if response.get("error"):
                raise ToolError(response["error"]["code"])
            products = [(item.get("product", item)) for item in (response.get("data") or {}).get("results", [])]
            matches = rules.closest_matches(products, spec["near"])
            anchor = matches[0] if len(matches) == 1 else rules.named_in(products, spec["near"])
        if not anchor or coords(anchor) is None:
            return {**row, "status": "empty", "note": "không xác định được một mốc có toạ độ"}
        row["near_product"] = anchor
        if "anchor_product" not in row:
            row["anchor_product"] = anchor
            row["anchor"] = spec["near"]
    if spec.get("sort") in ("price_asc", "price_desc") and spec.get("query"):
        # Catalog listing does not understand a semantic query. Intersect with a fresh Search scope first;
        # otherwise 'cheaper pool hotels' would silently become 'all hotels'. Every page uses the shared budget.
        query_ids, offset, total = set(), 0, 1
        while offset < total:
            payload = await tools.execute({"id": f"scope-{number}-{offset}", "name": "search_products",
                                           "args": {"query": spec["query"], "destination": destination,
                                                    "taxonomy": spec.get("taxonomy"), "limit": PAGE_SIZE,
                                                    "offset": offset, "availableOnly": spec.get("taxonomy") == "hotel"}})
            if payload.get("error"):
                raise ToolError(payload["error"]["code"])
            data = payload.get("data") or {}
            batch = [item.get("product", item) for item in data.get("results", [])]
            query_ids.update(product["productId"] for product in batch if product.get("productId"))
            total = int(data.get("total", len(batch)))
            offset += len(batch)
            if not batch:
                break
        row["query_ids"] = sorted(query_ids)
    await _page(row, tools)
    # Skip exhausted/fully seen pages, within the same tool/time budget.
    while not row["products"] and row["source_more"]:
        await _page(row, tools)
    if not row["products"]:
        row["status"] = "empty"
        row["note"] = "đã hết kết quả trong phạm vi này"
    return row


def asked_field(row: dict) -> str | None:
    pending = row.get("pending_fare") or {}
    if row.get("status") != "asked":
        return None
    if pending.get("kind_asked"):
        return "kind_unclear"
    return "origin" if pending.get("destination") else "destination"


def can_replace(old: dict, new: dict) -> bool:
    """Only an explicit update which fills exactly the field previously asked for can supersede it."""
    field = asked_field(old)
    before = FareQuestion.model_validate(old["spec"].get("fare") or {}).model_dump(mode="json")
    after = FareQuestion.model_validate(new["spec"].get("fare") or {}).model_dump(mode="json")
    if field is None or new.get("kind") != "fare":
        return False
    filled = before.get(field) is True and after.get(field) is False if field == "kind_unclear" else \
        not before.get(field) and bool(after.get(field))
    return filled and all(before[key] == after[key] for key in before if key != field)


async def _fare(state: dict, spec: dict, number: int, tools: BudgetTools) -> dict:
    ask = FareQuestion.model_validate(spec.get("fare") or {}).model_dump(mode="json")
    update = await fares.answer({**state, "fare_ask": ask, "other_questions": []}, tools=tools,
                               supported=state.get("supported_destinations"), timeout_seconds=tools.timeout,
                               today=vietnam_today())
    body = (update.get("response") or {}).get("question", "")
    pending = update.get("pending_fare") or {}
    status = "asked" if pending.get("chips") and not pending.get("answered") else "answered"
    from .messages import message
    if message(state, "fare_unavailable") in body:
        status = "unavailable"
    return {"job": number, "kind": "fare", "intent": spec["intent"], "spec": spec, "status": status,
            "fare_block": body, "pending_fare": pending, "intent_update": update.get("intent"),
            "suggestions": (update.get("response") or {}).get("suggestions", []),
            "products": list((update.get("candidates") or {}).values()), "cursor": 0, "listed": [],
            "offset": 0, "source_more": False, "anchor": None}


async def _one(state: dict, spec: dict, number: int, tools: BudgetTools, previous: list[dict]) -> dict:
    try:
        if spec.get("continue_from"):
            old = next((row for row in previous if row["job"] == spec["continue_from"] and row["kind"] == "explore"), None)
            if old is None:
                return {"job": number, "kind": spec["kind"], "intent": spec["intent"], "spec": spec,
                        "status": "failed", "products": [], "listed": [], "note": "con trỏ không có trong lượt"}
            root = old.get("source_job", old["job"])
            source = next(item for item in previous if item["job"] == root)
            row = deepcopy(source)
            row["source_job"] = root
            row["job"] = number
            row["continued_from"] = old["job"]
            row["listed"] = []
            if row["cursor"] >= len(row["products"]) and row["source_more"]:
                await _page(row, tools)
                while row["cursor"] >= len(row["products"]) and row["source_more"]:
                    await _page(row, tools)
            row["status"] = "ok" if row["cursor"] < len(row["products"]) else "empty"
            return row
        return await (_fare(state, spec, number, tools) if spec["kind"] == "fare"
                      else _explore(state, spec, number, tools))
    except Exception as exc:
        # Never propagate upstream text/credentials to state or the model.
        return {"job": number, "kind": spec["kind"], "intent": spec["intent"], "spec": spec,
                "status": "failed", "products": [], "listed": [], "note": "không tra được dữ liệu",
                "error": exc.code if isinstance(exc, ToolError) else "JOB_FAILED"}


def _codes(state: dict, products: list[dict], codes: dict[str, str], seq: int) -> int:
    memory = shown.current(state)
    existing = {**{pid: item["ref"] for pid, item in (memory.get("seen") or {}).items()},
                **{item["productId"]: item["ref"] for item in memory["items"]}}
    allocated = {product_id: ref for ref, product_id in codes.items()}
    for product in products:
        product_id = product["productId"]
        if product_id in allocated:
            continue
        ref = existing.get(product_id)
        if ref is None:
            seq += 1
            ref = f"#{seq}"
        codes[ref] = product_id
        allocated[product_id] = ref
    return seq


def _size(value) -> int:
    return len(json.dumps(value, ensure_ascii=False, separators=(",", ":")))


def _previous_brief(row: dict) -> dict:
    """Keep prior job identities/cursors available while bounding the next model payload."""
    brief = deepcopy(row.get("brief") or {})
    brief["earlier_refs"] = [line.split()[0] for line in brief.get("items") or []]
    brief["items"] = []
    brief["scope"] = str(brief.get("scope") or "")[:120]
    brief["note"] = str(brief.get("note") or "")[:80] or None
    if row.get("kind") == "fare":
        brief["fare_block"] = f"[[fare_block:{row['job']}]]"
    return brief


def _brief(row: dict, codes: dict[str, str], max_chars: int) -> dict:
    refs = {product_id: ref for ref, product_id in codes.items()}
    products = row.get("products") or []
    reasons = {}
    for taxonomy in dict.fromkeys(product["taxonomy"] for product in products):
        pool = [product for product in products if product["taxonomy"] == taxonomy]
        reasons.update({card["product"]["productId"]: card["reasons"] for card in rules.pick_cards(pool, len(pool), taxonomy)})
    if row.get("spec", {}).get("sort") == "price_desc":
        priced = [product for product in products if rules.price(product) is not None]
        if priced:
            reasons.setdefault(max(priced, key=rules.price)["productId"], []).append(rules.DEAREST)
    row["reasons"] = {refs[pid]: labels for pid, labels in reasons.items()}
    cursor = row.get("cursor", 0)
    spec = row.get("spec") or {}
    result = {"job": row["job"], "kind": row["kind"], "intent": row["intent"], "status": row["status"],
              "scope": " · ".join(str(spec[key]) for key in ("destination", "taxonomy", "query") if spec.get(key))[:120],
              "anchor": row.get("anchor"), "items": [], "unlisted": len(products) - cursor,
              "source_more": row.get("source_more", False), "note": str(row.get("note") or "")[:80] or None}
    if row["kind"] == "fare":
        block = row.get("fare_block", "")
        # The full block remains in code. If too long, its insertion token is sufficient for the model.
        result["fare_block"] = block if len(block) < max_chars // 3 else f"[[fare_block:{row['job']}]]"
        result["best_destination"] = (row.get("pending_fare") or {}).get("best")
    if _size(result) > max_chars:
        result["scope"], result["note"] = "", None
    for product in products[cursor:cursor + BRIEF_ITEMS]:
        ref = refs[product["productId"]]
        data = shown.facts(product)
        address = (product.get("attributes") or {}).get("address")
        if address:
            data += f"; địa chỉ: {address}"
        place = f"điểm đến: {product['destination']}; " if not spec.get("destination") and product.get("destination") else ""
        line = f"{ref} {shown._label(product)} — {place}{data}"
        labels = reasons.get(product["productId"], [])
        if labels:
            line += f" [nhãn: {', '.join(labels)}; trong kết quả tìm được của việc này]"
        trial = {**result, "items": [*result["items"], line], "unlisted": len(products) - cursor - 1}
        if _size(trial) > max_chars:
            if not result["items"]:
                line = f"{ref} {shown._label(product)[:60]} — {place}dữ kiện dài, hỏi cụ thể để tra lại"
                trial["items"] = [line]
            if _size(trial) > max_chars or result["items"]:
                break
        result = trial
        row["listed"].append(ref)
        cursor += 1
    row["cursor"] = cursor
    return result


async def execute(state: dict, specs: list[Job | dict], *, tools, timeout_seconds: float,
                  budget_seconds: float) -> dict:
    previous = deepcopy(state.get("turn_jobs") or [])
    counter = BudgetTools(tools, state.get("turn_tool_calls", 0),
                          state.get("started_at", time()) + budget_seconds, timeout_seconds)
    codes = deepcopy(state.get("turn_codes") or {})
    seq = max(state.get("turn_seq", 0), shown.current(state).get("seq", 0))
    seen = set(state.get("turn_signatures") or [])
    specs = [inherited(state, Job.model_validate(spec).model_dump(mode="json")) for spec in specs][:3]
    work = []
    for spec in specs:
        key = signature(spec, previous)
        if key in seen:
            continue
        seen.add(key)
        work.append((spec, len(previous) + len(work) + 1))
    results = await asyncio.gather(*(_one(state, spec, number, counter, previous) for spec, number in work))
    for row in results:
        seq = _codes(state, row.get("products") or [], codes, seq)
    briefs = [_previous_brief(row) for row in previous if "brief" in row]
    available_for_previous = ROUND_CHARS - 360 * len(results) - 10
    if _size(briefs) > available_for_previous:
        for old_brief in briefs:
            old_brief.pop("scope", None)
            old_brief.pop("note", None)
            old_brief.pop("anchor", None)
    if _size(briefs) > available_for_previous:
        for old_brief in briefs:
            old_brief.pop("earlier_refs", None)
    chars = _size(briefs)
    for index, row in enumerate(results):
        reserve = 360 * (len(results) - index - 1)
        brief = _brief(row, codes, min(BRIEF_CHARS, max(240, ROUND_CHARS - chars - reserve - 2)))
        chars += _size(brief) + 1
        row["brief"] = brief
        if row.get("continued_from"):
            root = row["source_job"]
            for parent in previous:
                if parent.get("source_job", parent["job"]) == root:
                    parent.update(cursor=row["cursor"], offset=row["offset"], source_more=row.get("source_more", False),
                                  products=deepcopy(row["products"]))
        if row["kind"] == "fare" and row.get("spec", {}).get("replaces"):
            old = next((item for item in [*previous, *results] if item["job"] == row["spec"]["replaces"]), None)
            if old and old["job"] < row["job"] and can_replace(old, row):
                old["status"] = "superseded"
                old["brief"]["status"] = "superseded"
            else:
                row["replace_rejected"] = True
        briefs.append(brief)
    all_jobs = [*previous, *results]
    candidates = {**(state.get("candidates") or {})}
    for row in results:
        for product in row.get("products") or []:
            candidates[product["productId"]] = product
    return {"turn_jobs": all_jobs, "turn_codes": codes, "turn_seq": seq, "candidates": candidates,
            "sources": {**(state.get("sources") or {}), **{pid: {"source": "SEARCH"} for pid in candidates}},
            "turn_tool_calls": counter.count, "turn_signatures": sorted(seen),
            "jobs_progress": bool(work), "turn_results": briefs}
