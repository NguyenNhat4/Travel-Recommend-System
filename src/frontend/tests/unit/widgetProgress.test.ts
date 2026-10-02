import { describe, expect, it } from 'vitest';
import { progressView } from '../../src/features/itinerary/widget/widgetProgress';

const done = (...nodes: string[]) => nodes.map((nodeId, index) => ({ sequence: index + 1, nodeId, message: `debug ${nodeId}` }));
const statuses = (nodes: string[]) => progressView(done(...nodes)).steps.map((step) => step.status);

describe('widget progress', () => {
  it('starts on understanding the request before any node finishes', () => {
    const view = progressView([]);
    expect(view.steps.map((step) => step.status)).toEqual(['active', 'pending', 'pending']);
    expect(view.current).toBe('Đang hiểu yêu cầu của bạn…');
  });

  it('ticks steps only from real completed nodes', () => {
    expect(statuses(['intake', 'classify'])).toEqual(['active', 'pending', 'pending']);
    expect(statuses(['intake', 'classify', 'extract'])).toEqual(['done', 'active', 'pending']);
    expect(statuses(['intake', 'classify', 'extract', 'tool'])).toEqual(['done', 'active', 'pending']);
    expect(statuses(['intake', 'classify', 'extract', 'tool', 'evaluate'])).toEqual(['done', 'done', 'active']);
  });

  it('shows the narration sub-step after compose', () => {
    const view = progressView(done('intake', 'classify', 'extract', 'tool', 'evaluate', 'compose'));
    expect(view.steps.map((step) => step.status)).toEqual(['done', 'done', 'active']);
    expect(view.steps[2].label).toBe('Đang viết lời tư vấn…');
    expect(view.current).toBe('Đang viết lời tư vấn…');
  });

  it('reopens the search step when evaluate asks for a retry', () => {
    const view = progressView(done('intake', 'classify', 'extract', 'tool', 'evaluate', 'retry'));
    expect(view.steps.map((step) => step.status)).toEqual(['done', 'active', 'pending']);
    expect(view.steps[1].label).toBe('Đang thử phương án khác…');
  });

  it('does not fake ticks on the chat or clarify branches', () => {
    expect(statuses(['intake', 'classify', 'converse', 'finalize'])).toEqual(['active', 'pending', 'pending']);
  });

  it('never surfaces backend debug messages', () => {
    const view = progressView([
      { nodeId: 'intake', message: 'request initialized' },
      { nodeId: 'classify', message: 'route travel (intent override)' },
      { nodeId: 'extract', message: 'normalized destination' },
    ]);
    const text = [view.current, ...view.steps.map((step) => step.label)].join(' ');
    expect(text).not.toMatch(/request initialized|route travel|normalized/);
  });
});
