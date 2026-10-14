import {describe,it,expect} from 'vitest';
import {emptyProgress,mergeProgress,type ProgressUpdate} from '../../src/features/itinerary/widget/progressModel';
import {progressView} from '../../src/features/itinerary/widget/widgetProgressView';
import plan from '../../../shared/mocks/itinerary-agent/stream-plan.json';
import explore from '../../../shared/mocks/itinerary-agent/stream-explore-jobs.json';
import fareJob from '../../../shared/mocks/itinerary-agent/stream-fare-job.json';
import fareButton from '../../../shared/mocks/itinerary-agent/stream-fare-button.json';
import clarify from '../../../shared/mocks/itinerary-agent/stream-clarify.json';
import answer from '../../../shared/mocks/itinerary-agent/stream-answer.json';
import blocked from '../../../shared/mocks/itinerary-agent/stream-blocked.json';
const build=(events: typeof plan) => progressView(events.reduce((m,e)=>mergeProgress(m,(e.data as {progress?:ProgressUpdate}).progress),emptyProgress()),undefined,true);
it('explains widened scope, exclusions and requested quantity from the current job',()=>{
 const model=mergeProgress(emptyProgress(),{turnKind:'explore',steps:['understand','search','write'],
  completedStep:'understand',understood:{jobs:[{groupId:'job:1',kind:'attraction',scope:{intent:'more',
   scopeMode:'replace',excludedDestinations:['Vũng Tàu'],requestedCount:10}}]}});
 const text=JSON.stringify(progressView(model));
 expect(text).toContain('bỏ phạm vi thành phố cũ');expect(text).toContain('tìm ở nhiều điểm đến');
 expect(text).toContain('Lượt này không xét Vũng Tàu');expect(text).toContain('Mục tiêu là 10');
});
describe('widget progress',() => {
 it('starts with only the work known to be running',()=>{
  expect(progressView([]).steps.map((s)=>s.status)).toEqual(['active']);
 });
 it('uses four plan steps with real results and notices',()=>{
  const view=build(plan);
  expect(view.steps.map((s)=>s.status)).toEqual(['done','done','done','done']);
  expect(view.summary).toContain('tìm thấy 10');
  expect(view.steps.flatMap((s)=>s.notices).join(' ')).toContain('Bỏ 2');
 });
 it.each([[explore,3],[fareJob,2],[fareButton,2],[clarify,1],[answer,1],[blocked,0]])('uses the steps supplied for the turn',(events,length)=>{
  const view=build(events as typeof plan);expect(view.steps).toHaveLength(length);
  const text=JSON.stringify(view);expect(text).not.toMatch(/internal debug|sourceTotal|query|nodeId/);
 });
 it('does not expose a summary for clarification or small talk',()=>{
  expect(build(clarify as typeof plan).summary).toBe('');expect(build(answer as typeof plan).summary).toBe('');
 });
 it('updates the current activity without repeating understanding on later rounds',()=>{
  const view=progressView(emptyProgress(),{nodeId:'orchestrate',code:'STARTED',round:2});
  expect(view.current).toContain('Đang xem kết quả');
 });
});

it('explains the current Hue job even if an older backend attaches a saved Nha Trang trip',()=>{
 const model=mergeProgress(emptyProgress(),{
  turnKind:'explore',steps:['understand','search','write'],completedStep:'understand',
  understood:{intent:{destination:'Nha Trang',startDate:'2026-10-17',origin:'Nghệ An'},
   jobs:[{groupId:'job:1',kind:'attraction',scope:{destination:'Huế',intent:'more'}}]},
  searches:[{groupId:'job:1',kind:'attraction',status:'ok',scope:{destination:'Huế',intent:'more'},counts:{inScope:50,chosen:3,sourceMore:true}}],
  notices:[{code:'SEEN',groupId:'job:1',kind:'attraction',count:3}],
 });
 const text=JSON.stringify(progressView(model));
 expect(text).not.toContain('Nha Trang');expect(text).not.toContain('17/10');expect(text).not.toContain('Nghệ An');
 expect(text).toContain('Huế');expect(text).toContain('lựa chọn mới');expect(text).toContain('tránh lặp');
});
