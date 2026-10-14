import unittest
from src.backend.app.agents.routing import (route_after_evaluate, route_after_extract, route_after_orchestrate,
                                            route_after_precheck, route_after_retry)


class RoutingTests(unittest.TestCase):
    def test_precheck_branches_and_fail_closed_default(self):
        for decision, node in [('simple', 'converse'), ('travel', 'extract'), ('missing_info', 'clarify'),
                               ('tool', 'tool'), ('orchestrate', 'orchestrate'), ('run_jobs', 'run_jobs'),
                               ('error', 'dead_letter')]:
            self.assertEqual(route_after_precheck({'decision': decision}), node)
        self.assertEqual(route_after_precheck({}), 'dead_letter')
        self.assertEqual(route_after_precheck({'decision': 'explore'}), 'dead_letter')

    def test_extraction_branches_and_fail_closed_default(self):
        # Chưa đồng ý lập lịch (FR-AGT-06): `extract` trả lượt cho `gatekeep` với lời mời thay cho hỏi lại.
        for decision, node in [('missing_info', 'clarify'), ('tool', 'tool'), ('gatekeep', 'gatekeep'),
                               ('error', 'dead_letter')]:
            self.assertEqual(route_after_extract({'decision': decision}), node)
        self.assertEqual(route_after_extract({}), 'dead_letter')
        self.assertEqual(route_after_extract({'decision': 'compose'}), 'dead_letter')

    def test_orchestrator_without_a_model_ends_in_a_controlled_error(self):
        self.assertEqual(route_after_orchestrate({'decision': 'error'}), 'dead_letter')
        self.assertEqual(route_after_orchestrate({'decision': 'run_jobs'}), 'run_jobs')
        self.assertEqual(route_after_orchestrate({}), 'gatekeep')

    def test_evaluation_error_and_retry(self):
        self.assertEqual(route_after_evaluate({'decision': 'compose'}), 'filter')
        self.assertEqual(route_after_evaluate({'decision': 'failed'}), 'dead_letter')
        self.assertEqual(route_after_evaluate({'decision': 'needs_retry'}), 'retry')
        self.assertEqual(route_after_evaluate({'decision': 'constraint_clarification'}), 'clarify')
        self.assertEqual(route_after_evaluate({'decision': 'no_results'}), 'filter')

    def test_retry_limit_and_grounded_fallback(self):
        self.assertEqual(route_after_retry({'attempt': 1, 'max_attempts': 100}), 'tool')
        self.assertEqual(route_after_retry({'attempt': 2, 'max_attempts': 100}), 'dead_letter')
        self.assertEqual(route_after_retry({'attempt': 2, 'decision': 'fallback', 'candidates': {'real': {}}}), 'filter')
