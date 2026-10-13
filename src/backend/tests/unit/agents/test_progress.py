import unittest
from src.backend.app.agents.steps import progress
from src.backend.app.application.itinerary.progress_counts import ProductCounts
from .test_orchestrator_jobs import Tools, initial, product
from src.backend.app.agents.steps import jobs


class ProgressTests(unittest.IsolatedAsyncioTestCase):
    def test_public_scope_explains_replacement_and_count_without_raw_query(self):
        from src.backend.app.application.itinerary.contracts import valid
        state={'orchestrator_turn':{'action':'execute','jobs':[{'kind':'explore','intent':'more',
            'taxonomy':'attraction','scope_mode':'replace','destination':None,
            'excluded_destinations':['Vũng Tàu'],'requested_count':10,'query':'raw internal query'}]}}
        with progress.collecting():
            result=progress.completed('orchestrate',state,{'events':[{'node':'orchestrate'}]})
        payload=result['events'][0]['progress']
        self.assertTrue(valid('AssistantProgressUpdate',payload))
        scope=payload['understood']['jobs'][0]['scope']
        self.assertEqual(scope['scopeMode'],'replace')
        self.assertEqual(scope['excludedDestinations'],['Vũng Tàu'])
        self.assertEqual(scope['requestedCount'],10)
        self.assertNotIn('query',scope)

    async def test_actual_page_counts_seen_once_and_preserves_products(self):
        state = initial()
        spec = dict(kind='explore', intent='new', taxonomy='hotel', destination='Hà Nội')
        with progress.collecting():
            result = await jobs.execute(state, [spec], tools=Tools([product('a'), product('b')]),
                                        timeout_seconds=1, budget_seconds=30)
            update = progress.completed('run_jobs', state, {**result,'events':[{'node':'run_jobs'}]})
        group = update['events'][0]['progress']['searches'][0]
        self.assertEqual(group['counts']['inScope'], 2)
        self.assertEqual(group['counts']['eligible'], 2)
        self.assertEqual(group['groupId'], 'job:1')

    def test_accounting_partitions_and_unique_products(self):
        counter = ProductCounts()
        counter.record('a')
        counter.record('b','SEEN')
        counter.record('b','SEEN')
        counter.record('c','DISTANCE',outside=True)
        counts = counter.snapshot({'a','c'})
        self.assertEqual(counts['received'], 3)
        self.assertEqual(counts['inScope'], 2)
        self.assertEqual(counts['eligible'], 1)
        self.assertEqual(counts['chosen'], 1)

    def test_preview_requires_completed_and_all_sources(self):
        p = product('a')
        response = dict(status='COMPLETED',itinerary={'days':[{'slots':[{'product':p}]}]})
        self.assertIsNone(progress.preview({}, {'response':response}))
        self.assertEqual(progress.preview({'sources':{'a':'search'}}, {'response':response})['products'], [p])
        self.assertIsNone(progress.preview({'sources':{'a':'search'}}, {'response':{**response,'status':'FALLBACK'}}))

    def test_no_progress_outside_stream_and_no_context_leak(self):
        update={'events':[{'node':'tool'}]}
        self.assertIs(progress.completed('tool',{},update), update)
        with progress.collecting():
            self.assertTrue(progress.active())
        self.assertFalse(progress.active())

    async def test_graph_stream_emits_real_activity_and_valid_progress_without_changing_json(self):
        from src.backend.app.agents.graph import build_graph
        from src.backend.app.agents.runtime_dependencies import LangGraphItineraryPlanner
        from src.backend.app.application.itinerary.contracts import valid
        from .test_orchestrator_runtime import Llm
        def llm():
            return Llm({'action':'execute','jobs':[{'kind':'explore','taxonomy':'hotel','destination':'Hà Nội'}]},
                       {'action':'answer','message':'[Nơi a](#1) phù hợp cho bạn.','cards':['#1']})
        graph = build_graph(llm=llm(),tools=Tools([product('a')]),llm_timeout_seconds=1,orchestrator_budget_seconds=30)
        chunks = [chunk async for chunk in LangGraphItineraryPlanner(graph).astream({'query':'Tìm chỗ nghỉ tại Hà Nội'})]
        activities = [payload['data'] for mode,payload in chunks if mode=='event' and payload['event']=='node.activity']
        self.assertTrue(activities)
        self.assertLessEqual(len(activities),30)
        for activity in activities:
            self.assertTrue(valid('AssistantNodeActivity',activity),activity)
        final = [state for mode,state in chunks if mode=='state'][-1]
        for ev in final['events']:
            if ev.get('progress'):
                self.assertTrue(valid('AssistantProgressUpdate',ev['progress']),ev['progress'])
        json_graph=build_graph(llm=llm(),tools=Tools([product('a')]),llm_timeout_seconds=1,orchestrator_budget_seconds=30)
        plain = await json_graph.ainvoke({'query':'Tìm chỗ nghỉ tại Hà Nội'})
        strip = lambda response: {key:value for key,value in response.items() if key!='conversationId'}
        self.assertEqual(strip(final['response']),strip(plain['response']))
        self.assertFalse(progress.active())

    async def test_far_and_unavailable_product_is_out_of_scope_before_supply(self):
        state=initial()
        location=product('anchor',taxonomy='attraction')
        far=product('far',available=False,attributes={'latitude':10,'longitude':110})
        near=product('near')
        # Reference lookup uses the existing shown-card context.
        from src.backend.app.agents.steps import shown
        state['shown']=shown.record({}, {'status':'NEEDS_CLARIFICATION','searchResults':{'attraction':[location]}})
        ref=state['shown']['items'][0]['ref']
        with progress.collecting():
            result=await jobs.execute(state,[dict(kind='explore',intent='new',taxonomy='hotel',destination='Hà Nội',near=ref)],tools=Tools([location,far,near]),timeout_seconds=1,budget_seconds=30)
            update=progress.completed('run_jobs',state,{**result,'events':[{'node':'run_jobs'}]})
        counts=update['events'][0]['progress']['searches'][0]['counts']
        self.assertEqual(counts['outOfScope'].get('DISTANCE'),1)
        self.assertEqual(counts['dropped'],{})

    def test_exploration_and_fare_do_not_repeat_the_saved_trip(self):
        state={'intent':{'destination':'Nha Trang','startDate':'2026-10-17','origin':'Nghệ An'},
               'missing_fields':['days'],'constraints':{'party_type_hint':'FAMILY_WITH_KIDS'},
               'orchestrator_turn':{'action':'execute','jobs':[{'kind':'explore','intent':'more','taxonomy':'attraction','destination':'Huế'}]}}
        with progress.collecting():
            progress.group('job:1','attraction',{'destination':'Huế','intent':'more'})
            for kind in ('explore','fare'):
                understood=progress._understood(state,kind)
                self.assertNotIn('intent',understood)
                self.assertEqual(understood['missing'],[])
                self.assertEqual(understood['assumptions'],[])
                self.assertNotIn('Nha Trang',str(understood))
            plan=progress._understood(state,'plan')
            self.assertEqual(plan['intent']['destination'],'Nha Trang')

    def test_jobs_are_visible_when_orchestrator_has_decided_before_search_finishes(self):
        state={'intent':{'destination':'Nha Trang','startDate':'2026-10-17'},
               'orchestrator_turn':{'action':'execute','jobs':[{'kind':'explore','intent':'more','taxonomy':'hotel','destination':'Huế'}]}}
        with progress.collecting():
            result=progress.completed('orchestrate',state,{'events':[{'node':'orchestrate'}]})
        understood=result['events'][0]['progress']['understood']
        self.assertEqual(understood['jobs'][0]['scope']['destination'],'Huế')
        self.assertEqual(understood['jobs'][0]['scope']['intent'],'more')
        self.assertNotIn('intent',understood)
