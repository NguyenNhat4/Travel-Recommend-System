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
            text = message({'language': language}, 'invalid_duration')
            self.assertIn(str(low), text)
            self.assertIn(str(high), text)
        self.assertEqual(models.PartyUpdate.model_fields['adults'].metadata[0].ge, bounds('Party', 'adults')[0])
