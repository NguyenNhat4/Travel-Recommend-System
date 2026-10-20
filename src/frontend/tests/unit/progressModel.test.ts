import {describe,it,expect} from 'vitest';
import {emptyProgress,mergeProgress,type ProgressUpdate} from '../../src/features/itinerary/widget/progressModel';
import explore from '../../../shared/mocks/itinerary-agent/stream-explore-jobs.json';
import fare from '../../../shared/mocks/itinerary-agent/stream-fare-superseded.json';
import {progressView} from '../../src/features/itinerary/widget/widgetProgressView';
function model(events: typeof explore) {return events.reduce((m,e) => mergeProgress(m,(e.data as {progress?:ProgressUpdate}).progress),emptyProgress());}
describe('public progress updates',() => {
 it('replaces cumulative counts and notices rather than adding them',() => {
   const m=model(explore);
   expect(m.searches).toHaveLength(2);
   expect(m.notices?.filter((n)=>n.code==='SEEN')).toHaveLength(1);
   expect(m.notices?.[0].count).toBe(5);
   expect(progressView(m).steps.find((s)=>s.key==='search')?.lines).toHaveLength(2);
 });
 it('hides superseded groups and all notices associated with them',() => {
   const m=model(fare as typeof explore);
   expect(progressView(m).steps.find((s)=>s.key==='search')?.lines).toHaveLength(1);
   expect(progressView(m).steps.flatMap((s)=>s.notices)).toEqual([]);
 });
 it('retains completed steps when the type changes',() => {
   const m=mergeProgress(mergeProgress(emptyProgress(),{turnKind:'explore',steps:['understand','search','write'],completedStep:'search'}),{turnKind:'clarify',steps:['understand']});
   expect(progressView(m).steps.some((s)=>s.key==='search' && s.status==='done')).toBe(true);
 });
});
