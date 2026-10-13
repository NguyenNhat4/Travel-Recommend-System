"""Contract-only checks for the separate assistant v2 entrypoint (E01)."""
from copy import deepcopy
import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from bundle_openapi import bundle


ROOT = Path(__file__).resolve().parents[2]


def validate_assistant_v2():
    document = bundle(ROOT / 'contracts/assistant-v2.openapi.yaml')
    schemas = document['components']['schemas']

    def refs(value):
        if isinstance(value, dict):
            for key, child in value.items():
                if key == '$ref':
                    assert child.startswith('#/'), child
                    target = document
                    for part in child[2:].split('/'):
                        target = target[part.replace('~1', '/').replace('~0', '~')]
                else:
                    refs(child)
        elif isinstance(value, list):
            for child in value:
                refs(child)

    refs(document)
    for schema in schemas.values():
        Draft202012Validator.check_schema(schema)

    def validator(name):
        return Draft202012Validator({'$ref': '#/components/schemas/' + name,
                                     'components': document['components']}, format_checker=FormatChecker())

    fixtures = ROOT / 'mocks/assistant-v2'
    index = json.loads((fixtures / 'index.json').read_text())
    for entry in index['fixtures']:
        operation = document['paths'][entry['path']][entry['method']]
        assert operation['operationId'] == entry['operationId']
        assert str(entry['status']) in operation['responses']
        value = json.loads((fixtures / entry['file']).read_text())
        for payload in value if entry.get('contentType') == 'text/event-stream' else [value]:
            validator(entry['schema']).validate(payload)

    request = json.loads((fixtures / 'request.json').read_text())
    validator('AssistantV2Request').validate(request)
    final = json.loads((fixtures / 'answer-30.json').read_text())
    assert sum(map(len, final['recommendations'].values())) == 30
    products = json.loads((ROOT / 'mocks/itinerary-agent/products.json').read_text())
    by_id = {p['productId']: p for p in products}
    for taxonomy, cards in final['recommendations'].items():
        assert len({p['productId'] for p in cards}) == len(cards)
        for card in cards:
            assert card == by_id[card['productId']]
            assert card['taxonomy'] == taxonomy

    negative = []
    bad = deepcopy(final)
    bad['recommendations']['hotel'].append(next(p for p in products if p['taxonomy'] == 'hotel'
                                              and p['productId'] not in {c['productId'] for c in bad['recommendations']['hotel']}))
    negative.append(('AssistantV2Final', bad))
    bad = deepcopy(final)
    bad['alternatives'] = [{'alternativeId': 'a1', 'product': next(p for p in products if p['taxonomy'] == 'hotel'
                             and p['productId'] not in {c['productId'] for c in bad['recommendations']['hotel']}),
                            'violates': [], 'disclosures': ['A separate alternative.'], 'itinerary': None,
                            'uiAction': {'type': 'select_alternative', 'actionId': 'x1', 'alternativeId': 'a1'}}]
    negative.append(('AssistantV2Final', bad))
    bad = deepcopy(final)
    bad['recommendations']['hotel'][0]['taxonomy'] = 'combo'
    negative.append(('AssistantV2Final', bad))
    negative.extend(('AssistantV2Request', payload) for payload in [
        {'clientTurnId': 't', 'basePlanRevision': None},
        dict(request, message='   '), dict(request, userId='another-owner'),
        dict(request, uiAction={'type': 'execute', 'tool': 'arbitrary'}),
        dict(request, conversationId='c', uiAction={'type': 'select_alternative', 'actionId': 'a', 'alternativeId': 'b'}),
        dict(request, intentOverride={'days': 0}),
    ])
    bad = deepcopy(final)
    bad['planEffect'] = 'replace'
    negative.append(('AssistantV2Final', bad))
    bad = json.loads((fixtures / 'itinerary-unknown.json').read_text())
    bad['itinerary']['costs']['estimatedTotalVnd'] = 0
    negative.append(('AssistantV2Final', bad))
    bad = json.loads((fixtures / 'itinerary-over.json').read_text())
    bad['itinerary']['days'][0]['activities'][0]['assumption'] = None
    negative.append(('AssistantV2Final', bad))
    for schema, payload in negative:
        assert not validator(schema).is_valid(payload), (schema, payload)

    stream = json.loads((fixtures / 'stream.json').read_text())
    assert [e['sequence'] for e in stream] == list(range(1, len(stream) + 1))
    assert sum(e['event'] in {'final', 'error'} for e in stream) == 1
    bad = deepcopy(stream[1])
    bad['data']['prompt'] = 'untrusted'
    assert not validator('AssistantV2Event').is_valid(bad)
    bad = deepcopy(stream[3])
    bad['data']['bookingAction'] = True
    assert not validator('AssistantV2Event').is_valid(bad)
    assert document['servers'] == [{'url': '/api/v2'}]
    print(f'PASS: assistant v2: {len(schemas)} schemas, {len(index["fixtures"])} fixtures, '
          f'{len(negative) + 2} negative checks; 30 grounded sample cards, 0 nights, four activities, over/unknown/zero costs.')


if __name__ == '__main__':
    validate_assistant_v2()
