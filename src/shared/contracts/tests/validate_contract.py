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
# Checkout nhiều bước (1.10.0): ví dụ request của spec §7.4 hợp lệ; thiếu trường bắt buộc hoặc sai loại giá thì bị từ chối.
validator('CheckoutRequest').validate({
    'contact': {'fullName': 'Nguyễn Minh Anh', 'email': 'minhanh@example.vn', 'phone': '0912345678'},
    'travelers': [
        {'travelerRef': 't1', 'type': 'ADULT', 'surname': 'Nguyễn', 'givenNames': 'Minh Anh'},
        {'travelerRef': 't3', 'type': 'CHILD', 'surname': 'Nguyễn', 'givenNames': 'Gia Bảo', 'birthDate': '2019-05-12'}],
    'itemDetails': [
        {'cartItemId': 'ci-hotel', 'rooms': [{'travelerRefs': ['t1', 't3'], 'leadTravelerRef': 't1'}]},
        {'cartItemId': 'ci-vinwonders', 'travelerRefs': ['t1', 't3']}]})
validator('CheckoutTraveler').validate({'travelerRef': 't1', 'type': 'ADULT', 'surname': 'Nguyễn', 'givenNames': 'Minh Anh',
    'birthDate': '1988-03-14', 'documents': {'title': 'MS', 'nationality': 'VN', 'docType': 'CCCD', 'docNumber': '079188001234', 'docExpiry': None}})
validator('CheckoutTraveler').validate({'travelerRef': 't3', 'type': 'CHILD', 'surname': 'Nguyễn', 'givenNames': 'Gia Bảo',
    'birthDate': '2025-03-03', 'documents': {'title': 'MISS', 'nationality': 'VN', 'escortTravelerRef': 't1'}})
validator('BookingTraveler').validate({'fullName': 'A', 'type': 'ADULT', 'roomNo': None, 'isLead': False,
    'documents': {'title': 'MS', 'nationality': 'VN', 'docType': 'CCCD', 'docNumberLast4': '1234'}})
validator('AddCartItemRequest').validate({'productId': 'p', 'usingDate': '2026-10-15', 'guests': {'adults': 2, 'children': 1}})
validator('AddCartItemRequest').validate({'productId': 'p', 'usingDate': '2026-10-15', 'quantity': 2})
negative += [
    ('ValidationFieldError', {'field': 'travelers[0]', 'message': 'x'}),
    ('CheckoutTraveler', {'travelerRef': 't1', 'type': 'ADULT', 'surname': 'Nguyễn'}),
    ('CheckoutTraveler', {'travelerRef': 't 1', 'type': 'ADULT', 'surname': 'Nguyễn', 'givenNames': 'An'}),
    ('CheckoutTraveler', {'travelerRef': 't1', 'type': 'ADULT', 'surname': 'N', 'givenNames': 'A', 'documents': {'title': 'DR'}}),
    ('CheckoutTraveler', {'travelerRef': 't1', 'type': 'ADULT', 'surname': 'N', 'givenNames': 'A', 'documents': {'docType': 'DRIVING'}}),
    ('BookingTravelerDocuments', {'title': 'MS', 'nationality': 'VN', 'docNumber': '079188001234'} | {'title': 'XX'}),
    ('AddCartItemRequest', {'productId': 'p', 'usingDate': '2026-10-15'}),
    ('GuestCounts', {'adults': 0, 'children': 0}),
    ('GuestCounts', {'adults': 1, 'children': 9}),
    ('FareLine', {'fareType': 'BAG', 'unitPrice': 1, 'count': 1, 'nights': None, 'amount': 1}),
    ('BookingTraveler', {'fullName': 'A', 'type': 'INFANT', 'roomNo': None, 'isLead': False}),
]
# Đặt trực tiếp qua đơn nháp (1.13.0, docs/spec/booking/dat-truc-tiep-theo-don-nhap.md §10): đúng một trong items / fromBooking.
validator('CreateBookingDraftRequest').validate({'items': [{'productId': 'p', 'usingDate': '2026-10-15', 'quantity': 1, 'nights': 2}], 'allowPartial': True})
validator('CreateBookingDraftRequest').validate({'fromBooking': 'VOTA-20261001-AB12'})
validator('GuestMergeRequest').validate({'guestId': 'g_' + 'a' * 22})
validator('CheckoutRequest').validate({'draftId': 'd-1', 'contact': {'fullName': 'A B', 'email': 'a@example.vn', 'phone': '0912345678'}, 'itemDetails': []})
negative += [
    ('CreateBookingDraftRequest', {}),
    ('CreateBookingDraftRequest', {'items': []}),
    ('CreateBookingDraftRequest', {'items': [{'productId': 'p', 'usingDate': '2026-10-15', 'quantity': 1}], 'fromBooking': 'VOTA-20261001-AB12'}),
    ('CreateBookingDraftRequest', {'fromBooking': 'not-a-code'}),
    ('GuestMergeRequest', {'guestId': 'a_123'}),
    ('BookingDraft', {'draftId': 'd', 'items': []}),
]
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
# details.fields[] của VALIDATION_ERROR ở booking đúng ValidationFieldError (docs/spec/booking/checkout-nhieu-buoc-hanh-khach.md §7.5).
for f in index['fixtures']:
    if f['file'].startswith('booking/'):
        error = json.loads((SHARED / 'mocks' / f['file']).read_text()).get('error') or {}
        for field_error in (error.get('details') or {}).get('fields', []):
            validator('ValidationFieldError').validate(field_error)
