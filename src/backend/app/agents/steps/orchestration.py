"""Orchestrator nodes, with bounded repair and execution. Runtime clients never enter state."""
from __future__ import annotations

import asyncio
from copy import deepcopy
from time import time

from src.backend.app.domain.itinerary import gatekeeper
from src.backend.app.domain.itinerary.normalization import fold

from ..models import FareQuestion, Job, OrchestratorTurn
from . import consent, exploration, fares, jobs, shown, tool_planning
from .classification import vietnam_today
from .history import llm_context, prompt_yaml
from .messages import chat_model, event, message, titled
from .prompts import ORCHESTRATOR_PROMPT

MAX_ROUNDS = 3


def payload(state: dict) -> list:
    context = llm_context(state)
    memory = shown.current(state)
    context["previous_selection"] = [{"ref": shown.ref_of(memory, item.get("productId")),
                                      "name": item.get("name"), "taxonomy": item.get("taxonomy")}
                                     for item in state.get("previous_selection") or []]
    constraints = deepcopy(context.get("known_constraints") or {})
    excluded = constraints.pop("exclude_products", []) or []
    if excluded:
        constraints["exclude_refs"] = [ref for product_id in excluded if (ref := shown.ref_of(memory, product_id))]
    context["known_constraints"] = constraints
    # Raw canonical product links from the last answer must not expose IDs to the orchestrator either.
    data = {"message": state.get("query", ""), **context, "language": state.get("language", "vi"),
            "catalog_destinations": state.get("supported_destinations") or [],
            "plan_consent": bool(state.get("plan_consent")), "pending_offer": state.get("pending_offer"),
            "rejected_destinations": state.get("rejected_destinations") or [],
            "rejected_refs": state.get("rejected_refs") or [], "open_question": state.get("open_question"),
            "dont_know_level": state.get("dont_know_count", 0),
            "previous_suggestions": state.get("last_suggestions") or [], "today": vietnam_today().isoformat(),
            "results": state.get("turn_results") or [], "pending": state.get("turn_pending") or [],
            "waiting_jobs": state.get("waiting_jobs") or [], "force_answer": bool(state.get("force_answer")),
            "unfinished": state.get("turn_unfinished") or [], "violations": state.get("turn_violations") or []}
    # fare_block is code text, supplied with product:# IDs internally; convert only its model-facing copy to #n.
    encoded = prompt_yaml(data)
    mapping = {**{item["productId"]: item["ref"] for item in shown.current(state)["items"]},
               **{pid: ref for ref, pid in (state.get("turn_codes") or {}).items()}}
    for product_id, ref in sorted(mapping.items(), key=lambda item: -len(item[0])):
        encoded = encoded.replace(f"product:{product_id}", ref)
    return [("system", ORCHESTRATOR_PROMPT), ("human", encoded)]


def _fallback(state: dict) -> dict:
    registry = gatekeeper.visible(state.get("turn_jobs") or [], state.get("turn_codes") or {})
    return {"action": "answer", "message": "", "cards": list(registry), "suggestions": [], "fallback": True}


def _stage(state: dict, result: OrchestratorTurn) -> dict:
    turn = result.model_dump(mode="json")
    declined = bool(state.get("turn_declines_offer") or turn["declines_offer"])
    stop = bool(state.get("turn_stop") or turn["stop"])
    rejected = list(state.get("rejected_destinations") or [])
    rejected_refs = list(state.get("rejected_refs") or [])
    names = state.get("supported_destinations") or []
    for value in turn["rejected"]:
        if value in shown.by_ref(shown.current(state)):
            rejected_refs.append(value)
        else:
            place = fares._place(value, names)
            if place:
                rejected.append(place)
    # An explicit new job asking again for a rejected place/ref restores exactly that scope.
    for spec in turn["jobs"]:
        if spec["intent"] == "new":
            rejected = [value for value in rejected if fold(value) != fold(spec.get("destination")) or
                        any(fold(value) == fold(new) for new in turn["rejected"])]
            rejected_refs = [ref for ref in rejected_refs if ref not in spec.get("refers_to", []) or ref in turn["rejected"]]
    update = {"orchestrator_turn": turn, "turn_declines_offer": declined, "turn_stop": stop,
              "rejected_destinations": list(dict.fromkeys(rejected)), "rejected_refs": list(dict.fromkeys(rejected_refs)),
              "events": [event("orchestrate", f"action {turn['action']}", jobs=len(turn["jobs"]))]}
    if declined or stop:
        update["pending_offer"] = None
    if stop:
        turn.update(action="answer", cards=[], jobs=[], suggestions=[], question=None, offer=None, title=None)
        turn["message"] = turn.get("message") or message(state, "farewell")
        return {**update, "decision": "gatekeep", "waiting_jobs": []}
    if turn["action"] == "execute":
        if not turn["jobs"] or state.get("force_answer"):
            return {**update, "orchestrator_turn": _fallback(state), "decision": "gatekeep"}
        return {**update, "turn_pending": turn["pending"], "decision": "run_jobs"}
    if turn["action"] == "plan":
        if not state.get("force_answer") and consent.structured_plan_allowed({**state, **update}, turn["plan_reason"]):
            reason = turn["plan_reason"]
            plan_update = {} if reason == "trip_details" and not state.get("plan_consent") else consent.newly_consented(state)
            return {**update, **plan_update, "decision": "extract", "interaction_type": "travel",
                    "form_request": reason == "form", "turn_plan_reason": reason,
                    "turn_plan_accepted": reason != "trip_details" or bool(state.get("plan_consent")),
                    "other_questions": turn["suggestions"][:3], "waiting_jobs": []}
        return {**update, **plan_denied({**state, **update})}
    if not turn.get("message") and not state.get("turn_jobs"):
        return {**update, "orchestrator_turn": _fallback(state), "decision": "gatekeep"}
    return {**update, "decision": "gatekeep"}


