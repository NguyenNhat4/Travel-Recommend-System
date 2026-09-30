// @vitest-environment jsdom
import React from 'react';
import { act, cleanup, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useInView } from '../../src/hooks/useInView';

type Callback = (entries: Array<{ isIntersecting: boolean }>) => void;

class FakeObserver {
  static instances: FakeObserver[] = [];
  disconnect = vi.fn();
  observe = vi.fn();
  constructor(public callback: Callback, public options?: IntersectionObserverInit) {
    FakeObserver.instances.push(this);
  }
  emit(isIntersecting: boolean) {
    this.callback([{ isIntersecting }]);
  }
}

function Probe({ once = true }: { once?: boolean }) {
  const [ref, inView] = useInView<HTMLDivElement>({ once });
  return <div ref={ref} data-testid="probe">{inView ? 'in' : 'out'}</div>;
}

describe('useInView', () => {
  beforeEach(() => { FakeObserver.instances = []; });
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it('is false until the element enters the viewport margin, then stays true (once)', () => {
    vi.stubGlobal('IntersectionObserver', FakeObserver);
    render(<Probe />);
    expect(screen.getByTestId('probe').textContent).toBe('out');
    expect(FakeObserver.instances[0].options?.rootMargin).toBe('300px');

    act(() => FakeObserver.instances[0].emit(true));
    expect(screen.getByTestId('probe').textContent).toBe('in');
    expect(FakeObserver.instances[0].disconnect).toHaveBeenCalled();
  });

  it('follows the viewport when once is false', () => {
    vi.stubGlobal('IntersectionObserver', FakeObserver);
    render(<Probe once={false} />);
    act(() => FakeObserver.instances[0].emit(true));
    expect(screen.getByTestId('probe').textContent).toBe('in');
    act(() => FakeObserver.instances[0].emit(false));
    expect(screen.getByTestId('probe').textContent).toBe('out');
  });

  it('treats the element as visible when IntersectionObserver is unavailable', () => {
    vi.stubGlobal('IntersectionObserver', undefined);
    render(<Probe />);
    expect(screen.getByTestId('probe').textContent).toBe('in');
  });
});