validator('TrackEventRequest').validate({'eventName': 'product_view', 'productId': products[0]['productId']})
for payload in [{'eventName': 'purchase', 'productId': 'x'}, {'eventName': 'product_view'},
                {'eventName': 'product_view', 'productId': 'x', 'taxonomy': 'hotel'}]:
    assert not validator('TrackEventRequest').is_valid(payload), payload

# CDP clone is a separate service with its own entry document.
CDP_DOC = bundle(SHARED / 'contracts/cdp-clone.openapi.yaml')
CDP_FIXTURES = SHARED / 'mocks/cdp-clone'

def cdp_validator(name):
    return Draft202012Validator({'$ref': '#/components/schemas/' + name, 'components': CDP_DOC['components']}, format_checker=FormatChecker())

DOC = CDP_DOC
check_refs(CDP_DOC)
for schema in CDP_DOC['components']['schemas'].values():
    Draft202012Validator.check_schema(schema)
cdp_fixtures = [
    ('RecordEventsRequest', 'backend-browse-events.request.json'),
    ('RecordEventsRequest', 'backend-purchase.request.json'),
    ('RecordEventsResponse', 'record-events.201.json'),
    ('ErrorResponse', 'record-events.401-invalid-token.json'),
    ('UserEvent', 'cancel-event.200.json'),
    ('EventListResponse', 'user-events.200.json'),
    ('Profile', 'profile.200.json'),
]
for schema, name in cdp_fixtures:
    cdp_validator(schema).validate(json.loads((CDP_FIXTURES / name).read_text()))
sample_ids = {p['productId'] for p in source}
for name in ['backend-browse-events.request.json', 'backend-purchase.request.json']:
    for event in json.loads((CDP_FIXTURES / name).read_text())['events']:
        assert event.get('productId') in (None, *sample_ids), event
purchase = json.loads((CDP_FIXTURES / 'backend-purchase.request.json').read_text())['events'][0]
cdp_negative = [
    {'events': []},
    {'events': [{k: v for k, v in purchase.items() if k != 'cdpUserId'}]},
    {'events': [{'eventName': 'search'}]},
    {'events': [{'eventName': 'product_view', 'productId': 'x'}]},
    {'events': [{'eventName': 'add_to_cart', 'productId': 'x', 'taxonomy': 'hotel'}]},
    {'events': [{k: v for k, v in purchase.items() if k != 'eventId'}]},
    {'events': [dict(purchase, eventGroupId=None)]},
    {'events': [dict(purchase, eventName='click')]},
    {'events': [dict(purchase, destination='Nha Trang')]},
    {'events': [{'eventName': 'search', 'searchQuery': 'x'}] * 101},
]
for payload in cdp_negative:
    assert not cdp_validator('RecordEventsRequest').is_valid(payload), payload
assert not cdp_validator('ProfileAttributes').is_valid({'lifecycleStage': 'sleeping'})
assert 'bearerAuth' not in CDP_DOC['components']['securitySchemes']
assert CDP_DOC['security'] == [{'serviceToken': []}]
print(f'PASS: {len(SCHEMAS)} schemas, all local refs, 50 grounded products, 4 itinerary statuses, minimal recommendation/itinerary payloads, negative checks, {len(index["fixtures"])} existing fixtures; CDP clone: {len(CDP_DOC["components"]["schemas"])} schemas, {len(cdp_fixtures)} fixtures, {len(cdp_negative) + 1} negative checks.')
