"""Mã nguyên nhân khi lượt dừng sớm (`steps/limits.py`) và cách snapshot từ chối lượt không phát lại được.

Plan `docs/plan/2026-10-12-go-luong-cu-orchestrator-chinh.md`, D2: trước đây "execution budget exhausted" gộp trần vòng,
trần tool và hết giờ; "model unavailable" gộp quá hạn và lỗi. Mỗi nguyên nhân một ca; câu chữ của event không đổi.
"""
import asyncio
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from src.backend.app.agents import clock, nodes
from src.backend.app.agents.models import OrchestratorTurn
from src.backend.app.agents.steps import jobs, limits, orchestration
from src.backend.app.application.ports.itinerary_tools import ToolError
from .behavior_snapshot import harness, record
from .test_orchestrator_jobs import Tools, initial, product

T0 = 1_000_000.0


class Clock:
    """Đồng hồ giả tiến theo bước, thay cho `clock.now`."""

    def __init__(self, now=T0):
        self.value = now

    def __call__(self):
        return self.value


class SlowModel:
    def __init__(self, delay=0.0, error=None):
        self.delay, self.error = delay, error

    def with_structured_output(self, schema):
        async def ainvoke(prompt):
            await asyncio.sleep(self.delay)
            if self.error:
                raise self.error
            return schema.model_validate({"action": "answer", "message": "Xin chào."})
        return SimpleNamespace(ainvoke=ainvoke)


def reason_of(update):
    return update["events"][0]["metadata"].get("reason")


class LimitReasonTests(unittest.TestCase):
    def test_order_follows_the_original_condition_round_then_tool_then_time(self):
        with patch.object(clock, "now", Clock(T0 + 99)):
            state = {"started_at": T0, "turn_rounds": 3, "turn_tool_calls": 10}
            self.assertEqual(orchestration.limit_reason(state, 10), limits.ROUND_LIMIT)
            self.assertEqual(orchestration.limit_reason({**state, "turn_rounds": 1}, 10), limits.TOOL_LIMIT)
            self.assertEqual(orchestration.limit_reason({**state, "turn_rounds": 1, "turn_tool_calls": 2}, 10),
                             limits.TIME_LIMIT)
            self.assertIsNone(orchestration.limit_reason({**state, "turn_rounds": 1, "turn_tool_calls": 2}, 100))

    def test_model_failure_separates_timeout_from_other_errors(self):
        self.assertEqual(limits.model_failure(TimeoutError()), limits.MODEL_TIMEOUT)
        self.assertEqual(limits.model_failure(RuntimeError("provider 500")), limits.MODEL_ERROR)


class RunJobsReasonTests(unittest.IsolatedAsyncioTestCase):
    async def run_jobs(self, now, **state):
        with patch.object(clock, "now", Clock(now)):
            return await orchestration.run_jobs_node(
                initial(started_at=T0, orchestrator_turn={"action": "execute", "jobs": []}, **state),
                tools=Tools([]), budget_seconds=10)

    async def test_round_cap(self):
        update = await self.run_jobs(T0, turn_rounds=3)
        self.assertEqual(update["events"][0]["message"], "execution budget exhausted")
        self.assertEqual(reason_of(update), limits.ROUND_LIMIT)
        self.assertEqual(update["turn_limit_reason"], limits.ROUND_LIMIT)

    async def test_tool_cap(self):
        update = await self.run_jobs(T0, turn_tool_calls=10)
        self.assertEqual(update["events"][0]["message"], "execution budget exhausted")
        self.assertEqual(reason_of(update), limits.TOOL_LIMIT)

    async def test_time_budget(self):
        update = await self.run_jobs(T0 + 11)
        self.assertEqual(update["events"][0]["message"], "execution budget exhausted")
        self.assertEqual(reason_of(update), limits.TIME_LIMIT)

    async def test_round_cap_reached_by_this_round_is_recorded(self):
        specs = [{"kind": "explore", "intent": "new", "destination": "Hà Nội", "taxonomy": "hotel"}]
        with patch.object(clock, "now", Clock(T0)):
            update = await orchestration.run_jobs_node(
                initial(started_at=T0, turn_rounds=2, orchestrator_turn={"action": "execute", "jobs": specs}),
                tools=Tools([product("a")]), budget_seconds=10)
        self.assertEqual(update["events"][0]["message"], "jobs executed")
        self.assertTrue(update["force_answer"])
        self.assertEqual(update["turn_limit_reason"], limits.ROUND_LIMIT)


