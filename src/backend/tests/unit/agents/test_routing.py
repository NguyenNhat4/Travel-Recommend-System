import unittest
from src.backend.app.agents.routing import route_after_classify, route_after_evaluate, route_after_retry


class RoutingTests(unittest.TestCase):
    def test_classification_branches_and_fail_closed_default(self):
        for route, node in [('simple', 'answer'), ('missing_info', 'answer'), ('tool', 'tool'), ('error', 'dead_letter')]:
            self.assertEqual(route_after_classify({'route': route}), node)
        self.assertEqual(route_after_classify({}), 'dead_letter')

    def test_evaluation_error_and_retry(self):
        self.assertEqual(route_after_evaluate({'evaluation_result': 'success'}), 'answer')
        self.assertEqual(route_after_evaluate({'evaluation_result': 'failed'}), 'dead_letter')
        self.assertEqual(route_after_evaluate({'evaluation_result': 'needs_retry'}), 'retry')

    def test_retry_limit_and_grounded_fallback(self):
        self.assertEqual(route_after_retry({'attempt': 1, 'max_attempts': 100}), 'tool')
        self.assertEqual(route_after_retry({'attempt': 2, 'max_attempts': 100}), 'dead_letter')
        self.assertEqual(route_after_retry({'attempt': 2, 'decision': 'fallback', 'candidates': {'real': {}}}), 'answer')
