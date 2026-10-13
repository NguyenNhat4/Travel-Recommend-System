"""Public progress for streaming only. Code owns counts; no prompts or free-form model text."""
from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
from math import ceil

from src.backend.app.application.itinerary.progress_counts import ProductCounts
from src.backend.app.domain.itinerary.geo import coords

_CURRENT = ContextVar('itinerary_public_progress', default=None)
KINDS = ('hotel', 'attraction', 'golf', 'combo', 'flight')
STEPS = {'plan': ['understand', 'search', 'arrange', 'write'],
         'explore': ['understand', 'search', 'write'], 'fare': ['understand', 'search'],
         'clarify': ['understand'], 'converse': ['understand'], 'blocked': []}


@contextmanager
def collecting():
    token = _CURRENT.set(dict(groups={}, activity_count=0, last_activity=None, kind='converse'))
    try:
        yield
    finally:
        _CURRENT.reset(token)


def active():
    return _CURRENT.get() is not None


def _scope(spec):
    scope = {key: spec[key] for key in ('destination', 'origin', 'near', 'sort', 'intent', 'date', 'returnDate')
             if spec.get(key) is not None}
    for internal, public in (('scope_mode', 'scopeMode'), ('excluded_destinations', 'excludedDestinations'),
                             ('requested_count', 'requestedCount')):
        if spec.get(internal) is not None and spec.get(internal) != []:
            scope[public] = deepcopy(spec[internal])
    return scope


def group(group_id, kind, spec=None):
    ctx = _CURRENT.get()
    if ctx is None or kind not in KINDS:
        return None
    row = ctx['groups'].setdefault(group_id, dict(groupId=group_id, kind=kind, status='running',
                                                scope={}, counter=ProductCounts()))
    spec = spec or {}
    scope = _scope(spec)
    row['scope'].update(scope)
    return row


def notify(code, *, node_id=None, **params):
    ctx = _CURRENT.get()
    if ctx is None or ctx['activity_count'] >= 30:
        return
    data = {'nodeId': node_id or ctx.get('node', 'run_jobs'), 'code': code}
    data.update({key: value for key, value in params.items()
                 if key in ('round', 'groupId', 'kinds', 'destination', 'origin', 'date') and value is not None})
    if data == ctx['last_activity']:
        return
    from langgraph.config import get_stream_writer
    try:
        writer = get_stream_writer()
    except RuntimeError:
        return
    writer({'event': 'node.activity', 'data': data})
    ctx['last_activity'] = data
    ctx['activity_count'] += 1


def started(name, state):
    ctx = _CURRENT.get()
    if ctx is None:
        return
    ctx['node'] = name
    notify('STARTED', node_id=name, **({'round': state.get('turn_rounds', 0)+1} if name == 'orchestrate' else {}))


def products(response):
    """All products actually present in the response, preserving itinerary order."""
    itinerary = response.get('itinerary') or {}
    result = []
    def walk(value):
        if isinstance(value, dict):
            if value.get('productId') and value.get('taxonomy') in KINDS:
                result.append(value)
            else:
                for child in value.values():
                    walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)
    walk(itinerary)
    walk(response.get('searchResults') or {})
    seen = set()
    return [p for p in result if not (p['productId'] in seen or seen.add(p['productId']))]


def _kind(name, state, old):
    decision = state.get('decision')
    if state.get('blocked_by_guardrail') or state.get('unclear_input') or name == 'dead_letter':
        return 'blocked'
    if name in ('extract', 'clarify') and decision in ('missing_info', 'invalid_input', 'constraint_clarification'):
        return 'clarify'
    if name in ('tool', 'evaluate', 'filter', 'compose', 'narrate') or decision == 'travel':
        return 'plan'
    turn = state.get('orchestrator_turn') or {}
    if name == 'orchestrate' and turn.get('action') == 'plan':
        return 'plan'
    jobs = state.get('turn_jobs') or turn.get('jobs') or []
    if jobs:
        return 'explore' if any(j.get('kind') == 'explore' for j in jobs) else 'fare'
    return old if name == 'finalize' else 'converse'