class OrchestrateReasonTests(unittest.IsolatedAsyncioTestCase):
    async def orchestrate(self, model, now=T0, timeout=10):
        with patch.object(clock, "now", Clock(now)):
            return await orchestration.orchestrate_node(initial(started_at=T0), llm=model, tools=Tools([]),
                                                        timeout_seconds=timeout, budget_seconds=10)

    async def test_budget_spent_before_the_model_call(self):
        update = await self.orchestrate(SlowModel(), now=T0 + 10)
        self.assertEqual(update["events"][0]["message"], "time budget exhausted, fallback")
        self.assertEqual(reason_of(update), limits.TIME_LIMIT)
        self.assertEqual(update["turn_limit_reason"], limits.TIME_LIMIT)

    async def test_slow_model_is_a_model_timeout(self):
        update = await self.orchestrate(SlowModel(delay=1), timeout=0.01)
        self.assertEqual(update["events"][0]["message"], "model unavailable, fallback")
        self.assertEqual(reason_of(update), limits.MODEL_TIMEOUT)

    async def test_model_exception_is_a_model_error(self):
        update = await self.orchestrate(SlowModel(error=RuntimeError("provider 500")))
        self.assertEqual(update["events"][0]["message"], "model unavailable, fallback")
        self.assertEqual(reason_of(update), limits.MODEL_ERROR)

    async def test_answer_within_budget_has_no_reason(self):
        update = await self.orchestrate(SlowModel())
        self.assertNotIn("turn_limit_reason", update)
        self.assertTrue(OrchestratorTurn.model_validate(update["orchestrator_turn"] | {"jobs": []}))


class BudgetToolsReasonTests(unittest.IsolatedAsyncioTestCase):
    async def test_tool_cap(self):
        counter = jobs.BudgetTools(Tools([product("a")]), jobs.MAX_TOOL_CALLS, T0 + 10, 1)
        with patch.object(clock, "now", Clock(T0)):
            with self.assertRaises(ToolError) as caught:
                await counter.get_product_detail("a")
        self.assertEqual((caught.exception.code, caught.exception.reason), ("JOB_BUDGET_EXHAUSTED", limits.TOOL_LIMIT))

    async def test_deadline(self):
        counter = jobs.BudgetTools(Tools([product("a")]), 0, T0 + 10, 1)
        with patch.object(clock, "now", Clock(T0 + 10)):
            with self.assertRaises(ToolError) as caught:
                await counter.get_product_detail("a")
        self.assertEqual((caught.exception.code, caught.exception.reason), ("JOB_BUDGET_EXHAUSTED", limits.TIME_LIMIT))

    async def test_slow_tool_keeps_timeout_error_and_marks_the_job(self):
        class SlowTools(Tools):
            async def execute(self, call):
                await asyncio.sleep(1)

        with patch.object(clock, "now", Clock(T0)):
            counter = jobs.BudgetTools(SlowTools([]), 0, T0 + 10, 0.01)
            with self.assertRaises(TimeoutError) as caught:
                await counter.execute({"id": "x", "name": "search_products", "args": {}})
            self.assertEqual(caught.exception.reason, limits.TOOL_TIMEOUT)
            spec = {"kind": "explore", "intent": "new", "destination": "Hà Nội", "taxonomy": "hotel"}
            row = await jobs._one(initial(), spec, 1, jobs.BudgetTools(SlowTools([]), 0, T0 + 10, 0.01), [])
        # Mã lỗi giữ như cũ; nguyên nhân nằm riêng.
        self.assertEqual((row["status"], row["error"], row["reason"]), ("failed", "JOB_FAILED", limits.TOOL_TIMEOUT))


