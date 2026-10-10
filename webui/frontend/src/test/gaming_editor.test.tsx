import { render, screen, fireEvent, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import GamingCropEditor, { parseBox, formatBox } from '../components/GamingCropEditor';
import { GeneratorTab } from '../components/GeneratorTab';
import { jobsApi, systemApi } from '../api/client';

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
    render(
      <GamingCropEditor
        facecamCrop="0.68,0.05,0.28,0.15"
        gameplayCrop="0.25,0.0,0.50,0.62"
        onChange={onChange}
      />
    );

    expect(screen.getByText(/9:16 Gaming Split Framing/i)).toBeTruthy();
    expect(screen.getByText(/Cam Top-Right/i)).toBeTruthy();
    expect(screen.getByText(/Cam Top-Left/i)).toBeTruthy();
    expect(screen.getByText(/Cam Bottom-Left/i)).toBeTruthy();
    expect(screen.getByText(/Center Action/i)).toBeTruthy();
    expect(screen.getByText(/Reset/i)).toBeTruthy();
  });

  it('triggers preset buttons and calls onChange', () => {
    const onChange = vi.fn();
    render(
      <GamingCropEditor
        facecamCrop="0.68,0.05,0.28,0.15"
        gameplayCrop="0.25,0.0,0.50,0.62"
        onChange={onChange}
      />
    );

    fireEvent.click(screen.getByText('Cam Top-Left'));
    expect(onChange).toHaveBeenCalled();

    fireEvent.click(screen.getByText('Cam Top-Right'));
    expect(onChange).toHaveBeenCalled();

    fireEvent.click(screen.getByText('Cam Bottom-Left'));
    expect(onChange).toHaveBeenCalled();

    fireEvent.click(screen.getByText('Center Action'));
    expect(onChange).toHaveBeenCalled();

    fireEvent.click(screen.getByText('Reset'));
    expect(onChange).toHaveBeenCalled();
  });
});

describe('GeneratorTab Gaming Split Integration', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(systemApi, 'getPromptTemplate').mockResolvedValue({
      template: 'Default prompt template',
    });
  });

  it('renders 9:16_gaming_split in orientation options and conditionally shows GamingCropEditor', () => {
    const { container } = render(
      <GeneratorTab defaultVideoPath="/videos/test.mp4" defaultProjectName="TestGaming" />
    );

    const orientationSelect = container.querySelector('#orientation-select') as HTMLSelectElement;
    expect(orientationSelect).toBeTruthy();

    const options = Array.from(orientationSelect.options).map((opt) => opt.value);
    expect(options).toContain('9:16_gaming_split');

    // Initially 9:16 is selected, GamingCropEditor should not be visible
    expect(screen.queryByText(/9:16 Gaming Split Framing/i)).toBeNull();

    // Select 9:16_gaming_split
    fireEvent.change(orientationSelect, { target: { value: '9:16_gaming_split' } });

    // Now GamingCropEditor should be visible
    expect(screen.getByText(/9:16 Gaming Split Framing/i)).toBeTruthy();
  });

  it('attaches orientation, gaming_facecam_crop, and gaming_gameplay_crop in handleRunJob', async () => {
    const runMock = vi.spyOn(jobsApi, 'run').mockResolvedValue({
      job_id: 'job_gaming_123',
      status: 'started',
    });
    vi.spyOn(jobsApi, 'streamLogs').mockReturnValue(() => {});

    const { container } = render(
      <GeneratorTab defaultVideoPath="/videos/test.mp4" defaultProjectName="TestGaming" />
    );

    const orientationSelect = container.querySelector('#orientation-select') as HTMLSelectElement;
    fireEvent.change(orientationSelect, { target: { value: '9:16_gaming_split' } });

    const form = container.querySelector('form');
    await act(async () => {
      form?.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    });

    expect(runMock).toHaveBeenCalledWith(
      expect.objectContaining({
        orientation: '9:16_gaming_split',
        gaming_facecam_crop: expect.stringMatching(/^[0-9.,]+$/),
        gaming_gameplay_crop: expect.stringMatching(/^[0-9.,]+$/),
      })
    );
  });
});