def plan_denied(state: dict) -> dict:
    destination = (state.get("pending_offer") or {}).get("destination") or (state.get("intent") or {}).get("destination")
    turn = {"action": "ask" if not destination else "answer", "message": ("Bạn muốn khám phá điểm đến nào?" if state.get("language") != "en" else "Which destination would you like to explore?")
            if not destination else ("Bạn có thể bấm nút lập lịch khi muốn bắt đầu." if state.get("language") != "en"
                                    else "Choose the plan button when you are ready."),
            "cards": [], "suggestions": [], "question": {"about": "destination"} if not destination else None,
            "offer": {"destination": destination, "text": message(state, "explore_offer", destination=destination)}
            if destination else None}
    return {"orchestrator_turn": turn, "decision": "gatekeep", "missing_fields": [], "clarification_reason": None}


async def orchestrate_node(state: dict, *, llm=None, tools=None, timeout_seconds: float = 10,
                           tool_timeout_seconds: float = 1, budget_seconds: float = 10) -> dict:
    update = {}
    if state.get("supported_destinations") is None and not state.get("turn_stop"):
        budget = jobs.BudgetTools(tools, state.get("turn_tool_calls", 0),
                                  state.get("started_at", time()) + budget_seconds, tool_timeout_seconds)
        names = await tool_planning.catalog_destinations(budget, tool_timeout_seconds)
        update = {"supported_destinations": names, "turn_tool_calls": budget.count}
        state = {**state, **update}
    if state.get("turn_rounds", 0) >= MAX_ROUNDS or state.get("turn_tool_calls", 0) >= jobs.MAX_TOOL_CALLS \
            or time() - state.get("started_at", time()) >= budget_seconds:
        state = {**state, "force_answer": True,
                 "turn_unfinished": state.get("turn_unfinished") or state.get("turn_pending") or []}
        update.update(force_answer=True, turn_unfinished=state["turn_unfinished"])
    remaining = budget_seconds - (time() - state.get("started_at", time()))
    # Do not exceed the request deadline just to ask the model for a forced answer.
    if remaining <= 0:
        return {**update, "orchestrator_turn": _fallback(state), "decision": "gatekeep",
                "events": [event("orchestrate", "time budget exhausted, fallback")]}
    try:
        result = await asyncio.wait_for(chat_model(llm).with_structured_output(OrchestratorTurn).ainvoke(payload(state)),
                                        min(timeout_seconds, remaining))
        return {**update, **_stage(state, OrchestratorTurn.model_validate(result))}
    except Exception:
        return {**update, "orchestrator_turn": _fallback(state), "decision": "gatekeep",
                "events": [event("orchestrate", "model unavailable, fallback")]}