class LlmFailedReasonTests(unittest.TestCase):
    def test_reason_comes_from_the_exception_being_handled(self):
        state = {"request_id": "r1", "language": "vi"}
        try:
            raise TimeoutError()
        except TimeoutError:
            update = nodes._llm_failed(state, "extract", "async", 2)
        self.assertEqual(update["events"][0]["message"], "LLM_UNAVAILABLE")
        self.assertEqual(reason_of(update), limits.MODEL_TIMEOUT)
        try:
            raise ValueError("schema")
        except ValueError:
            update = nodes._llm_failed(state, "extract", "async", 2)
        self.assertEqual(reason_of(update), limits.MODEL_ERROR)


class SnapshotRejectionTests(unittest.TestCase):
    @staticmethod
    def events(*reasons):
        return [{"node": "run_jobs", "message": "x", "metadata": {"reason": reason}} for reason in reasons]

    def test_only_time_and_provider_dependent_reasons_are_rejected(self):
        for reason in (limits.TIME_LIMIT, limits.MODEL_TIMEOUT, limits.MODEL_ERROR, limits.TOOL_TIMEOUT):
            self.assertEqual(harness.unreplayable(self.events(reason), []), [reason])
        self.assertEqual(harness.unreplayable(self.events(limits.ROUND_LIMIT, limits.TOOL_LIMIT, None), []), [])

    def test_a_failed_live_call_rejects_the_turn(self):
        self.assertEqual(harness.unreplayable([], [limits.TOOL_TIMEOUT]), [limits.TOOL_TIMEOUT])

    def test_recorder_lists_rejected_scenarios_with_reasons(self):
        result = {"ok": [{"response": {}}], "bad": [{}, {"unreplayable": ["MODEL_TIMEOUT"]}]}
        self.assertEqual(record.rejected(result), {"bad": ["MODEL_TIMEOUT"]})


class CassetteModelKeyTests(unittest.IsolatedAsyncioTestCase):
    async def test_orchestrator_model_has_its_own_key_and_shared_model_keeps_the_old_key(self):
        prompt = [("system", "s"), ("human", "h")]
        shared_key = harness._prompt_key("structured:OrchestratorTurn", None, prompt)
        records = {shared_key: {"action": "answer", "message": "chung"}}
        harness._CALLS.set([])
        shared = await harness.CassetteLlm(records).with_structured_output(OrchestratorTurn).ainvoke(prompt)
        self.assertEqual(shared.message, "chung")
        with self.assertRaises(harness.CassetteMiss):
            await harness.CassetteLlm(records, model="orchestrator").with_structured_output(
                OrchestratorTurn).ainvoke(prompt)

    async def test_live_timeout_while_recording_is_noted(self):
        class Live:
            def with_structured_output(self, schema):
                async def ainvoke(prompt):
                    await asyncio.sleep(1)
                return SimpleNamespace(ainvoke=ainvoke)

        harness._CALLS.set([])
        harness._FAILURES.set([])
        llm = harness.CassetteLlm({}, inner=Live())
        with self.assertRaises(TimeoutError):
            await asyncio.wait_for(llm.with_structured_output(OrchestratorTurn).ainvoke([("human", "x")]), 0.01)
        self.assertEqual(harness._FAILURES.get(), [limits.MODEL_TIMEOUT])


class FrozenClockTests(unittest.TestCase):
    def test_snapshot_clock_stands_still(self):
        with harness.frozen_world():
            first = clock.now()
            second = clock.now()
        self.assertEqual(first, second)
        self.assertEqual(first, harness.FROZEN_NOW.timestamp())


if __name__ == "__main__":
    unittest.main()
