import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import GamingCropEditor, { parseBox, formatBox } from '../components/GamingCropEditor';
import VerticalCropEditor from '../components/VerticalCropEditor';
import { GeneratorTab } from '../components/GeneratorTab';
import { jobsApi, systemApi } from '../api/client';

function renderComponent(ui: React.ReactElement): { container: HTMLDivElement; unmount: () => void } {
  const container = document.createElement('div');
  document.body.appendChild(container);
  const root = createRoot(container);
  act(() => {
    root.render(ui);
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

describe('GamingCropEditor Component', () => {
  it('parses valid and invalid box strings correctly', () => {
    const valid = parseBox('0.1,0.2,0.3,0.4', { x: 0, y: 0, w: 1, h: 1 });
    expect(valid.x).toBe(0.1);
    expect(valid.y).toBe(0.2);

    const invalid = parseBox('gibberish', { x: 0.5, y: 0.5, w: 0.5, h: 0.5 });
    expect(invalid.x).toBe(0.5);
  });

  it('formats box rect back into comma-separated string', () => {
    const str = formatBox({ x: 0.1234, y: 0.5678, w: 0.25, h: 0.35 });
    expect(str).toBe('0.1234,0.5678,0.2500,0.3500');
  });

  it('renders canvas elements and preset buttons', () => {
    const onChange = vi.fn();
    const { container, unmount } = renderComponent(
      <GamingCropEditor
        facecamCrop="0.68,0.05,0.28,0.15"
        gameplayCrop="0.25,0.0,0.50,0.62"
        onChange={onChange}
      />
    );

    expect(container.textContent).toContain('9:16 Gaming Split Framing');
    expect(container.textContent).toContain('Cam Top-Right');
    expect(container.textContent).toContain('Cam Top-Left');
    expect(container.textContent).toContain('Cam Bottom-Left');
    expect(container.textContent).toContain('Center Action');
    expect(container.textContent).toContain('Reset');
    unmount();
  });

  it('triggers preset buttons and calls onChange', () => {
    const onChange = vi.fn();
    const { container, unmount } = renderComponent(
      <GamingCropEditor
        facecamCrop="0.68,0.05,0.28,0.15"
        gameplayCrop="0.25,0.0,0.50,0.62"
        onChange={onChange}
      />
    );

    const buttons = Array.from(container.querySelectorAll('button'));
    const topLeftBtn = buttons.find((b) => b.textContent?.includes('Cam Top-Left'));
    expect(topLeftBtn).toBeTruthy();

    act(() => {
      topLeftBtn?.click();
    });

    expect(onChange).toHaveBeenCalled();
    const lastCall = onChange.mock.calls[onChange.mock.calls.length - 1];
    expect(lastCall[0]).toContain('0.0400,0.0500');

    const centerActionBtn = buttons.find((b) => b.textContent?.includes('Center Action'));
    expect(centerActionBtn).toBeTruthy();
    act(() => {
      centerActionBtn?.click();
    });
    expect(onChange).toHaveBeenCalled();

    unmount();
  });

  it('renders 3 sample frame buttons and allows switching', () => {
    const onSelect = vi.fn();
    const sampleFrames = [
      { index: 0, timestamp: 5.0, time_label: '00:05', path: '/tmp/f1.jpg', filename: 'f1.jpg', data_uri: 'data:image/jpeg;base64,1' },
      { index: 1, timestamp: 30.0, time_label: '00:30', path: '/tmp/f2.jpg', filename: 'f2.jpg', data_uri: 'data:image/jpeg;base64,2' },
      { index: 2, timestamp: 55.0, time_label: '00:55', path: '/tmp/f3.jpg', filename: 'f3.jpg', data_uri: 'data:image/jpeg;base64,3' },
    ];

    const { container, unmount } = renderComponent(
      <GamingCropEditor
        facecamCrop="0.68,0.05,0.28,0.15"
        gameplayCrop="0.25,0.0,0.50,0.62"
        sampleFrames={sampleFrames}
        onSelectSampleFrame={onSelect}
        onChange={vi.fn()}
      />
    );

    expect(container.textContent).toContain('Source Frames:');
    expect(container.textContent).toContain('Sample 1 (00:05)');
    expect(container.textContent).toContain('Sample 2 (00:30)');
    expect(container.textContent).toContain('Sample 3 (00:55)');

    const buttons = Array.from(container.querySelectorAll('button'));
    const sample2Btn = buttons.find((b) => b.textContent?.includes('Sample 2 (00:30)'));
    expect(sample2Btn).toBeTruthy();

    act(() => {
      sample2Btn?.click();
    });
    expect(onSelect).toHaveBeenCalledWith(1);

    unmount();
  });
});

describe('GeneratorTab Gaming Split Integration', () => {
  beforeEach(() => {
    vi.spyOn(systemApi, 'getStatus').mockResolvedValue({
      healthy: true,
      has_gpu: false,
      gpu_name: null,
      device: 'cpu',
      platform: 'linux',
      python_version: '3.11.0',
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('renders 9:16_gaming_split in orientation options and conditionally shows GamingCropEditor', () => {
    const { container, unmount } = renderComponent(
      <GeneratorTab defaultVideoPath="/videos/test.mp4" defaultProjectName="TestProj" />
    );

    const orientationSelect = container.querySelector('#orientation-select') as HTMLSelectElement;
    expect(orientationSelect).toBeTruthy();

    const options = Array.from(orientationSelect.options).map((o) => o.value);
    expect(options).toContain('9:16_gaming_split');

    expect(container.textContent).not.toContain('9:16 Gaming Split Framing');

    act(() => {
      orientationSelect.value = '9:16_gaming_split';
      orientationSelect.dispatchEvent(new Event('change', { bubbles: true }));
    });

    expect(container.textContent).toContain('9:16 Gaming Split Framing');
    unmount();
  });

  it('attaches orientation, gaming_facecam_crop, and gaming_gameplay_crop in handleRunJob', async () => {
    const runMock = vi.spyOn(jobsApi, 'run').mockResolvedValue({
      job_id: 'job_gaming_split_123',
      status: 'started',
    });

    const { container, unmount } = renderComponent(
      <GeneratorTab defaultVideoPath="/videos/test.mp4" defaultProjectName="TestProj" />
    );

    const orientationSelect = container.querySelector('#orientation-select') as HTMLSelectElement;
    act(() => {
      orientationSelect.value = '9:16_gaming_split';
      orientationSelect.dispatchEvent(new Event('change', { bubbles: true }));
    });

    const form = container.querySelector('form');
    expect(form).toBeTruthy();

    await act(async () => {
      form?.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    });

    expect(runMock).toHaveBeenCalled();
    const payload = runMock.mock.calls[0][0];
    expect(payload.orientation).toBe('9:16_gaming_split');
    expect(payload.gaming_facecam_crop).toBe('0.6800,0.0500,0.2800,0.1493');
    expect(payload.gaming_gameplay_crop).toBe('0.2500,0.0000,0.5000,0.6220');

    unmount();
  });

  it('renders framing mode selector and toggles between AI Face Tracking and Manual 9:16 Crop', async () => {
    const runMock = vi.spyOn(jobsApi, 'run').mockResolvedValue({
      job_id: 'job_manual_crop_456',
      status: 'started',
    });

    const { container, unmount } = renderComponent(
      <GeneratorTab defaultVideoPath="/videos/test.mp4" defaultProjectName="TestProj" />
    );

    expect(container.textContent).toContain('Framing Method');
    expect(container.textContent).toContain('AI Face Tracking');
    expect(container.textContent).toContain('Manual 9:16 Crop');

    // Toggle to Manual 9:16 Crop
    const manualCropBtn = Array.from(container.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('Manual 9:16 Crop')
    );
    expect(manualCropBtn).toBeTruthy();
    act(() => {
      manualCropBtn?.click();
    });

    expect(container.textContent).toContain('Manual 9:16 Vertical Crop');

    // Submit form and verify manual_crop is attached
    const form = container.querySelector('form');
    await act(async () => {
      form?.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    });

    expect(runMock).toHaveBeenCalled();
    const payload = runMock.mock.calls[0][0];
    expect(payload.orientation).toBe('9:16');
    expect(payload.manual_crop).toBe('0.3418,0.0000,0.3164,1.0000');
    expect(payload.face_mode).toBe('none');

    unmount();
  });
});

describe('VerticalCropEditor Standalone Component', () => {
  it('renders canvas and preset buttons, calls onChange on preset click', () => {
    const onChange = vi.fn();
    const { container, unmount } = renderComponent(
      <VerticalCropEditor
        cropBox="0.3418,0.0,0.3164,1.0"
        onChange={onChange}
      />
    );

    expect(container.textContent).toContain('Manual 9:16 Vertical Crop');
    expect(container.textContent).toContain('Left');
    expect(container.textContent).toContain('Center');
    expect(container.textContent).toContain('Right');
    expect(container.textContent).toContain('Reset');

    const leftBtn = Array.from(container.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('Left')
    );
    act(() => {
      leftBtn?.click();
    });
    expect(onChange).toHaveBeenCalled();

    unmount();
  });
});