async def run_jobs_node(state: dict, *, tools=None, tool_timeout_seconds: float = 1,
                        budget_seconds: float = 10) -> dict:
    turn = state.get("orchestrator_turn") or {}
    specs = turn.get("jobs") or []
    rounds = state.get("turn_rounds", 0)
    if rounds >= MAX_ROUNDS or state.get("turn_tool_calls", 0) >= jobs.MAX_TOOL_CALLS \
            or time() - state.get("started_at", time()) >= budget_seconds:
        return {"force_answer": True, "decision": "gatekeep" if state.get("button_jobs") else "orchestrate",
                "orchestrator_turn": _fallback(state) if state.get("button_jobs") else turn,
                "turn_unfinished": [*specs, *(state.get("turn_pending") or []), *(state.get("button_pending_jobs") or [])],
                "events": [event("run_jobs", "execution budget exhausted")]}
    update = await jobs.execute(state, specs, tools=tools, timeout_seconds=tool_timeout_seconds,
                                budget_seconds=budget_seconds)
    rounds += 1
    new = update["turn_jobs"][len(state.get("turn_jobs") or []):]
    if turn.get("repair_only"):
        for row in new:
            row["answer_only"] = True
    unavailable = [row for row in new if row.get("status") == "failed"]
    force = bool(state.get("force_answer")) or not update["jobs_progress"] or rounds >= MAX_ROUNDS or update["turn_tool_calls"] >= jobs.MAX_TOOL_CALLS
    shortcut = rounds == 1 and len(specs) == 1 and specs[0]["kind"] == "fare" and turn.get("fare_only") \
        and not turn.get("pending") and len(new) == 1 and new[0]["status"] in ("answered", "asked", "unavailable")
    action = {"action": "answer", "message": f"[[fare_block:{new[0]['job']}]]", "cards": [], "suggestions": []} \
        if shortcut else ({"action": "answer", "message": "\n\n".join(f"[[fare_block:{row['job']}]]" for row in new), "cards": [], "suggestions": []} if state.get("button_jobs") else turn)
    # Gatekeeper rechecks references at finalize; active code fare links may exceed the four visible day cards.
    update.update(turn_rounds=rounds, force_answer=force, orchestrator_turn=action,
                  decision="gatekeep" if shortcut or state.get("button_jobs") else "orchestrate",
                  turn_unfinished=[*turn.get("pending", []), *(row["spec"] for row in unavailable)] if force or unavailable else [],
                  events=[event("run_jobs", "fare shortcut" if shortcut else "jobs executed", rounds=rounds,
                                tool_calls=update["turn_tool_calls"], failed=len(unavailable))])
    remaining = state.get("button_pending_jobs") or []
    if state.get("button_jobs") and remaining:
        if force:
            update["turn_unfinished"].extend(remaining)
        else:
            update.update(decision="run_jobs", button_pending_jobs=remaining[3:],
                          orchestrator_turn={"action": "execute", "jobs": remaining[:3], "pending": [], "fare_only": False})
    # Keep the state of the last code-written fare result visible to dependent explore jobs.
    fare_rows = [row for row in new if row["kind"] == "fare" and row.get("status") != "superseded"]
    if fare_rows:
        update["pending_fare"] = fare_rows[-1].get("pending_fare")
        if fare_rows[-1].get("intent_update"):
            update["intent"] = fare_rows[-1]["intent_update"]
    elif not state.get("plan_consent"):
        destination = next((row["spec"].get("destination") for row in new if row["spec"].get("destination")), None)
        if destination:
            update["intent"] = {**state.get("intent", {}), "destination": destination}
    return update


def _offer(state: dict, turn: dict, render: dict) -> tuple[str | None, str | None]:
    offer = turn.get("offer") or {}
    destination = fares._place(offer.get("destination"), state.get("supported_destinations") or [])
    if destination is None:
        destination = fares._place((state.get("intent") or {}).get("destination"), state.get("supported_destinations") or [])
    allowed = destination and not state.get("plan_consent") and destination not in (state.get("rejected_destinations") or []) \
        and destination not in (state.get("offered_destinations") or []) \
        and not state.get("turn_declines_offer") and not state.get("turn_stop") \
        and not render["fare_question"] and not turn.get("question")
    return destination, str(offer.get("text") or "") if allowed and "?" in str(offer.get("text") or "") else None


