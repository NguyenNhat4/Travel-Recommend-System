"""Inspect and grade the current graph against the authored fixture cases."""
from __future__ import annotations
import asyncio
from functools import partial
import json
from pathlib import Path
import sys

import streamlit as st

ROOT=Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from src.backend.app.agents.graph import build_graph
from src.backend.app.agents.llm import get_llm
from src.backend.app.agents.tools.itinerary_gateway import ItineraryToolGateway
from src.backend.app.infrastructure.clients.itinerary_fixture_clients import FixtureItineraryClients
from src.backend.app.infrastructure.clients.itinerary_conversation_store import InMemoryConversationStore
from src.evaluation.agent.evaluation_runner import CaseSession, apply_review, load_suite, make_report, run_full_evaluation, save_report
from src.evaluation.agent.suite_visualization import build_graph_dot, build_graph_mermaid


def rows(results):
    return [{'Case':r['id'],'Kết quả':r['status'],'Lỗi tự động':r['automatedFailures'],
             'Thiếu bằng chứng':len(r['blockers']),'Thời gian (ms)':r['durationMs'],
             'Số lượt':len(r['turns'])} for r in results]


def show_graph(graph, state, title='Graph luồng agent'):
    st.subheader(title)
    events=state.get('events',[])
    st.caption(' → '.join(e['node'] for e in events) or 'Chưa chạy case — sơ đồ đầy đủ của agent.')
    st.graphviz_chart(build_graph_dot(graph,events),width='stretch')
    st.caption('Xanh: node/cạnh đã chạy · Đỏ: node có lỗi · Xám: chưa chạy · Nét đứt: cạnh điều kiện.')


def display_result(result, namespace, on_review):
    st.subheader(f"{result['id']} · {result['status']}")
    if result['error']: st.error(result['error'])
    if result['runtimeErrors']: st.warning('Runtime error: '+', '.join(result['runtimeErrors']))
    for issue in result['blockers']: st.warning(issue)
    st.caption(f"{result['automatedFailures']} tiêu chí tự động sai · {result['durationMs']:.2f} ms")
    turn=None
    if result['turns']:
        index=st.selectbox('Lượt hội thoại',range(len(result['turns'])),format_func=lambda i:f"Lượt {i+1}",key=f"{namespace}_turn_{result['id']}")
        turn=result['turns'][index]
        snapshots=turn['snapshots']
        graph_state=turn['state']
        if snapshots:
            # A new run/turn has its own selection, initially showing the final step.
            run_id=turn['state'].get('request_id','')
            selected=st.selectbox('State sau node',range(len(snapshots)),index=len(snapshots)-1,
                                  format_func=lambda i:f"{i+1}. {snapshots[i]['node']}",
                                  key=f"{namespace}_node_{result['id']}_{index}_{run_id}")
            graph_state=snapshots[selected]['state']
        graph=build_graph()
        show_graph(graph,graph_state)
        with st.expander('Mermaid từ LangGraph'):
            mermaid=build_graph_mermaid(graph,graph_state.get('events',[]))
            st.code(mermaid,language='mermaid')
            st.download_button('Tải Mermaid graph',mermaid,file_name=f"{result['id']}-turn-{index+1}.mmd",
                               mime='text/plain',key=f"{namespace}_mermaid_{result['id']}_{index}")
    st.dataframe([{'Tiêu chí':c['criterion'],'Expected':json.dumps(c['expected'],ensure_ascii=False),
                   'Actual':json.dumps(c['actual'],ensure_ascii=False),'Kết quả':c['status'],
                   'Bằng chứng':c['evidence']} for c in result['checks']], hide_index=True, width='stretch')
    if turn is None: return
    state=turn['state']
    st.write('Khách:',turn['request']['message'])
    response_tab,state_tab,trace_tab=st.tabs(['Response','State từng node','Tool calls'])
    with response_tab:
        response=state.get('response',{})
        st.write(response.get('question') or response.get('message') or state.get('final_answer',''))
        plan=response.get('itinerary',{})
        if plan.get('stay'): st.write('Lưu trú:',plan['stay']['product']['name'])
        for day in plan.get('days',[]):
            st.write(f"Ngày {day['day']} · {day.get('date') or ''}")
            st.dataframe([{'Buổi':s['time'],'Sản phẩm':(s.get('product') or {}).get('name',s.get('activityType')),
                           'Giá':(s.get('product') or {}).get('unitPrice'),'Ghi chú':s.get('note')} for s in day['slots']],hide_index=True,width='stretch')
        st.json(response,expanded=True)
    with state_tab:
        st.json(graph_state,expanded=False)
    with trace_tab:
        st.json(turn['calls'],expanded=True)
        st.caption('Call lấy tại port, gồm Catalog hydration; retry xuất hiện trong thứ tự call và events.')
    if result['complete']:
        with st.expander('Review tiêu chí nghiệp vụ'):
            st.caption('Xem mọi dòng REVIEW, response và trace trước khi xác nhận. Review không ghi đè lỗi tự động hoặc BLOCKED.')
            run_key=f"{namespace}_{result['id']}_{result['turns'][0]['state'].get('request_id','')}"
            decision=st.radio('Kết luận review',['PASS','FAIL'],key=f'review_{run_key}')
            comment=st.text_input('Nhận xét review',key=f'comment_{run_key}')
            if st.button('Lưu review',key=f'save_review_{run_key}'):
                on_review(apply_review(result,decision,comment))
                st.rerun()


