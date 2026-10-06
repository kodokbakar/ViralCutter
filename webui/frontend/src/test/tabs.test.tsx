import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { GeneratorTab } from '../components/GeneratorTab';
import { SubtitlesTab } from '../components/SubtitlesTab';
import { WatermarkTab } from '../components/WatermarkTab';
import { SubtitleEditorTab } from '../components/SubtitleEditorTab';
import { LibraryTab } from '../components/LibraryTab';
import { GDriveTab } from '../components/GDriveTab';
import { DiagnosticsTab } from '../components/DiagnosticsTab';
import { Navbar } from '../components/Navbar';
import { jobsApi, gdriveApi, libraryApi, subtitlesApi, systemApi, uploadApi, previewApi } from '../api/client';
import type { ActiveJobResponse, SystemStatusResponse } from '../api/types';

// Mock EventSource for jsdom environment
class MockEventSource {
  static instances: MockEventSource[] = [];
  url: string;
  listeners: Record<string, ((event: unknown) => void)[]> = {};
  onmessage: ((event: unknown) => void) | null = null;
  onerror: ((event: unknown) => void) | null = null;
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

  close() {
    this.closed = true;
  }
}

// Helper to set input values triggering React synthetic events
function setNativeValue(element: HTMLElement, value: string) {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const tracker = (element as any)._valueTracker;
  if (tracker) {
    tracker.setValue('__force_change__');
  }
  let prototype = Object.getPrototypeOf(element);
  while (prototype && !Object.prototype.hasOwnProperty.call(prototype, 'value')) {
    prototype = Object.getPrototypeOf(prototype);
  }
  const descriptor = prototype ? Object.getOwnPropertyDescriptor(prototype, 'value') : null;
  if (descriptor?.set) {
    descriptor.set.call(element, value);
  } else {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (element as any).value = value;
  }
  element.dispatchEvent(new Event('input', { bubbles: true }));
  element.dispatchEvent(new Event('change', { bubbles: true }));
}

// Helper to render component into DOM
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