def gatekeep_node(state: dict, *, budget_seconds: float = 10) -> dict:
    turn = deepcopy(state.get("orchestrator_turn") or _fallback(state))
    rows, codes = state.get("turn_jobs") or [], state.get("turn_codes") or {}
    problems = gatekeeper.inspect(turn, rows, codes, state.get("language", "vi"))
    can_repair = state.get("gate_repairs", 0) < 1 and state.get("turn_rounds", 0) < MAX_ROUNDS \
        and state.get("turn_tool_calls", 0) < jobs.MAX_TOOL_CALLS \
        and time() - state.get("started_at", time()) < budget_seconds
    if problems["violations"] and can_repair and not turn.get("fallback"):
        references = [ref for ref in problems["unknown_refs"] if ref in shown.by_ref(shown.current(state))]
        repair = {"gate_repairs": 1, "turn_violations": problems["violations"], "force_answer": True,
                  "decision": "orchestrate", "events": [event("gatekeep", "answer needs repair", issues=problems["violations"])]}
        if references:
            repair.update(orchestrator_turn={"action": "execute", "jobs": [Job(kind="explore", intent="about_shown",
                                                                                 refers_to=references).model_dump(mode="json")]},
                          decision="run_jobs")
            repair["orchestrator_turn"]["repair_only"] = any(row.get("kind") == "explore" and
                                                             row.get("intent") in ("more", "cheaper", "dearer") for row in rows)
        return repair
    fallback = bool(problems["violations"] or turn.get("fallback"))
    if fallback:
        turn.update(title=None, message="", question=None, offer=None)
    explore_rows = [row for row in rows if row["kind"] == "explore"]
    hotel_only = bool(explore_rows) and all(row.get("spec", {}).get("taxonomy") == "hotel" or
                                           row.get("intent") == "about_shown" and bool(row.get("products")) and
                                           all(product.get("taxonomy") == "hotel" for product in row["products"])
                                           for row in explore_rows)
    rendered = gatekeeper.render(turn, rows, codes, seen=shown.current(state), language=state.get("language", "vi"),
                                 rejected_refs=state.get("rejected_refs") or [],
                                 rejected_destinations=state.get("rejected_destinations") or [], hotel_only=hotel_only, fallback=fallback)
    body = exploration.once_praise(rendered["body"])
    destination, offer_text = _offer(state, turn, rendered)
    if offer_text:
        body += "\n\n" + offer_text
    unfinished = state.get("turn_unfinished") or []
    suggestions = list(rendered["suggestions"])
    if unfinished:
        body += "\n\n" + ("Mình chưa hoàn tất phần yêu cầu còn lại trong lượt này; bạn có thể hỏi tiếp." if state.get("language") != "en"
                              else "Some requested work is unfinished this turn; you can ask me to continue.")
        suggestions.insert(0, "Tiếp tục phần chưa trả lời" if state.get("language") != "en" else "Continue unfinished work")
    chip = message(state, "chip_plan", destination=destination) if destination else None
    # Fare reply buttons retain their exact text and precedence (they bypass the LLM next turn).
    checked = exploration.checked_suggestions(suggestions, state.get("last_suggestions") or [], [],
                                             destinations=state.get("supported_destinations") or [], plan_chip=chip,
                                             avoid=state.get("rejected_destinations") or [])
    if rendered["fare_question"]:
        priority = (rendered["suggestions"] or [])[:3]
        checked = list(dict.fromkeys([*priority, *checked]))[:3]
    if state.get("turn_stop"):
        body = turn.get("message") or message(state, "farewell")
        checked = []
        rendered["searchResults"] = {}
    response = {"status": "NEEDS_CLARIFICATION", "conversationId": state["conversation_id"],
                "question": titled((turn.get("title") or "").replace("?", "") or None, gatekeeper._one_question(body))}
    if checked:
        response["suggestions"] = checked
    if rendered["searchResults"]:
        response["searchResults"] = rendered["searchResults"]
    if not state.get("turn_stop"):
        response["knownIntent"] = state.get("intent")
    prefill = rendered["prefill"]
    prefill["title"] = turn.get("title")
    prefill["offer"] = {"text": offer_text} if offer_text else None
    return {"response": response, "decision": "finalize", "orchestrator_prefill": prefill,
            "orchestrator_fare_ids": rendered["fare_ids"], "waiting_jobs": rendered["waiting_jobs"],
            "pending_fare": rendered["pending_fare"] if any(row["kind"] == "fare" for row in rows) else state.get("pending_fare"),
            **consent.structured_offer_update(state, destination=destination, inserted=bool(offer_text)),
            "events": [event("gatekeep", "fallback grounded" if fallback else "answer grounded",
                             issues=problems["violations"], dropped=rendered["dropped"])]}


def fare_button_turn(state: dict, picked: dict) -> dict:
    """Replay every waiting fare job lacking the field supplied by this code-created button."""
    ask = FareQuestion.model_validate(picked.get("fare_ask") or {}).model_dump(mode="json")
    specs = [Job(kind="fare", fare=FareQuestion.model_validate(ask)).model_dump(mode="json")]
    pending = state.get("pending_fare") or {}
    field = "kind_unclear" if pending.get("kind_asked") else "origin" if pending.get("destination") else "destination"
    for spec in state.get("waiting_jobs") or []:
        old = FareQuestion.model_validate(spec.get("fare") or {}).model_dump(mode="json")
        missing = old.get(field) if field == "kind_unclear" else not old.get(field)
        if missing:
            old[field] = ask[field]
        specs.append({**spec, "fare": old})
    return {**picked, "decision": "run_jobs", "orchestrator_turn": {"action": "execute", "jobs": specs[:3],
                                                                  "pending": [], "fare_only": len(specs) == 1},
            "button_jobs": True, "button_pending_jobs": specs[3:], "waiting_jobs": []}