def persist(report):
    st.session_state.report=report
    try:
        st.session_state.report_path=str(save_report(report))
        st.session_state.save_error=None
    except OSError:
        st.session_state.save_error='Không ghi được report vào thư mục reports; vẫn có thể tải JSON.'


st.set_page_config(page_title='Itinerary Agent Evaluation',layout='wide')
st.title('Đánh giá Itinerary Agent')
st.caption('Graph hiện tại · LLM thật · Search/Recommendation/Catalog bằng fixture từng case. Giá và available là snapshot.')
suite=load_suite(); cases={c['id']:c for c in suite['scenarios']}
with st.sidebar:
    source=st.radio('Chế độ',['Evaluation suite','Custom query'],key='input_source')
    model=st.text_input('Model (để trống dùng cấu hình .env)',key='eval_model') or None
    st.caption('LLM dùng provider/key đang cấu hình. Chạy case phát sinh request API.')
    st.caption(f"Suite {suite['version']} · {len(cases)} case · {suite['fingerprint'][:12]}")

if source=='Custom query':
    st.subheader('Chat nhiều lượt với catalog fixture hiện có')
    if st.button('Cuộc hội thoại mới',key='reset_custom'):
        for name in ('custom_store','custom_conversation','custom_messages','custom_state'): st.session_state.pop(name,None)
    for message in st.session_state.get('custom_messages',[]):
        with st.chat_message(message['role']): st.write(message['content'])
    query=st.chat_input('Nhập yêu cầu du lịch',key='custom_chat_input',max_chars=1000)
    if query:
        try:
            if 'custom_store' not in st.session_state:
                st.session_state.custom_store=InMemoryConversationStore()
            clients=FixtureItineraryClients()
            graph=build_graph(tools=ItineraryToolGateway(clients,clients,clients),store=st.session_state.custom_store,llm=get_llm(model=model),llm_timeout_seconds=30)
            state=asyncio.run(graph.ainvoke({'query':query,'conversation_id':st.session_state.get('custom_conversation')}))
            st.session_state.custom_conversation=state.get('conversation_id')
            st.session_state.setdefault('custom_messages',[]).extend([{'role':'user','content':query},{'role':'assistant','content':state.get('response',{})}])
            st.session_state.custom_state=state
            st.rerun()
        except Exception:
            st.error('Không chạy được LLM. Kiểm tra key, model, dependency và kết nối.')
    if st.session_state.get('custom_state'):
        state=st.session_state.custom_state
        st.graphviz_chart(build_graph_dot(build_graph(),state.get('events',[])),width='stretch')
        st.json(state.get('response',{}))
