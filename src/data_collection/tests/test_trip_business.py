import copy
import gzip
import json
import unittest
from pathlib import Path

from collectors.trip_business import parse_quote
from fresh_catalog_db import validate_catalog
from normalise import trip_business_products, trip_route_history
from data_collection.seed.release_flights import BUNDLE, load_bundle


class BusinessTests(unittest.TestCase):
    def setUp(self):
        self.quotes = json.load(gzip.open(BUNDLE.with_name('evidence.json.gz'), 'rt'))
        self.products = load_bundle()
        self.parents = {r['productId']: r for r in map(json.loads, gzip.open(BUNDLE.parent.parent/'2026-09-30/products.jsonl.gz','rt'))}

    def test_all_captured_business_quotes_map_to_same_stable_ids(self):
        for quote, product in zip(self.quotes, self.products):
            parent = self.parents[product['attributes']['parentProductId']]
            route = dict(fromAirports=[product['attributes']['originAirport']], toAirports=[product['attributes']['destinationAirport']], businessQuotes=[quote])
            output = trip_business_products(route, parent)[0]
            output.pop('_meta')
            self.assertEqual(output['productId'], product['productId'])
            self.assertEqual(output['unitPrice'], product['unitPrice'])
            self.assertEqual(output['attributes']['departureAt'], product['attributes']['departureAt'])
            validate_catalog([output], allow_external_parents=True)

    def test_economy_missing_price_or_missing_flight_is_rejected(self):
        q = self.quotes[0]
        for replacement in ({'cabin':'Hạng Phổ Thông'}, {'price':None}, {'flight':'Vietnam Airlines'},
                            {'observedAt':'invalid'}, {'flight':q['flight']+' Chặng 2'}, {'currency':'USD'}):
            self.assertIsNone(parse_quote({**q, **replacement}))

    def test_new_quote_wins_while_other_dates_survive(self):
        q = self.quotes[0]
        records = [{'key':'route','crawledAt':'2026-09-30T00:00:00Z','flights':[], 'businessQuotes':[q]},
                   {'key':'route','crawledAt':'2026-10-01T00:00:00Z','flights':[], 'businessQuotes':[]},
                   {'key':'route','crawledAt':'2026-10-01T00:00:00Z','flights':[],
                    'businessQuotes':[{**q,'price':5000000,'observedAt':'2026-10-01T00:00:00Z'}]}]
        result = trip_route_history(records)[0]['businessQuotes']
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['price'], 5000000)

    def test_quote_must_match_search_route_date_and_flight(self):
        q = self.quotes[0]
        for url in (q['url'].replace('quantity=1', 'quantity=2'),
                    q['url'].replace('2026-10-15', '2026-10-16'),
                    q['url'].replace('VN205', 'VN999'),
                    q['url'].replace('vn.trip.com', 'example.com')):
            self.assertIsNone(parse_quote({**q, 'url': url}))
        parent = self.parents[self.products[0]['attributes']['parentProductId']]
        route = dict(fromAirports=['DAD'], toAirports=['SGN'], businessQuotes=[q])
        self.assertEqual(trip_business_products(route, parent), [])
