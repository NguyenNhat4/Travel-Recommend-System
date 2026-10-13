// @vitest-environment jsdom
import React from 'react';
import {render,screen,fireEvent,cleanup} from '@testing-library/react';
import {it,expect,vi,afterEach} from 'vitest';
import {createInitialAssistantState} from '../../src/context/assistantState';
const mocks=vi.hoisted(()=>({debugMode:true}));
vi.mock('../../src/context/TravelContext',()=>({useTravel:()=>({...mocks,toggleDebugMode:vi.fn(),activeEvents:[],bookings:[],cartCount:0})}));
vi.mock('../../src/context/AssistantProvider',()=>({useAssistant:()=>({state:{...createInitialAssistantState(),run:{runId:'r',requestId:'request-example',startedAt:0},progress:[{nodeId:'run_jobs',durationMs:42}],activities:[]}})}));
vi.mock('../../src/services/recsys',()=>({fetchRecommendations:()=>new Promise(()=>{})}));
import {DebugPanel} from '../../src/components/common/DebugPanel';
afterEach(cleanup);
it('exposes the request and timing only when diagnostics is open',()=>{
  mocks.debugMode=true;render(<DebugPanel />);
  expect(screen.queryByRole('region',{name:'Trợ lý — lượt gần nhất'})).toBeNull();
  fireEvent.click(screen.getByText('DIAGNOSTICS / CHẨN ĐOÁN'));
  expect(screen.getByRole('region',{name:'Trợ lý — lượt gần nhất'})).toBeTruthy();
  expect(screen.getAllByText('42')).toHaveLength(2);
  expect(screen.getByRole('button',{name:'Sao chép requestId'})).toBeTruthy();
});
it('keeps assistant diagnostics hidden when debug mode is off',()=>{
  mocks.debugMode=false;render(<DebugPanel />);
  expect(screen.queryByText('request-example')).toBeNull();
  expect(screen.queryByRole('region',{name:'Trợ lý — lượt gần nhất'})).toBeNull();
});