else:
    single,batch=st.tabs(['Chạy từng case','Chạy tất cả'])
    with single:
        case_id=st.selectbox('Case',list(cases),format_func=lambda k:f"{k} · {cases[k]['category']}",key='case_id')
        case=cases[case_id]
        left,right=st.columns(2)
        with left:
            st.write('Input và context'); st.write(case['input_and_context'])
            st.write('Request sẽ gửi'); st.json(case['execution']['turns'])
        with right:
            st.write('Expected extraction'); st.write(case['expected_extraction'])
            st.write('Expected output'); st.write(case['expected_output'])
            st.write('Fail conditions'); st.write(case['fail_conditions'])
        with st.expander('Fixture và phần thiếu bằng chứng'):
            st.json(case['fixtures'],expanded=False)
            for issue in case['execution']['blockers']: st.warning(issue)
            st.caption('Adapter thêm score=1.0 để đáp ứng SearchResponse; detail thiếu mô tả giữ chuỗi rỗng, ngày giữ null. Không thêm sản phẩm/đặc tính.')
        controls=st.columns(3)
        run_case=controls[0].button('Chạy case',key='run_case',type='primary')
        run_turn=controls[1].button('Chạy lượt tiếp theo',key='run_turn')
        reset=controls[2].button('Reset case',key='reset_case')
        signature=(case_id,model,suite['fingerprint'])
        if reset or st.session_state.get('case_signature')!=signature:
            st.session_state.case_signature=signature
            st.session_state.pop('case_session',None); st.session_state.pop('case_result',None)
        live_graph=st.empty()
        if not st.session_state.get('case_result'):
            with live_graph.container():
                show_graph(build_graph(),{})
        if run_case or run_turn:
            try:
                if run_case or 'case_session' not in st.session_state:
                    st.session_state.case_session=CaseSession(case,get_llm(model=model),llm_factory=partial(get_llm,model=model))
                session=st.session_state.case_session
                def update_step(turn_index,snapshot):
                    with live_graph.container():
                        show_graph(session.graph,snapshot['state'],f"Graph — lượt {turn_index+1} · {snapshot['node']}")
                with st.spinner('Đang chạy agent...'):
                    result=asyncio.run(session.run_all(on_step=update_step) if run_case else session.run_next(on_step=update_step))
                st.session_state.case_result=result
                live_graph.empty()
                if result['complete'] or result['error']:
                    persist(make_report([result],suite,session.model))
            except Exception:
                st.error('Không khởi tạo được runner/LLM. Kiểm tra key, model và dependency; không dùng kết quả cũ.')
                st.session_state.pop('case_result',None)
        def review_single(result):
            st.session_state.case_result=result
            persist(make_report([result],suite,st.session_state.case_session.model))
        if st.session_state.get('case_result'): display_result(st.session_state.case_result,'single',review_single)
    with batch:
        st.write(f'Chạy tuần tự {len(cases)} case, mỗi case có store riêng. Case lỗi vẫn tiếp tục case kế tiếp.')
        if st.button(f'Chạy tất cả {len(cases)} case',key='run_all',type='primary'):
            st.session_state.pop('batch_report',None)
            progress=st.progress(0,text='Chuẩn bị'); table=st.empty()
            def update(done,total,results):
                progress.progress(done/total,text=f"{done}/{total} · {results[-1]['id']}: {results[-1]['status']}")
                table.dataframe(rows(results),hide_index=True,width='stretch')
            try:
                report=run_full_evaluation(model=model,progress=update)
                st.session_state.batch_report=report
                persist(report)
            except Exception:
                st.error('Không khởi tạo được batch. Kiểm tra key, model và dependency.')
        report=st.session_state.get('batch_report')
        if report:
            st.write('Tổng hợp'); st.json(report['summary'])
            st.caption('PASS chỉ khi toàn bộ tiêu chí được xác minh. BLOCKED và REVIEW không tính PASS; automatedCheckPassRate chỉ tính các assertion có thể chạy.')
            st.dataframe(rows(report['scenarios']),hide_index=True,width='stretch')
            inspect_id=st.selectbox('Xem lại kết quả đã chạy',[r['id'] for r in report['scenarios']],key='batch_inspect')
            def review_batch(result):
                updated=[result if r['id']==result['id'] else r for r in report['scenarios']]
                refreshed=make_report(updated,suite,report['model'])
                refreshed['reviewOfRunId']=report['runId']
                st.session_state.batch_report=refreshed
                persist(refreshed)
            display_result(next(r for r in report['scenarios'] if r['id']==inspect_id),'batch',review_batch)
    report=st.session_state.get('report')
    if report:
        st.divider()
        st.caption(f"Report {report['runId']} · {report['generatedAt']} · Model: {report['model']}")
        if st.session_state.get('save_error'): st.warning(st.session_state.save_error)
        else: st.caption('Đã lưu: '+st.session_state.get('report_path',''))
        st.download_button('Tải report JSON',json.dumps(report,ensure_ascii=False,indent=2),file_name=f"{report['runId']}.json",mime='application/json')
