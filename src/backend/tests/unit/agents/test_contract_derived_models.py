"""LLM output models must take enums and bounds from the OpenAPI contract, not from copies."""
import unittest
from typing import get_args

from src.backend.app.agents import models
from src.backend.app.agents.steps.messages import message
from src.backend.app.application.itinerary.contracts import bounds, enum_values, schema


class ContractDerivedModelTests(unittest.TestCase):
    def test_enums_equal_the_contract_declaration(self):
        for literal, name in ((models.PartyType, 'PartyType'), (models.Pace, 'Pace'), (models.Taxonomy, 'Taxonomy')):
            with self.subTest(name=name):
                self.assertEqual(get_args(literal), tuple(schema(name)['enum']))
        self.assertEqual(get_args(models.PriceUnit), enum_values('ProductSummary', 'priceUnit'))

    def test_structured_output_schema_exposes_the_contract_values_to_the_model(self):
        properties = models.Extraction.model_json_schema()['$defs']
        self.assertEqual(properties['PartyUpdate']['properties']['type']['anyOf'][0]['enum'], list(enum_values('PartyType')))

    def test_numeric_bounds_and_user_messages_follow_the_contract(self):
        low, high = bounds('TripIntent', 'days')
        for language in ('vi', 'en'):
            text = message({'language': language}, 'invalid_reason_days_out_of_range', value=9)
            self.assertIn(str(low), text)
            self.assertIn(str(high), text)

    def test_out_of_range_numbers_reach_extract_instead_of_failing_the_model_output(self):
        # Giới hạn được kiểm ở `extract` theo contract, để người dùng nhận câu hỏi lại thay vì LLM_UNAVAILABLE.
        update = models.IntentUpdate(budget=-1, party={'adults': 0, 'children': -1})
        self.assertEqual((update.budget, update.party.adults, update.party.children), (-1, 0, -1))
