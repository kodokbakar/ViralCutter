import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import GamingCropEditor, { parseBox, formatBox } from '../components/GamingCropEditor';
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
});