def _understood(state, kind):
    trip_turn = kind in ('plan', 'clarify')
    raw = (state.get('intent') or {}) if trip_turn else {}
    intent = {key: raw[key] for key in ('destination','origin','startDate','days','party','budget','interests','pace')
              if raw.get(key) is not None}
    assumptions = []
    if kind == 'plan' and raw.get('budget') is None:
        assumptions.append({'code': 'NO_BUDGET'})
    skip = (state.get('flight_options') or {}).get('status') if trip_turn else None
    code = {'NO_ORIGIN':'NO_ORIGIN','DAY_TRIP':'DAY_TRIP','EXCLUDED':'FLIGHT_EXCLUDED','SAME_CITY':'SAME_CITY'}.get(skip)
    if code:
        assumptions.append({'code': code})
    if trip_turn and (state.get('constraints') or {}).get('party_type_hint') == 'FAMILY_WITH_KIDS':
        assumptions.append({'code':'KIDS_COUNT_UNKNOWN'})
    party = raw.get('party') or {}
    count = ceil(((party.get('adults') or 0)+(party.get('children') or 0))/9)
    if count > 1:
        assumptions.append({'code':'ROOM_MIN_GUESTS','count':count})
    ctx = _CURRENT.get()
    jobs = [{'groupId':g['groupId'],'kind':g['kind'],'scope':g['scope']} for g in ctx['groups'].values()
            if g['groupId'].startswith('job:') and g['status'] != 'superseded']
    # A first execute decision already tells us what will be searched, before any tool has finished.
    if not jobs and kind in ('explore', 'fare'):
        for index, spec in enumerate((state.get('orchestrator_turn') or {}).get('jobs') or [], 1):
            source = spec.get('fare') or {} if spec.get('kind') == 'fare' else spec
            taxonomy = 'flight' if spec.get('kind') == 'fare' else spec.get('taxonomy')
            if taxonomy not in KINDS:
                continue
            scope = _scope(source)
            if source.get('day'):
                scope['date'] = source['day']
            jobs.append({'groupId': f'job:{index}', 'kind': taxonomy, 'scope': scope})
    return dict(**({'intent':intent} if intent else {}),
                missing=(state.get('missing_fields') or []) if trip_turn else [],
                jobs=jobs[:12], assumptions=assumptions)


def completed(name, before, update):
    ctx = _CURRENT.get()
    if ctx is None:
        return update
    state = {**before, **update}
    kind = _kind(name, state, ctx['kind'])
    ctx['kind'] = kind
    chosen = None
    if name in ('compose','gatekeep','finalize') and state.get('response'):
        chosen = {p['productId'] for p in products(state['response'])}
    searches, notices = [], []
    for g in ctx['groups'].values():
        row = {k:deepcopy(g[k]) for k in ('groupId','kind','scope','status')}
        if g.get('counter') is not None:
            row['counts'] = g['counter'].snapshot(chosen)
            for code,count in row['counts']['dropped'].items():
                if count:
                    notices.append(dict(code=code,groupId=row['groupId'],kind=row['kind'],count=count))
        if g['status'] in ('failed','unavailable'):
            notices.append(dict(code='LOOKUP_FAILED',groupId=row['groupId'],kind=row['kind']))
        if g['status'] == 'partial':
            notices.append(dict(code='PARTIAL_RESULTS',groupId=row['groupId'],kind=row['kind']))
        searches.append(row)
    if name == 'retry':
        notices.append({'code':'RETRYING'})
    if state.get('nearest_open_date'):
        notices.append({'code':'NOT_ON_SALE','date':state.get('intent',{}).get('startDate') or state['nearest_open_date']})
    response = state.get('response') or {}
    if (response.get('itinerary') or {}).get('budgetStatus') == 'OVER_BUDGET':
        notices.append({'code':'OVER_BUDGET'})
    understood = _understood(state,kind)
    if name == 'tool':
        changed = set().union(*((e.get('metadata') or {}).get('changed', []) for e in update.get('events') or []))
        for key in ('destination','origin'):
            old, new = (before.get('intent') or {}).get(key), (state.get('intent') or {}).get(key)
            if key in changed and old and new and old != new:
                understood['assumptions'].append({'code':'NAME_MATCHED','from':old,'to':new})
    payload = dict(turnKind=kind,steps=STEPS[kind],understood=understood,searches=searches[:12],notices=notices[:10])
    finished = {'extract':'understand','run_jobs':'search','evaluate':'search','compose':'arrange','narrate':'write','gatekeep':'write','clarify':'understand'}.get(name)
    if name == 'precheck' and (kind=='fare' or decision_is_plan(state)):
        finished='understand'
    if name == 'orchestrate' and (state.get('orchestrator_turn') or {}).get('action') in ('execute','plan','answer','ask'):
        finished = 'understand'
    if finished in STEPS[kind]:
        payload['completedStep'] = finished
    if name == 'compose' and response.get('status') == 'COMPLETED':
        itinerary = response['itinerary']
        points = [p for p in products(response) if coords(p) is not None]
        criteria = ['MAX_TWO_ACTIVITIES_PER_DAY']
        if len(points) >= 2:
            criteria.insert(0,'SHORTEST_DISTANCE')
        if any(p['taxonomy']=='flight' for p in products(response)):
            criteria.append('FLIGHT_TIMES')
        if any(g['counter'] and g['counter'].snapshot()['dropped'].get('PREFERENCE') for g in ctx['groups'].values()):
            criteria.append('STAY_PREFERENCE')
        payload['arranged'] = dict(criteria=criteria,stayOptions=len(response.get('stayOptions') or []),budgetStatus=itinerary.get('budgetStatus','UNKNOWN'))
    events = update.get('events') or []
    if events:
        update = {**update,'events':[*events[:-1],{**events[-1],'progress':payload}]}
    return update

_JOB = ContextVar('itinerary_progress_job', default=None)

@contextmanager
def job_context(group_id):
    token = _JOB.set(group_id)
    try:
        yield
    finally:
        _JOB.reset(token)


def current_group():
    ctx = _CURRENT.get()
    return ctx['groups'].get(_JOB.get()) if ctx else None


def lookup_failed():
    row = current_group()
    if row:
        row['lookup_failed'] = True


def decision_is_plan(state):
    return state.get('decision') in ('travel','tool')
