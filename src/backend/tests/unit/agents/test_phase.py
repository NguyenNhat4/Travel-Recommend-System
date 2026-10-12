"""Cờ hội thoại (`steps/phase.py`, `steps/consent.py`): hội thoại đã lưu theo dạng cũ vẫn khôi phục đúng."""
import asyncio
import unittest

from src.backend.app.agents.nodes import intake_node_async
from src.backend.app.agents.steps import consent, phase
from src.backend.app.domain.itinerary.planning import empty_intent
from src.backend.app.infrastructure.persistence.conversation_store import InMemoryConversationStore


def restore(record: dict) -> dict:
    store = InMemoryConversationStore()
    asyncio.run(store.save("c1", {"intent": empty_intent(), **record}))
    return asyncio.run(intake_node_async({"query": "ok", "conversation_id": "c1"}, store=store))


class RestoredPhaseTests(unittest.TestCase):
    def test_a_record_saved_before_the_exploration_phase_gets_every_flag_with_its_default(self):
        update = restore({})
        for key, default in phase.CARRIED.items():
            self.assertEqual(update[key], default, key)

    def test_a_record_with_a_plan_or_asked_details_counts_as_consented(self):
        self.assertTrue(restore({"previous_plan": {"days": []}})["plan_consent"])
        self.assertTrue(restore({"start_date_asked": True})["plan_consent"])
        self.assertFalse(restore({"start_date_asked": True, "plan_consent": False})["plan_consent"])

    def test_saved_flags_come_back_and_turn_flags_start_fresh(self):
        update = restore({"plan_consent": True, "pending_fare": {"origin": "Hà Nội"}, "rejected_destinations": ["Huế"]})
        self.assertEqual(update["pending_fare"], {"origin": "Hà Nội"})
        self.assertEqual(update["rejected_destinations"], ["Huế"])
        self.assertEqual({key: update[key] for key in phase.TURN_ONLY}, phase.TURN_ONLY)

    def test_restored_consent_reads_only_the_saved_record(self):
        self.assertFalse(consent.restored({}))
        self.assertTrue(consent.restored({"plan_consent": True}))


class SettledTests(unittest.TestCase):
    def test_a_pending_fare_question_is_dropped_when_the_turn_is_not_about_fares(self):
        state = {"pending_fare": {"origin": "Hà Nội"}}
        self.assertIsNone(phase.settled(state, {"decision": "explore"})["pending_fare"])
        self.assertNotIn("pending_fare", phase.settled(state, {"decision": "explore", "fare_question": True}))


if __name__ == "__main__":
    unittest.main()
