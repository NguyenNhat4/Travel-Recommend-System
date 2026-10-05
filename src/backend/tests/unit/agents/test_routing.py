import unittest
from src.backend.app.agents.routing import route_after_classify, route_after_evaluate, route_after_extract, route_after_retry


class RoutingTests(unittest.TestCase):
    def test_classification_branches_and_fail_closed_default(self):
        for decision, node in [('simple', 'converse'), ('travel', 'extract'), ('missing_info', 'clarify'),
                               ('error', 'dead_letter')]:
            self.assertEqual(route_after_classify({'decision': decision}), node)
        self.assertEqual(route_after_classify({}), 'dead_letter')

    def test_extraction_branches_and_fail_closed_default(self):
        for decision, node in [('missing_info', 'clarify'), ('tool', 'tool'), ('error', 'dead_letter')]:
            self.assertEqual(route_after_extract({'decision': decision}), node)
        self.assertEqual(route_after_extract({}), 'dead_letter')
        self.assertEqual(route_after_extract({'decision': 'simple'}), 'dead_letter')

    def test_evaluation_error_and_retry(self):
        self.assertEqual(route_after_evaluate({'decision': 'compose'}), 'compose')
        self.assertEqual(route_after_evaluate({'decision': 'failed'}), 'dead_letter')
        self.assertEqual(route_after_evaluate({'decision': 'needs_retry'}), 'retry')
        self.assertEqual(route_after_evaluate({'decision': 'constraint_clarification'}), 'clarify')
        self.assertEqual(route_after_evaluate({'decision': 'no_results'}), 'compose')

    def test_retry_limit_and_grounded_fallback(self):
        self.assertEqual(route_after_retry({'attempt': 1, 'max_attempts': 100}), 'tool')
        self.assertEqual(route_after_retry({'attempt': 2, 'max_attempts': 100}), 'dead_letter')
        self.assertEqual(route_after_retry({'attempt': 2, 'decision': 'fallback', 'candidates': {'real': {}}}), 'compose')
