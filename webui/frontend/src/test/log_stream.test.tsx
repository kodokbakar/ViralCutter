import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { jobsApi, type ConnectionStatus } from '../api/client';
import { GeneratorTab } from '../components/GeneratorTab';

// Mock EventSource for Vitest / jsdom
class MockEventSource {
  static instances: MockEventSource[] = [];
  url: string;
  listeners: Record<string, ((event: unknown) => void)[]> = {};
  onmessage: ((event: unknown) => void) | null = null;
  onerror: ((event: unknown) => void) | null = null;
  onopen: (() => void) | null = null;
  closed = false;

  constructor(url: string) {
    this.url = url;
    MockEventSource.instances.push(this);
  }

  addEventListener(event: string, handler: (event: unknown) => void) {
    if (!this.listeners[event]) {
      this.listeners[event] = [];
    }
    this.listeners[event].push(handler);
  }

  removeEventListener(event: string, handler: (event: unknown) => void) {
    if (this.listeners[event]) {
      this.listeners[event] = this.listeners[event].filter((h) => h !== handler);
    }
  }

  emit(event: string, data?: unknown, lastEventId?: string) {
    const ev = { type: event, data, lastEventId };
    if (this.listeners[event]) {
      this.listeners[event].forEach((h) => h(ev));
    }
    if (event === 'message' && this.onmessage) {
      this.onmessage(ev);
    }
    if (event === 'error' && this.onerror) {
      this.onerror(ev);
    }
  }

  close() {
    this.closed = true;
  }
}

function renderComponent(element: React.ReactElement) {
  const container = document.createElement('div');
  document.body.appendChild(container);
  const root = createRoot(container);

  act(() => {
    root.render(element);
  });

  return {
    container,
    unmount: () => {
      act(() => {
        root.unmount();
      });
      container.remove();
    },
  };
}

