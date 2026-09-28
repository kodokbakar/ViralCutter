import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import {
  jobsApi,
  uploadApi,
  previewApi,
  libraryApi,
  subtitlesApi,
  gdriveApi,
  systemApi,
  ApiError,
} from '../api/client';

describe('API Client Layer', () => {
  const originalFetch = globalThis.fetch;

  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  it('correctly dispatches jobsApi.run', async () => {
    const mockResponse = {
      job_id: 'job_123',
      status: 'queued',
      command: ['python3', 'main_improved.py'],
      started_at: 1000,
      ended_at: null,
      return_code: null,
      error: null,
      log_tail: [],
    };

    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => mockResponse,
    } as Response);

    const result = await jobsApi.run({
      input_source: 'youtube',
      url: 'https://www.youtube.com/watch?v=test',
    });

    expect(result.job_id).toBe('job_123');
    expect(globalThis.fetch).toHaveBeenCalledWith(
      '/api/v1/jobs/run',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({
          input_source: 'youtube',
          url: 'https://www.youtube.com/watch?v=test',
        }),
      })
    );
  });

  it('correctly constructs previewApi.getVideoUrl with URI encoding', () => {
    const rawPath = '/path/to/my video #1 [viral].mp4';
    const url = previewApi.getVideoUrl(rawPath);
    expect(url).toBe(`/api/v1/preview/stream?path=${encodeURIComponent(rawPath)}`);
  });

  it('correctly dispatches jobsApi.cancel and jobsApi.getStatus', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ status: 'cancelled', job_id: 'job_456' }),
    } as Response);

    const cancelRes = await jobsApi.cancel('job_456');
    expect(cancelRes.status).toBe('cancelled');
    expect(globalThis.fetch).toHaveBeenCalledWith(
      '/api/v1/jobs/job_456/cancel',
      expect.objectContaining({ method: 'POST' })
    );

    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ job_id: 'job_456', status: 'running' }),
    } as Response);

    const statusRes = await jobsApi.getStatus('job_456');
    expect(statusRes.job_id).toBe('job_456');
    expect(globalThis.fetch).toHaveBeenCalledWith(
      '/api/v1/jobs/job_456',
      expect.objectContaining({ method: 'GET' })
    );

    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ active: true, job: { job_id: 'job_456', status: 'running' } }),
    } as Response);

    const activeRes = await jobsApi.getActive();
    expect(activeRes.active).toBe(true);
    expect(activeRes.job?.job_id).toBe('job_456');
    expect(globalThis.fetch).toHaveBeenCalledWith(
      '/api/v1/jobs/active',
      expect.objectContaining({ method: 'GET' })
    );
  });

  it('correctly dispatches uploadApi.uploadSingle to /upload', async () => {
    const blob = new Blob(['video'], { type: 'video/mp4' });
    const file = new File([blob], 'video.mp4', { type: 'video/mp4' });

    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        filename: 'video.mp4',
        filepath: '/path/video.mp4',
        size: 5,
        completed: true,
      }),
    } as Response);

    const res = await uploadApi.uploadSingle(file, 'test_proj');
    expect(res.completed).toBe(true);
    expect(globalThis.fetch).toHaveBeenCalledWith(
      '/api/v1/upload',
      expect.objectContaining({ method: 'POST' })
    );
  });

  it('correctly verifies libraryApi contracts (listAssets, renameProject, deleteAsset, getDownloadUrl)', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => [],
    } as Response);

    await libraryApi.listAssets('my_project', 'video');
    expect(globalThis.fetch).toHaveBeenCalledWith(
      '/api/v1/library/assets?project_name=my_project&type=video',
      expect.objectContaining({ method: 'GET' })
    );

    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ status: 'renamed', old_name: 'old_p', new_name: 'new_p' }),
    } as Response);

    await libraryApi.renameProject('old_p', 'new_p');
    expect(globalThis.fetch).toHaveBeenCalledWith(
      '/api/v1/library/projects/old_p',
      expect.objectContaining({
        method: 'PATCH',
        body: JSON.stringify({ new_name: 'new_p' }),
      })
    );

    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ status: 'deleted', path: 'virals/test.mp4' }),
    } as Response);

    await libraryApi.deleteAsset('virals/test.mp4');
    expect(globalThis.fetch).toHaveBeenCalledWith(
      '/api/v1/library/assets?file_path=virals%2Ftest.mp4',
      expect.objectContaining({ method: 'DELETE' })
    );

    const downloadUrl = libraryApi.getDownloadUrl('virals/export.zip');
    expect(downloadUrl).toBe('/api/v1/library/export/download?path=virals%2Fexport.zip');
  });

  it('correctly dispatches gdriveApi.listVideos to /gdrive/videos', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => [],
    } as Response);

    await gdriveApi.listVideos({ query: 'vacation', limit: 10 });
    expect(globalThis.fetch).toHaveBeenCalledWith(
      '/api/v1/gdrive/videos?query=vacation&limit=10',
      expect.objectContaining({ method: 'GET' })
    );
  });

  it('correctly handles HTTP API errors and throws ApiError', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 404,
      json: async () => ({ detail: 'Project not found' }),
    } as Response);

    await expect(libraryApi.getProject('nonexistent')).rejects.toThrow(ApiError);
    await expect(libraryApi.getProject('nonexistent')).rejects.toThrow('Project not found');
  });

  it('correctly parses system status response', async () => {
    const mockStatus = {
      status: 'ok',
      gpu: { available: true, name: 'NVIDIA RTX 4090' },
      disk: { total_gb: 500, used_gb: 200, free_gb: 300, percent_used: 40 },
      ffmpeg: { ffmpeg_available: true, ffprobe_available: true, version: '6.1' },
      python: { version: '3.13.14' },
      tools: { whisper: true, insightface: true },
    };

    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => mockStatus,
    } as Response);

    const res = await systemApi.getStatus();
    expect(res.status).toBe('ok');
    expect(res.gpu.available).toBe(true);
    expect(res.disk.free_gb).toBe(300);
  });

  it('correctly sends subtitles parse request', async () => {
    const mockParse = {
      format: 'srt',
      entries: [{ index: 1, start: 0, end: 2, text: 'Hello' }],
      count: 1,
    };

    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => mockParse,
    } as Response);

    const res = await subtitlesApi.parse({ content: '1\n00:00:00,000 --> 00:00:02,000\nHello' });
    expect(res.count).toBe(1);
    expect(res.entries[0].text).toBe('Hello');
  });

  it('correctly invokes gdriveApi.getStatus', async () => {
    const mockGdrive = {
      available: false,
      mode: 'unconfigured',
      message: 'Not connected',
    };

    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => mockGdrive,
    } as Response);

    const res = await gdriveApi.getStatus();
    expect(res.available).toBe(false);
    expect(res.mode).toBe('unconfigured');
  });

  it('correctly chunks files in uploadApi.uploadFileChunked', async () => {
    // Create a dummy blob representing 12 MB file (3 chunks of 5 MB)
    const blob = new Blob(['A'.repeat(12 * 1024 * 1024)], { type: 'video/mp4' });
    const file = new File([blob], 'test.mp4', { type: 'video/mp4' });

    const chunkCalls: number[] = [];
    vi.spyOn(uploadApi, 'uploadChunk').mockImplementation(
      async (_chunk, _uploadId, chunkIndex, totalChunks) => {
        chunkCalls.push(chunkIndex);
        return {
          filename: 'test.mp4',
          filepath: '/tmp/test.mp4',
          size: file.size,
          completed: chunkIndex === totalChunks - 1,
        };
      }
    );

    const res = await uploadApi.uploadFileChunked(file);
    expect(res.completed).toBe(true);
    expect(chunkCalls).toEqual([0, 1, 2]);
  });
});
