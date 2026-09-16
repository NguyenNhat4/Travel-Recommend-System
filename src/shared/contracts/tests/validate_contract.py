"""Run from any directory: python3 src/shared/contracts/tests/validate_contract.py."""
import copy
import json
from pathlib import Path
import sys
from jsonschema import Draft202012Validator, FormatChecker

SHARED = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SHARED / 'contracts/scripts'))
from bundle_openapi import bundle

DOC = bundle()
SCHEMAS = DOC['components']['schemas']
FIXTURES = SHARED / 'mocks/itinerary-agent'

def validator(name):
    return Draft202012Validator({'$ref': '#/components/schemas/' + name, 'components': DOC['components']}, format_checker=FormatChecker())

def check_refs(value):
    if isinstance(value, dict):
        for k, v in value.items():
            if k == '$ref':
                assert v.startswith('#/'), v
                node = DOC
                for part in v[2:].split('/'):
                    node = node[part.replace('~1', '/').replace('~0', '~')]
            else:
                check_refs(v)
    elif isinstance(value, list):
        for v in value:
            check_refs(v)

check_refs(DOC)
for schema in SCHEMAS.values():
    Draft202012Validator.check_schema(schema)
products = json.loads((FIXTURES / 'products.json').read_text())
source = [json.loads(line) for line in (SHARED.parent / 'data_collection/sample/products-sample.jsonl').read_text().splitlines()]
assert len(products) == len(source) == 50
ids = {p['productId'] for p in products}
assert len(ids) == 50
for product, original in zip(products, source):
    validator('ProductSummary').validate(product)
    for key in SCHEMAS['ProductSummary']['required']:
        assert product[key] == original[key], key
    assert product['attributes'].get('parentProductId') in (None, *ids)
validator('SearchRequest').validate(json.loads((FIXTURES / 'search-request.json').read_text()))
for name in ['completed', 'needs-clarification', 'no-results', 'fallback']:
    validator('ItineraryResponse').validate(json.loads((FIXTURES / (name + '.json')).read_text()))
validator('RecommendationResponse').validate(json.loads((FIXTURES / 'recommendations-minimal.json').read_text()))
validator('ItineraryResponse').validate(json.loads((FIXTURES / 'completed-minimal.json').read_text()))
negative = [
    ('SearchRequest', {'query': '   '}),
    ('SearchRequest', {'query': 'hotel', 'category': 'HOTEL'}),
    ('SearchRequest', {'query': 'hotel', 'limit': 0}),
    ('ProductSummary', dict(products[0], unitPrice=-1)),
    ('ProductSummary', dict(products[0], attributes=[])),
    ('ItineraryResponse', {'status': 'COMPLETED'}),
]
completed = json.loads((FIXTURES / 'completed.json').read_text())
bad = copy.deepcopy(completed)
bad['itinerary']['budgetStatus'] = 'WITHIN_BUDGET'
negative.append(('ItineraryResponse', bad))
bad = copy.deepcopy(completed)
bad['itinerary']['days'][0]['slots'][0]['product'] = None
negative.append(('ItineraryResponse', bad))
for schema, payload in negative:
    assert not validator(schema).is_valid(payload), (schema, payload)
minimal = json.loads((FIXTURES / 'recommendations-minimal.json').read_text())
missing_reason = copy.deepcopy(minimal)
del missing_reason['recommendations'][0]['because']
assert not validator('RecommendationResponse').is_valid(missing_reason)
# Rich ProductDetail is still mandatory for Agent grounding.
assert not validator('ProductDetail').is_valid(minimal['recommendations'][0])
validator('BecauseItem').validate({'productName': 'Sản phẩm đã xem', 'event': 'product_view', 'daysAgo': 2})
# Existing UI fixtures are synthetic; validate their wire shape too.
index = json.loads((SHARED / 'mocks/index.json').read_text())
legacy_failures = []
for f in index['fixtures']:
    operation = DOC['paths'][f['path']][f['method']]
    response = operation['responses'][str(f['status'])]
    if '$ref' in response:
        response = DOC['components']['responses'][response['$ref'].split('/')[-1]]
    schema = response['content']['application/json']['schema']
    v = Draft202012Validator(dict(schema, components=DOC['components']), format_checker=FormatChecker())
    errors = list(v.iter_errors(json.loads((SHARED / 'mocks' / f['file']).read_text())))
    if errors:
        legacy_failures.append((f['file'], [e.message[:150] for e in errors]))
assert not legacy_failures, legacy_failures
print(f'PASS: {len(SCHEMAS)} schemas, all local refs, 50 grounded products, 4 itinerary statuses, minimal recommendation/itinerary payloads, negative checks, {len(index["fixtures"])} existing fixtures.')