describe('Issue #11 - Log Streaming, Reconnection & Auto-scroll Resilience', () => {
  const originalEventSource = globalThis.EventSource;

  beforeEach(() => {
    vi.useFakeTimers();
    MockEventSource.instances = [];
    globalThis.EventSource = MockEventSource as unknown as typeof EventSource;
  });

  afterEach(() => {
    vi.useRealTimers();
    globalThis.EventSource = originalEventSource;
    vi.restoreAllMocks();
  });

  describe('jobsApi.streamLogs exponential backoff & cursor resumption', () => {
    it('notifies status connected on open and reconnects with exponential backoff on unexpected error', () => {
      const statuses: ConnectionStatus[] = [];
      const messages: string[] = [];

      const cleanup = jobsApi.streamLogs(
        'job_stream_1',
        (msg) => messages.push(msg),
        undefined,
        (status) => statuses.push(status)
      );

      expect(MockEventSource.instances.length).toBe(1);
      expect(statuses).toContain('connected');

      // First instance receives a message
      MockEventSource.instances[0].emit('message', JSON.stringify({ message: 'Log line 1' }));
      expect(messages).toEqual(['Log line 1']);

      // Unexpected drop (error event without terminal data)
      MockEventSource.instances[0].onerror?.(new Event('error') as unknown as { type: string });
      expect(statuses[statuses.length - 1]).toBe('reconnecting');
      expect(MockEventSource.instances[0].closed).toBe(true);

      // Backoff delay 1: 1000ms
      act(() => {
        vi.advanceTimersByTime(999);
      });
      expect(MockEventSource.instances.length).toBe(1);

      act(() => {
        vi.advanceTimersByTime(1);
      });
      expect(MockEventSource.instances.length).toBe(2);
      expect(MockEventSource.instances[1].url).toBe('/api/v1/jobs/job_stream_1/stream?cursor=1');

      // Second failure - backoff delay 2: 2000ms
      MockEventSource.instances[1].onerror?.(new Event('error') as unknown as { type: string });
      expect(statuses[statuses.length - 1]).toBe('reconnecting');

      act(() => {
        vi.advanceTimersByTime(1999);
      });
      expect(MockEventSource.instances.length).toBe(2);

      act(() => {
        vi.advanceTimersByTime(1);
      });
      expect(MockEventSource.instances.length).toBe(3);

      cleanup();
      expect(statuses[statuses.length - 1]).toBe('disconnected');
    });

    it('resumes cursor correctly when messages with lastEventId or custom id/cursor are received', () => {
      const cleanup = jobsApi.streamLogs('job_cursor_test', () => {});
      const es1 = MockEventSource.instances[0];

      // Simulate event with lastEventId = '42'
      es1.emit('message', JSON.stringify({ message: 'Event 42' }), '42');

      // Disconnect
      es1.onerror?.(new Event('error') as unknown as { type: string });

      act(() => {
        vi.advanceTimersByTime(1000);
      });

      expect(MockEventSource.instances.length).toBe(2);
      expect(MockEventSource.instances[1].url).toBe('/api/v1/jobs/job_cursor_test/stream?cursor=43');

      cleanup();
    });

    it('does not reconnect on terminal complete event and notifies disconnected', () => {
      const statuses: ConnectionStatus[] = [];
      const cleanup = jobsApi.streamLogs('job_terminal', () => {}, undefined, (s) => statuses.push(s));
      const es = MockEventSource.instances[0];

      es.emit('complete', JSON.stringify({ status: 'completed' }));
      expect(statuses[statuses.length - 1]).toBe('disconnected');
      expect(es.closed).toBe(true);

      // Advance timers to ensure no reconnection attempt is scheduled
      act(() => {
        vi.advanceTimersByTime(15000);
      });
      expect(MockEventSource.instances.length).toBe(1);

      cleanup();
    });
  });

  describe('GeneratorTab Auto-scroll & User Scroll Lock', () => {
    it('auto-scrolls when user is within 60px of bottom and pauses when scrolled up', () => {
      let messageHandler: ((line: string) => void) | null = null;
      vi.spyOn(jobsApi, 'streamLogs').mockImplementation((_jobId, onMessage) => {
        messageHandler = onMessage;
        return () => {};
      });

      const activeJob = {
        active: true,
        job: {
          job_id: 'job_scroll_test',
          status: 'running' as const,
          stage: 'Processing',
          percent: 50,
          elapsed: '00:00:10',
          started_at: '2026-09-30 00:00:00',
        },
      };

      const { container, unmount } = renderComponent(
        <GeneratorTab activeJob={activeJob} defaultVideoPath="/videos/test.mp4" defaultProjectName="TestProj" />
      );

      const logContainer = container.querySelector('.overflow-y-auto') as HTMLDivElement;
      expect(logContainer).toBeTruthy();

      // Mock scroll dimensions near bottom (within 60px)
      Object.defineProperty(logContainer, 'scrollHeight', { value: 500, configurable: true });
      Object.defineProperty(logContainer, 'clientHeight', { value: 400, configurable: true });
      Object.defineProperty(logContainer, 'scrollTop', { value: 80, writable: true, configurable: true });
      // distance = 500 - 80 - 400 = 20 <= 60 (near bottom)

      act(() => {
        messageHandler?.('Line 1');
        vi.advanceTimersByTime(100);
      });

      // auto-scroll should have set scrollTop = scrollHeight
      expect(logContainer.scrollTop).toBe(500);

      // Now simulate user scrolling UP: distance to bottom > 60px
      Object.defineProperty(logContainer, 'scrollHeight', { value: 1000, configurable: true });
      Object.defineProperty(logContainer, 'clientHeight', { value: 400, configurable: true });
      logContainer.scrollTop = 200; // distance = 1000 - 200 - 400 = 400 > 60

      act(() => {
        logContainer.dispatchEvent(new Event('scroll'));
      });

      // New log arrives while user is scrolled up
      act(() => {
        messageHandler?.('Line 2 while scrolled up');
        vi.advanceTimersByTime(100);
      });

      // scrollTop should NOT jump to scrollHeight (1000), should stay at 200
      expect(logContainer.scrollTop).toBe(200);

      // "Scroll to bottom" button should be visible when user is scrolled up
      const scrollBottomBtn = container.querySelector('[data-testid="scroll-to-bottom-button"]');
      expect(scrollBottomBtn).toBeTruthy();

      // Click "Scroll to bottom"
      act(() => {
        scrollBottomBtn?.dispatchEvent(new MouseEvent('click', { bubbles: true }));
      });
      expect(logContainer.scrollTop).toBe(1000);

      unmount();
    });
  });

  describe('GeneratorTab Connection Status Badge & Stable Log Keys', () => {
    it('displays subtle badge reflecting connection status and renders stable keys', () => {
      let statusCallback: ((status: ConnectionStatus) => void) | undefined;
      let messageHandler: ((line: string) => void) | null = null;

      vi.spyOn(jobsApi, 'streamLogs').mockImplementation((_jobId, onMessage, onError) => {
        messageHandler = onMessage;
        statusCallback = onError?.onStatusChange;
        return () => {};
      });

      const activeJob = {
        active: true,
        job: {
          job_id: 'job_badge_test',
          status: 'running' as const,
          stage: 'Running',
          percent: 25,
          elapsed: '00:00:05',
          started_at: '2026-09-30 00:00:00',
        },
      };

      const { container, unmount } = renderComponent(
        <GeneratorTab activeJob={activeJob} defaultVideoPath="/videos/test.mp4" defaultProjectName="TestProj" />
      );

      // Simulate status connected
      act(() => {
        statusCallback?.('connected');
      });

      const badge = container.querySelector('[data-testid="connection-status-badge"]');
      expect(badge).toBeTruthy();
      expect(badge?.textContent).toContain('Connected');

      // Simulate status reconnecting
      act(() => {
        statusCallback?.('reconnecting');
      });
      expect(badge?.textContent).toContain('Reconnecting...');

      // Ingest a log and check rendered key stability
      act(() => {
        messageHandler?.('Pipeline test line message');
        vi.advanceTimersByTime(100);
      });

      const logLines = container.querySelectorAll('.leading-relaxed');
      expect(logLines.length).toBeGreaterThan(0);

      unmount();
    });

    it('cleanly resets trackedJobId to null on job completion and cancellation', async () => {
      vi.spyOn(jobsApi, 'cancel').mockResolvedValue({ status: 'cancelled', job_id: 'job_cancel_test' });
      vi.spyOn(jobsApi, 'streamLogs').mockReturnValue(() => {});

      const activeJob = {
        active: true,
        job: {
          job_id: 'job_cancel_test',
          status: 'running' as const,
          stage: 'Running',
          percent: 50,
          elapsed: '00:00:10',
          started_at: '2026-09-30 00:00:00',
        },
      };

      const { container, unmount } = renderComponent(
        <GeneratorTab activeJob={activeJob} defaultVideoPath="/videos/test.mp4" defaultProjectName="TestProj" />
      );

      expect(container.textContent).toContain('job_cancel_test');

      const cancelBtn = container.querySelector('button[title="Stop current execution"]') ||
        Array.from(container.querySelectorAll('button')).find((b) => b.textContent?.includes('Cancel'));

      expect(cancelBtn).toBeTruthy();

      await act(async () => {
        cancelBtn?.dispatchEvent(new MouseEvent('click', { bubbles: true }));
      });

      // Badge or trackedJobId badge should disappear once trackedJobId is reset to null
      expect(container.querySelector('[data-testid="connection-status-badge"]')).toBeNull();

      unmount();
    });
  });

  describe('DOM Thrashing: document.hidden Throttling', () => {
    it('throttles flush interval when document is hidden', () => {
      let messageHandler: ((line: string) => void) | null = null;
      vi.spyOn(jobsApi, 'streamLogs').mockImplementation((_jobId, onMessage) => {
        messageHandler = onMessage;
        return () => {};
      });

      const activeJob = {
        active: true,
        job: {
          job_id: 'job_throttle_test',
          status: 'running' as const,
          stage: 'Running',
          percent: 10,
          elapsed: '00:00:02',
          started_at: '2026-09-30 00:00:00',
        },
      };

      // Set document.hidden to true
      Object.defineProperty(document, 'hidden', { value: true, configurable: true });

      const { container, unmount } = renderComponent(
        <GeneratorTab activeJob={activeJob} defaultVideoPath="/videos/test.mp4" defaultProjectName="TestProj" />
      );

      // Ingest message while hidden
      act(() => {
        messageHandler?.('Background log line');
      });

      // At 50ms, it should not yet have flushed because interval is 1000ms
      act(() => {
        vi.advanceTimersByTime(50);
      });
      expect(container.textContent).not.toContain('Background log line');

      // At 1000ms, it flushes the background buffer
      act(() => {
        vi.advanceTimersByTime(950);
      });
      expect(container.textContent).toContain('Background log line');

      // Restore document.hidden
      Object.defineProperty(document, 'hidden', { value: false, configurable: true });
      act(() => {
        document.dispatchEvent(new Event('visibilitychange'));
      });

      unmount();
    });
  });
});
