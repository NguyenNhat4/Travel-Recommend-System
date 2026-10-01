"""Structural regression checks: keep nine nodes and no risky/HITL path."""
import copy
import functools
import unittest
from types import SimpleNamespace
from src.backend.app.agents import nodes, routing
from src.backend.app.agents.steps import classification
from src.backend.app.agents.graph import build_graph
from src.backend.app.agents.state import AgentState
from src.backend.app.agents.models import Extraction
from src.backend.app.application.itinerary.contracts import error_response


class LabCopyTests(unittest.TestCase):
    def test_removed_routes_and_state_fields(self):
        # `route`/`evaluation_result` gộp vào `decision`; `thread_id`/`scenario_id`/`messages`/`errors`/
        # `pending_question`/`llm_used` bỏ vì không node nào đọc lại (docs/spec/agent/field-review.md §3).
        self.assertFalse({'risk_level', 'approval', 'proposed_action', 'route', 'evaluation_result',
                          'thread_id', 'scenario_id', 'messages', 'errors', 'pending_question',
                          'llm_used'} & AgentState.__annotations__.keys())
        self.assertFalse(hasattr(nodes, 'approval_node'))
        self.assertFalse(hasattr(nodes, 'risky_action_node'))
        self.assertFalse(hasattr(routing, 'route_after_approval'))

    def test_twelve_node_topology(self):
        graph = build_graph()
        self.assertEqual(set(graph.get_graph().nodes) - {'__start__', '__end__'},
                         {'intake', 'classify', 'extract', 'tool', 'evaluate', 'converse', 'compose', 'narrate',
                          'clarify', 'retry', 'dead_letter', 'finalize'})

    def test_every_node_is_named_for_the_trace(self):
        """`partial` mất __name__, nên node dựng từ nó sẽ hiện là "RunnableLambda" trong LangSmith."""
        for name, node in build_graph().nodes.items():
            if name.startswith('__'):
                continue
            with self.subTest(node=name):
                self.assertNotEqual(node.bound.get_name(), 'RunnableLambda')

    def test_nodes_do_not_mutate_the_input_state(self):
        state = nodes.intake_node({'query': '  request  ', 'request_id': 'test'})
        classified = classification.extract_result(state, Extraction(patch={'days': 3}))
        state.update(classified)
        state['response'] = error_response('INTERNAL_ERROR', 'safe error', 'test')
        state['http_status'] = 500
        state['decision'] = 'error'
        # `clarify` would call a real model here, so hand it one that fails and exercise the fixed-wording fallback.
        offline = SimpleNamespace(with_structured_output=lambda schema: (_ for _ in ()).throw(RuntimeError('offline')))
        ask = functools.partial(nodes.ask_clarification_node, llm=offline)
        ask.__name__ = 'ask_clarification_node'
        for node in [nodes.intake_node, nodes.evaluate_node, ask, nodes.compose_node,
                     nodes.retry_or_fallback_node, nodes.dead_letter_node, nodes.finalize_node]:
            with self.subTest(node=node.__name__):
                before = copy.deepcopy(state)
                self.assertIsInstance(node(state), dict)
                self.assertEqual(state, before)