describe('Phase 4 Frontend Tabs & Job Workflow Integration', () => {
  const originalEventSource = globalThis.EventSource;

  beforeEach(() => {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;
    MockEventSource.instances = [];
    globalThis.EventSource = MockEventSource as unknown as typeof EventSource;
    vi.restoreAllMocks();
    document.body.textContent = '';
    if (typeof localStorage !== 'undefined' && localStorage.clear) {
      localStorage.clear();
    }
  });

  afterEach(() => {
    globalThis.EventSource = originalEventSource;
    vi.restoreAllMocks();
    document.body.textContent = '';
    if (typeof localStorage !== 'undefined' && localStorage.clear) {
      localStorage.clear();
    }
  });

  // -------------------------------------------------------------
  // 1. GeneratorTab
  // -------------------------------------------------------------
  describe('GeneratorTab', () => {
    it('renders parameter controls and file selection inputs', () => {
      const { container, unmount } = renderComponent(
        <GeneratorTab defaultVideoPath="/videos/sample.mp4" defaultProjectName="SampleProj" />
      );

      // Verify Preset select
      const presetSelect = container.querySelector('#generator-preset-select') as HTMLSelectElement;
      expect(presetSelect).toBeTruthy();
      expect(presetSelect.value).toBe('viral_shorts');

      // Verify Target Duration slider
      const durationInput = container.querySelector('#target-duration-input') as HTMLInputElement;
      expect(durationInput).toBeTruthy();
      expect(durationInput.value).toBe('60');

      // Verify Orientation select
      const orientationSelect = container.querySelector('#orientation-select') as HTMLSelectElement;
      expect(orientationSelect).toBeTruthy();
      expect(orientationSelect.value).toBe('9:16');

      // Verify Whisper Model select
      const modelSelect = container.querySelector('#whisper-model-select') as HTMLSelectElement;
      expect(modelSelect).toBeTruthy();
      expect(modelSelect.value).toBe('large-v3-turbo');

      // Verify Run button
      const runBtn = container.querySelector('[data-testid="run-job-button"]');
      expect(runBtn).toBeTruthy();

      unmount();
    });

    it('submits job request with correct parameters and connects to stream', async () => {
      const runMock = vi.spyOn(jobsApi, 'run').mockResolvedValue({
        job_id: 'job_gen_999',
        status: 'started',
      });
      const streamMock = vi.spyOn(jobsApi, 'streamLogs').mockReturnValue(() => {});

      const { container, unmount } = renderComponent(
        <GeneratorTab defaultVideoPath="/videos/sample.mp4" defaultProjectName="SampleProj" />
      );

      // Select preset fast
      const presetSelect = container.querySelector('#generator-preset-select') as HTMLSelectElement;
      act(() => {
        setNativeValue(presetSelect, 'fast');
      });

      // Submit form
      const form = container.querySelector('form');
      await act(async () => {
        form?.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
      });

      expect(runMock).toHaveBeenCalledWith(
        expect.objectContaining({
          video_path: '/videos/sample.mp4',
          project_name: 'SampleProj',
          model: 'tiny',
          workflow: '2',
          whisper_preset: 'fast',
          max_duration: 30,
        })
      );

      expect(streamMock).toHaveBeenCalledWith('job_gen_999', expect.any(Function), expect.any(Function));

      unmount();
    });

    it('renders whisper tuning inputs and includes batch and chunk size in run request', async () => {
      const runMock = vi.spyOn(jobsApi, 'run').mockResolvedValue({
        job_id: 'job_gen_whisper',
        status: 'started',
      });
      vi.spyOn(jobsApi, 'streamLogs').mockReturnValue(() => {});

      const { container, unmount } = renderComponent(
        <GeneratorTab defaultVideoPath="/videos/sample.mp4" defaultProjectName="SampleProj" />
      );

      const batchInput = container.querySelector('#whisper-batch-size-input') as HTMLInputElement;
      const chunkInput = container.querySelector('#whisper-chunk-size-input') as HTMLInputElement;
      expect(batchInput).toBeTruthy();
      expect(chunkInput).toBeTruthy();
      expect(batchInput.value).toBe('8');
      expect(chunkInput.value).toBe('10');

      act(() => {
        setNativeValue(batchInput, '16');
        setNativeValue(chunkInput, '20');
      });

      const form = container.querySelector('form');
      await act(async () => {
        form?.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
      });

      expect(runMock).toHaveBeenCalledWith(
        expect.objectContaining({
          whisper_batch_size: 16,
          whisper_chunk_size: 20,
        })
      );

      unmount();
    });

    it('handles AI backend configuration and includes fields in run request', async () => {
      const runMock = vi.spyOn(jobsApi, 'run').mockResolvedValue({
        job_id: 'job_gen_custom_ai',
        status: 'started',
      });
      vi.spyOn(jobsApi, 'streamLogs').mockReturnValue(() => {});

      const { container, unmount } = renderComponent(
        <GeneratorTab defaultVideoPath="/videos/sample.mp4" defaultProjectName="SampleProj" />
      );

      const aiBackendSelect = container.querySelector('#ai-backend-select') as HTMLSelectElement;
      expect(aiBackendSelect).toBeTruthy();
      expect(aiBackendSelect.value).toBe('gemini');

      // Change backend to custom
      act(() => {
        setNativeValue(aiBackendSelect, 'custom');
      });

      const apiKeyInput = container.querySelector('#api-key-input') as HTMLInputElement;
      const modelInput = container.querySelector('#ai-model-input') as HTMLInputElement;
      const baseUrlInput = container.querySelector('#ai-base-url-input') as HTMLInputElement;

      expect(apiKeyInput).toBeTruthy();
      expect(modelInput).toBeTruthy();
      expect(baseUrlInput).toBeTruthy();

      act(() => {
        setNativeValue(apiKeyInput, 'sk-test-key');
        setNativeValue(modelInput, 'gpt-4o-mini');
        setNativeValue(baseUrlInput, 'https://api.openai.com/v1');
      });

      const form = container.querySelector('form');
      await act(async () => {
        form?.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
      });

      expect(runMock).toHaveBeenCalledWith(
        expect.objectContaining({
          ai_backend: 'custom',
          api_key: 'sk-test-key',
          ai_model_name: 'gpt-4o-mini',
          ai_base_url: 'https://api.openai.com/v1',
        })
      );

      unmount();
    });

    it('auto-suggests chunk size based on AI backend and allows manual edit', async () => {
      const runMock = vi.spyOn(jobsApi, 'run').mockResolvedValue({
        job_id: 'job_gen_chunk_test',
        status: 'started',
      });
      vi.spyOn(jobsApi, 'streamLogs').mockReturnValue(() => {});

      const { container, unmount } = renderComponent(
        <GeneratorTab defaultVideoPath="/videos/sample.mp4" defaultProjectName="SampleProj" />
      );

      const aiBackendSelect = container.querySelector('#ai-backend-select') as HTMLSelectElement;
      const chunkSizeInput = container.querySelector('#ai-chunk-size-input') as HTMLInputElement;

      // Default backend is gemini -> 70000
      expect(chunkSizeInput.value).toBe('70000');

      // Change to custom -> auto-suggests 40000
      act(() => {
        setNativeValue(aiBackendSelect, 'custom');
      });
      expect(chunkSizeInput.value).toBe('40000');

      // Change to local -> auto-suggests 30000
      act(() => {
        setNativeValue(aiBackendSelect, 'local');
      });
      expect(chunkSizeInput.value).toBe('30000');

      // Manual edit to 50000
      act(() => {
        setNativeValue(chunkSizeInput, '50000');
      });
      expect(chunkSizeInput.value).toBe('50000');

      const form = container.querySelector('form');
      await act(async () => {
        form?.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
      });

      expect(runMock).toHaveBeenCalledWith(
        expect.objectContaining({
          ai_backend: 'local',
          chunk_size: 50000,
        })
      );

      unmount();
    });

    it('pre-injects default prompt template from server and allows reset to default', async () => {
      const defaultTemplateText = 'Default Prompt: {transcript_chunk} {json_template}';
      const promptMock = vi.spyOn(systemApi, 'getPromptTemplate').mockResolvedValue({
        template: defaultTemplateText,
      });

      const { container, unmount } = renderComponent(
        <GeneratorTab defaultVideoPath="/videos/sample.mp4" defaultProjectName="SampleProj" />
      );

      // Allow useEffect to resolve getPromptTemplate
      await act(async () => {
        await Promise.resolve();
      });

      expect(promptMock).toHaveBeenCalled();

      // Open AI Prompt Template editor
      const toggleEditorBtn = Array.from(container.querySelectorAll('button')).find((b) =>
        b.textContent?.includes('AI Prompt Template')
      );
      expect(toggleEditorBtn).toBeTruthy();
      act(() => {
        toggleEditorBtn?.click();
      });

      const textarea = container.querySelector('#ai-prompt-template-textarea') as HTMLTextAreaElement;
      expect(textarea).toBeTruthy();
      expect(textarea.value).toBe(defaultTemplateText);
      expect(container.textContent).toContain('Default Template');

      // Edit prompt template
      act(() => {
        setNativeValue(textarea, 'Custom prompt for test');
      });
      expect(textarea.value).toBe('Custom prompt for test');
      expect(container.textContent).toContain('Custom Active');

      // Click Reset to Default
      const resetBtn = container.querySelector('#reset-prompt-template-btn') as HTMLButtonElement;
      expect(resetBtn).toBeTruthy();
      await act(async () => {
        resetBtn.click();
        await Promise.resolve();
      });

      expect(textarea.value).toBe(defaultTemplateText);
      expect(container.textContent).toContain('Default Template');

      unmount();
    });

    it('displays active job status banner and supports cancellation', async () => {
      const cancelMock = vi.spyOn(jobsApi, 'cancel').mockResolvedValue({
        status: 'cancelled',
        job_id: 'job_active_123',
      });

      const mockActive: ActiveJobResponse = {
        active: true,
        job: {
          job_id: 'job_active_123',
          status: 'running',
          stage: 'TRANSCRIBING',
          percent: 45,
          elapsed: '00:01:10',
        },
      };

      const refreshMock = vi.fn();
      const { container, unmount } = renderComponent(
        <GeneratorTab activeJob={mockActive} onRefreshActiveJob={refreshMock} />
      );

      // Banner should be visible
      expect(container.textContent).toContain('Active Job:');
      expect(container.textContent).toContain('job_active_123');
      expect(container.textContent).toContain('TRANSCRIBING');
      expect(container.textContent).toContain('45%');

      // Click Cancel
      const cancelBtn = Array.from(container.querySelectorAll('button')).find((b) =>
        b.textContent?.includes('Cancel Job')
      );
      expect(cancelBtn).toBeTruthy();

      await act(async () => {
        cancelBtn?.click();
      });

      expect(cancelMock).toHaveBeenCalledWith('job_active_123');
      expect(refreshMock).toHaveBeenCalled();

      unmount();
    });

    it('triggers AI connection test via Test Connection button', async () => {
      const testAiMock = vi.spyOn(systemApi, 'testAi').mockResolvedValue({
        success: true,
        message: 'AI Provider is ready',
        latency_ms: 120,
      });

      const { container, unmount } = renderComponent(<GeneratorTab />);

      const testBtn = container.querySelector('[data-testid="test-ai-button"]') as HTMLButtonElement;
      expect(testBtn).toBeTruthy();

      await act(async () => {
        testBtn.click();
      });

      expect(testAiMock).toHaveBeenCalled();
      expect(container.textContent).toContain('AI Provider is ready');
      expect(container.textContent).toContain('120ms');

      unmount();
    });

    it('sets workflow to 2 when burn subtitles toggle is unchecked', async () => {
      const runMock = vi.spyOn(jobsApi, 'run').mockResolvedValue({
        job_id: 'job_noburn_123',
        status: 'queued',
        message: 'Job submitted',
      });

      const { container, unmount } = renderComponent(
        <GeneratorTab defaultVideoPath="/videos/test.mp4" />
      );

      const burnToggle = container.querySelector('#burn-subtitles-toggle') as HTMLInputElement;
      expect(burnToggle).toBeTruthy();
      expect(burnToggle.checked).toBe(true);

      act(() => {
        burnToggle.click();
      });

      const form = container.querySelector('form');
      await act(async () => {
        form?.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
      });

      expect(runMock).toHaveBeenCalledWith(
        expect.objectContaining({
          workflow: '2',
        })
      );

      unmount();
    });

    it('ingests stream logs via timer flusher and ignores ping comments', async () => {
      let onMessageCallback: (line: string) => void = () => {};
      vi.spyOn(jobsApi, 'streamLogs').mockImplementation((_jobId, onMessage) => {
        onMessageCallback = onMessage;
        return () => {};
      });

      const activeJob = {
        active: true,
        job: {
          job_id: 'job_timer_test',
          status: 'running' as const,
          stage: 'Downloading',
          percent: 10,
          elapsed: '00:00:05',
          started_at: '2026-09-30 00:00:00',
        },
      };

      const { container, unmount } = renderComponent(
        <GeneratorTab activeJob={activeJob} />
      );

      // Simulate stream messages: a ping and a real log
      act(() => {
        onMessageCallback(': ping');
        onMessageCallback('[Pipeline] Processing step 1');
      });

      const logText = container.textContent || '';
      expect(logText).toContain('[Pipeline] Processing step 1');
      expect(logText).not.toContain(': ping');

      unmount();
    });

    it('relocates generator preview below controls and log console with full-width isolated output view', async () => {
      const { container, unmount } = renderComponent(
        <GeneratorTab defaultVideoPath="/videos/test.mp4" defaultProjectName="TestProj" />
      );

      const previewSection = container.querySelector('[data-testid="generator-output-preview"]');
      expect(previewSection).toBeTruthy();
      expect(previewSection?.className).toContain('w-full');

      // Verify that controls and execution log stream exist before preview section in DOM order
      const form = container.querySelector('form');
      const logHeader = Array.from(container.querySelectorAll('span')).find((s) =>
        s.textContent?.includes('Execution Log Stream')
      );
      expect(form).toBeTruthy();
      expect(logHeader).toBeTruthy();

      // previewSection should come after form and log console in DOM
      expect(Boolean(form?.compareDocumentPosition(previewSection!)! & Node.DOCUMENT_POSITION_FOLLOWING)).toBe(true);
      expect(Boolean(logHeader?.compareDocumentPosition(previewSection!)! & Node.DOCUMENT_POSITION_FOLLOWING)).toBe(true);

      // Verify isolation: NO input video elements, file inputs, or upload dropzones inside preview section
      expect(previewSection?.querySelector('input[type="file"]')).toBeNull();
      expect(previewSection?.querySelector('input[type="url"]')).toBeNull();
      expect(previewSection?.textContent).not.toContain('Video Source');
      expect(previewSection?.textContent).not.toContain('Click to select or drop video file');

      // Empty state verification
      expect(previewSection?.textContent).toContain('No generated video clips available yet');

      unmount();
    });

    it('renders isolated preview player and clip list when completed clips are fetched', async () => {
      const mockClips = [
        { name: 'clip_01.mp4', path: '/virals/TestProj/burned_sub/clip_01.mp4', size: 1048576, modified_at: 1700000000, asset_type: 'video' },
        { name: 'clip_02.mp4', path: '/virals/TestProj/burned_sub/clip_02.mp4', size: 2097152, modified_at: 1700000010, asset_type: 'video' },
      ];
      vi.spyOn(libraryApi, 'listAssets').mockResolvedValue(mockClips);
      const navigateMock = vi.fn();

      const { container, unmount } = renderComponent(
        <GeneratorTab
          defaultVideoPath="/videos/test.mp4"
          defaultProjectName="TestProj"
          onNavigateTab={navigateMock}
        />
      );

      // Click Refresh Clips button to trigger fetch
      const refreshBtn = Array.from(container.querySelectorAll('button')).find((b) =>
        b.textContent?.includes('Refresh Clips')
      );
      expect(refreshBtn).toBeTruthy();

      await act(async () => {
        refreshBtn?.click();
      });

      const previewSection = container.querySelector('[data-testid="generator-output-preview"]');
      expect(previewSection).toBeTruthy();

      // Video player should be rendered with first clip
      const videoEl = previewSection?.querySelector('video');
      expect(videoEl).toBeTruthy();
      expect(videoEl?.getAttribute('src')).toBe(previewApi.getVideoUrl('/virals/TestProj/burned_sub/clip_01.mp4'));

      // Check clip metadata and actions
      expect(previewSection?.textContent).toContain('clip_01.mp4');
      expect(previewSection?.textContent).toContain('Isolated Output Preview');
      expect(previewSection?.textContent).toContain('Download MP4');
      expect(previewSection?.textContent).toContain('Subtitle Editor');
      expect(previewSection?.textContent).toContain('Export to Google Drive');

      // Check Subtitle Editor navigation
      const subEditorBtn = Array.from(previewSection?.querySelectorAll('button') || []).find((b) =>
        b.textContent?.includes('Subtitle Editor')
      );
      expect(subEditorBtn).toBeTruthy();
      act(() => {
        subEditorBtn?.click();
      });
      expect(navigateMock).toHaveBeenCalledWith('subtitle-editor', 'TestProj');

      // Switch to clip_02
      const clip2Btn = Array.from(previewSection?.querySelectorAll('button') || []).find((b) =>
        b.textContent?.includes('clip_02.mp4')
      );
      expect(clip2Btn).toBeTruthy();
      act(() => {
        clip2Btn?.click();
      });

      const updatedVideo = previewSection?.querySelector('video');
      expect(updatedVideo?.getAttribute('src')).toBe(previewApi.getVideoUrl('/virals/TestProj/burned_sub/clip_02.mp4'));

      unmount();
    });

    it('renders burned_sub clips with AI score badge and hook title from getProjectClips', async () => {
      const mockGeneratedClips = [
        {
          name: '000_ClipAlpha_subtitled.mp4',
          path: '/virals/TestProj/burned_sub/000_ClipAlpha_subtitled.mp4',
          size: 1048576,
          folder_type: 'burned_sub' as const,
          score: 95,
          hook_title: 'VIRAL HOOK TITLE',
          duration: 35,
        },
        {
          name: '001_ClipBeta_subtitled.mp4',
          path: '/virals/TestProj/burned_sub/001_ClipBeta_subtitled.mp4',
          size: 2097152,
          folder_type: 'burned_sub' as const,
          score: 75,
          hook_title: 'ANOTHER HOOK',
          duration: 40,
        },
      ];
      vi.spyOn(libraryApi, 'getProjectClips').mockResolvedValue(mockGeneratedClips);

      const { container, unmount } = renderComponent(
        <GeneratorTab
          defaultVideoPath="/videos/test.mp4"
          defaultProjectName="TestProj"
        />
      );

      const refreshBtn = Array.from(container.querySelectorAll('button')).find((b) =>
        b.textContent?.includes('Refresh Clips')
      );
      expect(refreshBtn).toBeTruthy();

      await act(async () => {
        refreshBtn?.click();
      });

      const previewSection = container.querySelector('[data-testid="generator-output-preview"]');
      expect(previewSection).toBeTruthy();

      // Check folder type badge
      expect(previewSection?.textContent).toContain('Burned Subtitles (Ready to Post)');

      // Check hook title
      expect(previewSection?.textContent).toContain('VIRAL HOOK TITLE');

      // Check AI score badges
      const selectedScore = previewSection?.querySelector('[data-testid="selected-clip-score"]');
      expect(selectedScore?.textContent).toBe('Score: 95');

      const clipScoreBadges = previewSection?.querySelectorAll('[data-testid="clip-score-badge"]');
      expect(clipScoreBadges?.length).toBe(2);
      expect(clipScoreBadges?.[0]?.textContent).toBe('Score: 95');
      expect(clipScoreBadges?.[1]?.textContent).toBe('Score: 75');

      unmount();
    });

    it('renders hook title overlay controls and includes them in run request', async () => {
      const runMock = vi.spyOn(jobsApi, 'run').mockResolvedValue({
        job_id: 'job_hook_test',
        status: 'started',
      });
      vi.spyOn(jobsApi, 'streamLogs').mockReturnValue(() => {});

      const { container, unmount } = renderComponent(
        <GeneratorTab defaultVideoPath="/videos/test.mp4" defaultProjectName="TestProj" />
      );

      // Verify Hook Title Overlay toggle is present and checked by default
      const hookToggle = container.querySelector('#hook-header-toggle') as HTMLInputElement;
      expect(hookToggle).toBeTruthy();
      expect(hookToggle.checked).toBe(true);

      // Verify Hook Style select is present with default yellow_box
      const hookStyleSelect = container.querySelector('#hook-header-style-select') as HTMLSelectElement;
      expect(hookStyleSelect).toBeTruthy();
      expect(hookStyleSelect.value).toBe('yellow_box');

      // Change style to neon
      act(() => {
        setNativeValue(hookStyleSelect, 'neon');
      });

      // Submit form
      const form = container.querySelector('form');
      await act(async () => {
        form?.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
      });

      expect(runMock).toHaveBeenCalledWith(
        expect.objectContaining({
          enable_hook_header: true,
          hook_header_style: 'neon',
        })
      );

      // Toggle hook header off and verify style select is hidden
      act(() => {
        hookToggle.click();
      });
      expect(hookToggle.checked).toBe(false);
      expect(container.querySelector('#hook-header-style-select')).toBeNull();

      // Submit form again
      await act(async () => {
        form?.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
      });

      expect(runMock).toHaveBeenCalledWith(
        expect.objectContaining({
          enable_hook_header: false,
        })
      );

      unmount();
    });
  });

  // -------------------------------------------------------------
  // 2. SubtitlesTab
  // -------------------------------------------------------------
  describe('SubtitlesTab', () => {
    it('renders subtitle generation parameters and triggers task submission', async () => {
      const runMock = vi.spyOn(jobsApi, 'run').mockResolvedValue({
        job_id: 'job_sub_777',
        status: 'started',
      });
      const streamMock = vi.spyOn(jobsApi, 'streamLogs').mockReturnValue(() => {});

      const { container, unmount } = renderComponent(
        <SubtitlesTab defaultVideoPath="/videos/lecture.mp4" defaultProjectName="Lecture01" />
      );

      const modelSelect = container.querySelector('#subtitles-whisper-model') as HTMLSelectElement;
      const langSelect = container.querySelector('#subtitles-language') as HTMLSelectElement;
      const promptInput = container.querySelector('#subtitles-prompt') as HTMLTextAreaElement;

      expect(modelSelect).toBeTruthy();
      expect(langSelect).toBeTruthy();
      expect(promptInput).toBeTruthy();

      // Configure parameters using setNativeValue
      act(() => {
        setNativeValue(modelSelect, 'medium');
        setNativeValue(langSelect, 'pt');
        setNativeValue(promptInput, 'Artificial Intelligence, PyTorch');
      });

      // Submit
      const form = container.querySelector('form');
      await act(async () => {
        form?.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
      });

      expect(runMock).toHaveBeenCalledWith(
        expect.objectContaining({
          workflow: '3',
          video_path: '/videos/lecture.mp4',
          project_name: 'Lecture01',
          model: 'medium',
          language: 'pt',
          prompt_template: 'Artificial Intelligence, PyTorch',
        })
      );

      expect(streamMock).toHaveBeenCalledWith('job_sub_777', expect.any(Function), expect.any(Function));

      unmount();
    });

    it('triggers subtitle preview on video via Preview on Video button', async () => {
      const previewVideoMock = vi.spyOn(previewApi, 'previewSubtitleVideo').mockResolvedValue({
        preview_url: '/api/v1/preview/video?path=%2Ftmp%2Ftest_preview.mp4',
        file_path: '/tmp/test_preview.mp4',
      });

      const { container, unmount } = renderComponent(
        <SubtitlesTab defaultVideoPath="/videos/lecture.mp4" />
      );

      const previewBtn = Array.from(container.querySelectorAll('button')).find((b) =>
        b.textContent?.includes('Preview on Video')
      );
      expect(previewBtn).toBeTruthy();

      await act(async () => {
        previewBtn?.click();
      });

      expect(previewVideoMock).toHaveBeenCalledWith(
        expect.objectContaining({
          video_path: '/videos/lecture.mp4',
          duration: 3.0,
        })
      );

      expect(container.textContent).toContain('Subtitle Video Preview (3s Loop)');
      const videoEl = container.querySelector('video');
      expect(videoEl).toBeTruthy();
      expect(videoEl?.getAttribute('src')).toBe('/api/v1/preview/video?path=%2Ftmp%2Ftest_preview.mp4');

      unmount();
    });
  });

  // -------------------------------------------------------------
  // 3. WatermarkTab
  // -------------------------------------------------------------
  describe('WatermarkTab', () => {
    it('renders positioning grid, sliders, and preview overlay', () => {
      const { container, unmount } = renderComponent(
        <WatermarkTab defaultVideoPath="/videos/clip.mp4" defaultProjectName="ClipProj" />
      );

      // Verify position buttons
      expect(container.textContent).toContain('Top-Left');
      expect(container.textContent).toContain('Top-Right');
      expect(container.textContent).toContain('Center');
      expect(container.textContent).toContain('Bottom-Right');

      // Verify sliders
      const opacitySlider = container.querySelector('#watermark-opacity-slider') as HTMLInputElement;
      const scaleSlider = container.querySelector('#watermark-scale-slider') as HTMLInputElement;
      expect(opacitySlider).toBeTruthy();
      expect(scaleSlider).toBeTruthy();

      // Verify preview area
      expect(container.textContent).toContain('Interactive Preview Overlay');

      unmount();
    });

    it('submits watermark job with selected position and slider values', async () => {
      const runMock = vi.spyOn(jobsApi, 'run').mockResolvedValue({
        job_id: 'job_wm_444',
        status: 'started',
      });

      const { container, unmount } = renderComponent(
        <WatermarkTab defaultVideoPath="/videos/clip.mp4" defaultProjectName="ClipProj" />
      );

      // Switch to text mode
      const textBtn = Array.from(container.querySelectorAll('button')).find((b) =>
        b.textContent?.includes('Text Watermark')
      );
      act(() => {
        textBtn?.click();
      });

      // Select position bottom_left
      const bottomLeftBtn = Array.from(container.querySelectorAll('button')).find((b) =>
        b.textContent === 'Bottom-Left'
      );
      act(() => {
        bottomLeftBtn?.click();
      });

      // Adjust opacity slider using setNativeValue
      const opacitySlider = container.querySelector('#watermark-opacity-slider') as HTMLInputElement;
      act(() => {
        setNativeValue(opacitySlider, '0.5');
      });

      // Submit
      const form = container.querySelector('form');
      await act(async () => {
        form?.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
      });

      expect(runMock).toHaveBeenCalledWith(
        expect.objectContaining({
          video_path: '/videos/clip.mp4',
          project_name: 'ClipProj',
          watermark_mode: 'text',
          watermark_text: '@ViralCutter',
          watermark_position: 'bottom_left',
          watermark_opacity: 0.5,
        })
      );

      unmount();
    });

    it('uploads watermark image file and includes path in job payload', async () => {
      if (!globalThis.URL.createObjectURL) {
        globalThis.URL.createObjectURL = vi.fn(() => 'blob:mock-url');
      } else {
        vi.spyOn(globalThis.URL, 'createObjectURL').mockReturnValue('blob:mock-url');
      }

      const uploadMock = vi.spyOn(uploadApi, 'uploadSingle').mockResolvedValue({
        filename: 'watermark_logo.png',
        filepath: '/abs/path/VIRALS/ClipProj/watermark_logo.png',
        size: 2048,
        project_name: 'ClipProj',
        completed: true,
      });

      const runMock = vi.spyOn(jobsApi, 'run').mockResolvedValue({
        job_id: 'job_wm_555',
        status: 'started',
      });

      const { container, unmount } = renderComponent(
        <WatermarkTab defaultVideoPath="/videos/clip.mp4" defaultProjectName="ClipProj" />
      );

      const fileInput = container.querySelector('#watermark-file-input') as HTMLInputElement;
      expect(fileInput).toBeTruthy();

      const fakeFile = new File(['fake-png-content'], 'watermark_logo.png', { type: 'image/png' });
      await act(async () => {
        Object.defineProperty(fileInput, 'files', {
          value: [fakeFile],
          writable: true,
        });
        fileInput.dispatchEvent(new Event('change', { bubbles: true }));
      });

      expect(uploadMock).toHaveBeenCalledWith(fakeFile, 'ClipProj');
      expect(container.textContent).toContain('Uploaded: watermark_logo.png');

      const form = container.querySelector('form');
      await act(async () => {
        form?.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
      });

      expect(runMock).toHaveBeenCalledWith(
        expect.objectContaining({
          video_path: '/videos/clip.mp4',
          project_name: 'ClipProj',
          watermark_mode: 'image',
          watermark_image: '/abs/path/VIRALS/ClipProj/watermark_logo.png',
        })
      );

      unmount();
    });
  });

  // -------------------------------------------------------------
  // 4. SubtitleEditorTab
  // -------------------------------------------------------------
  describe('SubtitleEditorTab', () => {
    it('renders interactive cue list and handles preset loading', async () => {
      vi.spyOn(subtitlesApi, 'getPresets').mockResolvedValue({
        presets: {
          Hormozi: { font: 'Montserrat-ExtraBold', size: 36, color: '#FFFFFF', highlight_color: '#00FF66' },
          Beast: { font: 'Montserrat-ExtraBold', size: 38, color: '#FFFFFF', highlight_color: '#FFD700' },
        },
      });
      vi.spyOn(subtitlesApi, 'previewStyle').mockResolvedValue({
        html: '<div style="color:white;">Sample Preview</div>',
      });

      const { container, unmount } = renderComponent(
        <SubtitleEditorTab currentProject="MyProject" />
      );

      await act(async () => {
        await Promise.resolve();
      });

      expect(container.textContent).toContain('Subtitle Cue Editor');
      expect(container.textContent).toContain('Style Presets & Preview');

      unmount();
    });
  });

  // -------------------------------------------------------------
  // 5. LibraryTab
  // -------------------------------------------------------------
  describe('LibraryTab', () => {
    it('renders projects and project assets', async () => {
      vi.spyOn(libraryApi, 'listProjects').mockResolvedValue([
        {
          name: 'ProjectAlpha',
          path: '/virals/ProjectAlpha',
          created_at: 1000,
          modified_at: 2000,
          video_count: 2,
          segment_count: 3,
        },
      ]);
      vi.spyOn(libraryApi, 'getProject').mockResolvedValue({
        name: 'ProjectAlpha',
        path: '/virals/ProjectAlpha',
        created_at: 1000,
        modified_at: 2000,
        segments: [],
        files: ['clip_01.mp4', 'clip_02.mp4'],
      });
      vi.spyOn(libraryApi, 'listAssets').mockResolvedValue([
        {
          name: 'clip_01.mp4',
          path: '/virals/ProjectAlpha/clip_01.mp4',
          size: 1024 * 1024 * 5,
          modified_at: 2000,
          asset_type: 'video',
        },
      ]);

      const onSelectMock = vi.fn();
      const { container, unmount } = renderComponent(
        <LibraryTab onSelectVideo={onSelectMock} />
      );

      await act(async () => {
        await Promise.resolve();
      });

      expect(container.textContent).toContain('ProjectAlpha');
      expect(container.textContent).toContain('Projects');

      unmount();
    });
  });

  // -------------------------------------------------------------
  // 6. GDriveTab
  // -------------------------------------------------------------
  describe('GDriveTab', () => {
    it('renders status, lists drive videos, and triggers import and export', async () => {
      vi.spyOn(gdriveApi, 'getStatus').mockResolvedValue({
        available: true,
        mode: 'colab_mount',
        message: 'Google Drive mounted at /content/drive',
      });
      vi.spyOn(gdriveApi, 'listVideos').mockResolvedValue([
        {
          id: 'drive_vid_1',
          name: 'Podcast_Episode_10.mp4',
          size_formatted: '250.0 MB',
          modified_time: '2026-09-28',
          path: '/content/drive/My Drive/Podcast_Episode_10.mp4',
        },
      ]);
      const importMock = vi.spyOn(gdriveApi, 'importVideo').mockResolvedValue({
        status: 'imported',
        video_path: '/uploads/Podcast_Episode_10.mp4',
        project_folder: 'Podcast_Episode_10',
      });
      const exportMock = vi.spyOn(gdriveApi, 'exportToDrive').mockResolvedValue({
        status: 'exported',
        destination: '/content/drive/My Drive/ViralCutter_Backups/Proj_01',
      });

      const onSelectVideoMock = vi.fn();
      const { container, unmount } = renderComponent(
        <GDriveTab onSelectVideo={onSelectVideoMock} defaultProjectName="Proj_01" />
      );

      await act(async () => {
        await Promise.resolve();
      });

      // Status verified
      expect(container.textContent).toContain('Google Drive mounted at /content/drive');
      expect(container.textContent).toContain('Podcast_Episode_10.mp4');

      // Click video item to select
      const selectBtn = Array.from(container.querySelectorAll('button')).find((b) =>
        b.textContent === 'Select'
      );
      act(() => {
        selectBtn?.click();
      });

      // Click Import button
      const importBtn = container.querySelector('[data-testid="import-gdrive-button"]') as HTMLButtonElement;
      expect(importBtn).toBeTruthy();

      await act(async () => {
        importBtn.click();
      });

      expect(importMock).toHaveBeenCalledWith(
        expect.objectContaining({
          file_id: 'drive_vid_1',
        })
      );

      // Trigger Export
      const exportBtn = container.querySelector('[data-testid="export-gdrive-button"]') as HTMLButtonElement;
      expect(exportBtn).toBeTruthy();

      await act(async () => {
        exportBtn.click();
      });

      expect(exportMock).toHaveBeenCalledWith(
        expect.objectContaining({
          project_name: 'Proj_01',
          destination_folder: 'ViralCutter_Backups',
        })
      );

      unmount();
    });
  });

  // -------------------------------------------------------------
  // 7. DiagnosticsTab
  // -------------------------------------------------------------
  describe('DiagnosticsTab', () => {
    it('renders system hardware metrics, FFmpeg health, and active jobs table', async () => {
      const mockSys: SystemStatusResponse = {
        status: 'healthy',
        gpu: {
          available: true,
          name: 'NVIDIA GeForce RTX 4090',
          device_count: 1,
          cuda_version: '12.4',
          vram_free_mb: 20480,
          vram_total_mb: 24576,
        },
        disk: {
          total_gb: 500,
          used_gb: 150,
          free_gb: 350,
          percent_used: 30,
        },
        ffmpeg: {
          ffmpeg_available: true,
          ffprobe_available: true,
          version: '7.1',
        },
        python: {
          version: '3.14.7',
          executable: '/usr/bin/python3',
        },
        tools: { ffmpeg: true, ffprobe: true, torch: true },
      };

      const mockActive: ActiveJobResponse = {
        active: true,
        job: {
          job_id: 'job_diag_555',
          status: 'running',
          stage: 'FACE_DETECTION',
          percent: 75,
          elapsed: '00:02:15',
        },
      };

      vi.spyOn(systemApi, 'getStatus').mockResolvedValue(mockSys);
      vi.spyOn(jobsApi, 'getActive').mockResolvedValue(mockActive);
      const cancelMock = vi.spyOn(jobsApi, 'cancel').mockResolvedValue({
        status: 'cancelled',
        job_id: 'job_diag_555',
      });

      const { container, unmount } = renderComponent(<DiagnosticsTab />);

      await act(async () => {
        await Promise.resolve();
      });

      // Verify GPU info
      expect(container.textContent).toContain('NVIDIA GeForce RTX 4090');
      expect(container.textContent).toContain('CUDA Ready');

      // Verify Disk info
      expect(container.textContent).toContain('350.0 GB Free');

      // Verify FFmpeg health
      expect(container.textContent).toContain('Healthy');

      // Verify Active Jobs table
      expect(container.textContent).toContain('job_diag_555');
      expect(container.textContent).toContain('FACE_DETECTION');
      expect(container.textContent).toContain('75%');

      // Cancel button in table
      const cancelBtn = Array.from(container.querySelectorAll('button')).find((b) =>
        b.textContent?.includes('Cancel')
      );
      expect(cancelBtn).toBeTruthy();

      await act(async () => {
        cancelBtn?.click();
      });

      expect(cancelMock).toHaveBeenCalledWith('job_diag_555');

      unmount();
    });
  });

  // -------------------------------------------------------------
  // 8. Navbar Tab Switching Across All 7 Tabs
  // -------------------------------------------------------------
  describe('Navbar Tab Switching', () => {
    it('renders all 7 tabs and invokes onTabChange when clicked', () => {
      const onTabChange = vi.fn();

      const { container, unmount } = renderComponent(
        <Navbar
          currentTab="generator"
          onTabChange={onTabChange}
          activeJob={null}
          backendHealthy={true}
        />
      );

      const tabLabels = [
        'Generator',
        'Subtitles',
        'Watermark',
        'Subtitle Editor',
        'Library',
        'Google Drive',
        'Diagnostics',
      ];

      for (const label of tabLabels) {
        expect(container.textContent).toContain(label);
        const button = Array.from(container.querySelectorAll('button')).find((b) =>
          b.textContent?.includes(label)
        );
        expect(button).toBeTruthy();

        act(() => {
          button?.click();
        });
      }

      expect(onTabChange).toHaveBeenCalledWith('generator');
      expect(onTabChange).toHaveBeenCalledWith('subtitles');
      expect(onTabChange).toHaveBeenCalledWith('watermark');
      expect(onTabChange).toHaveBeenCalledWith('subtitle-editor');
      expect(onTabChange).toHaveBeenCalledWith('library');
      expect(onTabChange).toHaveBeenCalledWith('gdrive');
      expect(onTabChange).toHaveBeenCalledWith('diagnostics');

      unmount();
    });
  });
});
