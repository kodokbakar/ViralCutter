/**
 * API client layer for ViralCutter /api/v1/ endpoints.
 */

import type {
  ActiveJobResponse,
  AssetItem,
  ExportResponse,
  GDriveExportRequest,
  GDriveExportResponse,
  GDriveImportRequest,
  GDriveImportResponse,
  GDriveStatusResponse,
  GDriveVideoItem,
  JobResponse,
  JobRunRequest,
  JobStatusResponse,
  ProjectDetail,
  ProjectSummary,
  SubtitleConvertRequest,
  SubtitleConvertResponse,
  SubtitleParseRequest,
  SubtitleParseResponse,
  SubtitlePresetsResponse,
  SubtitleSaveRequest,
  SubtitleSaveResponse,
  SubtitleStylePreviewRequest,
  SubtitleStylePreviewResponse,
  SystemHealthResponse,
  SystemStatusResponse,
  ThumbnailRequest,
  ThumbnailResponse,
  UploadResponse,
  VideoMetadata,
} from './types';

const API_BASE = '/api/v1';

export class ApiError extends Error {
  status: number;
  data: unknown;

  constructor(message: string, status: number, data?: unknown) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.data = data;
  }
}

async function request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const url = `${API_BASE}${endpoint}`;
  const headers = new Headers(options.headers || {});

  if (!headers.has('Content-Type') && options.body && !(options.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json');
  }

  const response = await fetch(url, {
    method: options.method || 'GET',
    ...options,
    headers,
  });

  if (!response.ok) {
    let errorDetail = `Request failed with status ${response.status}`;
    let errData: unknown;
    try {
      errData = await response.json();
      if (typeof errData === 'object' && errData !== null) {
        const d = errData as Record<string, unknown>;
        if (typeof d.detail === 'string') {
          errorDetail = d.detail;
        } else if (typeof d.message === 'string') {
          errorDetail = d.message;
        }
      }
    } catch {
      // Non-JSON response
    }
    throw new ApiError(errorDetail, response.status, errData);
  }

  return response.json() as Promise<T>;
}

// -------------------------------------------------------------
// Jobs API
// -------------------------------------------------------------
export const jobsApi = {
  run: (params: JobRunRequest): Promise<JobResponse> =>
    request<JobResponse>('/jobs/run', {
      method: 'POST',
      body: JSON.stringify(params),
    }),

  cancel: (jobId: string): Promise<{ status: string; job_id?: string; message?: string }> =>
    request<{ status: string; job_id?: string; message?: string }>(
      `/jobs/${encodeURIComponent(jobId)}/cancel`,
      {
        method: 'POST',
      }
    ),

  getActive: (): Promise<ActiveJobResponse> =>
    request<ActiveJobResponse>('/jobs/active'),

  getStatus: (jobId: string): Promise<JobStatusResponse> =>
    request<JobStatusResponse>(`/jobs/${encodeURIComponent(jobId)}`),

  /**
   * Connect to SSE log stream.
   * Returns a cleanup function to close connection.
   */
  streamLogs: (
    jobId: string,
    onMessage: (logLine: string) => void,
    onError?: (error: Event) => void
  ): (() => void) => {
    const sseUrl = `${API_BASE}/jobs/${encodeURIComponent(jobId)}/stream`;
    const eventSource = new EventSource(sseUrl);

    eventSource.onmessage = (event) => {
      try {
        const parsed = JSON.parse(event.data);
        if (typeof parsed === 'string') {
          onMessage(parsed);
        } else if (parsed && typeof parsed.line === 'string') {
          onMessage(parsed.line);
        } else {
          onMessage(event.data);
        }
      } catch {
        onMessage(event.data);
      }
    };

    if (onError) {
      eventSource.onerror = (e) => {
        onError(e);
      };
    }

    return () => {
      eventSource.close();
    };
  },
};

// -------------------------------------------------------------
// Upload API
// -------------------------------------------------------------
export const uploadApi = {
  uploadSingle: (file: File, projectName?: string): Promise<UploadResponse> => {
    const formData = new FormData();
    formData.append('file', file);
    if (projectName) {
      formData.append('project_name', projectName);
    }
    return request<UploadResponse>('/upload', {
      method: 'POST',
      body: formData,
    });
  },

  upload: (file: File, projectName?: string): Promise<UploadResponse> =>
    uploadApi.uploadSingle(file, projectName),

  uploadChunk: (
    fileChunk: Blob,
    uploadId: string,
    chunkIndex: number,
    totalChunks: number,
    filename: string,
    projectName?: string
  ): Promise<UploadResponse> => {
    const formData = new FormData();
    formData.append('file', fileChunk, filename);
    formData.append('upload_id', uploadId);
    formData.append('chunk_index', String(chunkIndex));
    formData.append('total_chunks', String(totalChunks));
    if (projectName) {
      formData.append('project_name', projectName);
    }
    return request<UploadResponse>('/upload', {
      method: 'POST',
      body: formData,
    });
  },

  uploadFileChunked: async (
    file: File,
    projectName?: string,
    onProgress?: (progress: number, chunkIndex: number, totalChunks: number) => void,
    chunkSize = 5 * 1024 * 1024 // 5MB chunks
  ): Promise<UploadResponse> => {
    const totalChunks = Math.max(1, Math.ceil(file.size / chunkSize));
    const uploadId = `upload_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`;
    let lastResponse: UploadResponse | null = null;

    for (let index = 0; index < totalChunks; index++) {
      const start = index * chunkSize;
      const end = Math.min(file.size, start + chunkSize);
      const chunk = file.slice(start, end);

      lastResponse = await uploadApi.uploadChunk(
        chunk,
        uploadId,
        index,
        totalChunks,
        file.name,
        projectName
      );

      if (onProgress) {
        const percent = Math.round(((index + 1) / totalChunks) * 100);
        onProgress(percent, index + 1, totalChunks);
      }
    }

    if (!lastResponse) {
      throw new Error('Upload completed with no response');
    }
    return lastResponse;
  },
};

// -------------------------------------------------------------
// Preview API
// -------------------------------------------------------------
export const previewApi = {
  getVideoUrl: (videoPath: string): string =>
    `${API_BASE}/preview/stream?path=${encodeURIComponent(videoPath)}`,

  getThumbnailUrl: (thumbnailPath: string): string =>
    `${API_BASE}/preview/thumbnail?path=${encodeURIComponent(thumbnailPath)}`,

  getMetadata: (videoPath: string): Promise<VideoMetadata> =>
    request<VideoMetadata>(`/preview/metadata?path=${encodeURIComponent(videoPath)}`),

  createThumbnail: (req: ThumbnailRequest): Promise<ThumbnailResponse> =>
    request<ThumbnailResponse>('/preview/thumbnail', {
      method: 'POST',
      body: JSON.stringify(req),
    }),
};

// -------------------------------------------------------------
// Library API
// -------------------------------------------------------------
export const libraryApi = {
  listProjects: (): Promise<ProjectSummary[]> =>
    request<ProjectSummary[]>('/library/projects'),

  getProject: (projectName: string): Promise<ProjectDetail> =>
    request<ProjectDetail>(`/library/projects/${encodeURIComponent(projectName)}`),

  renameProject: (
    projectName: string,
    newName: string
  ): Promise<{ status: string; old_name?: string; new_name: string }> =>
    request<{ status: string; old_name?: string; new_name: string }>(
      `/library/projects/${encodeURIComponent(projectName)}`,
      {
        method: 'PATCH',
        body: JSON.stringify({ new_name: newName }),
      }
    ),

  deleteProject: (
    projectName: string
  ): Promise<{ status: string; project_name: string }> =>
    request<{ status: string; project_name: string }>(
      `/library/projects/${encodeURIComponent(projectName)}`,
      {
        method: 'DELETE',
      }
    ),

  listAssets: (projectName?: string, assetType?: string): Promise<AssetItem[]> => {
    const params = new URLSearchParams();
    if (projectName) params.set('project_name', projectName);
    if (assetType) params.set('type', assetType);
    const q = params.toString();
    return request<AssetItem[]>(`/library/assets${q ? `?${q}` : ''}`);
  },

  deleteAsset: (
    filePathOrProject: string,
    maybeAssetName?: string
  ): Promise<{ status: string; path?: string }> => {
    const filePath = maybeAssetName ? `${filePathOrProject}/${maybeAssetName}` : filePathOrProject;
    return request<{ status: string; path?: string }>(
      `/library/assets?file_path=${encodeURIComponent(filePath)}`,
      {
        method: 'DELETE',
      }
    );
  },

  exportProject: (projectName: string): Promise<ExportResponse> =>
    request<ExportResponse>(`/library/projects/${encodeURIComponent(projectName)}/export`, {
      method: 'POST',
    }),

  getDownloadUrl: (zipPath: string): string =>
    `${API_BASE}/library/export/download?path=${encodeURIComponent(zipPath)}`,
};

// -------------------------------------------------------------
// Subtitles API
// -------------------------------------------------------------
export const subtitlesApi = {
  parse: (req: SubtitleParseRequest): Promise<SubtitleParseResponse> =>
    request<SubtitleParseResponse>('/subtitles/parse', {
      method: 'POST',
      body: JSON.stringify(req),
    }),

  convert: (req: SubtitleConvertRequest): Promise<SubtitleConvertResponse> =>
    request<SubtitleConvertResponse>('/subtitles/convert', {
      method: 'POST',
      body: JSON.stringify(req),
    }),

  save: (req: SubtitleSaveRequest): Promise<SubtitleSaveResponse> =>
    request<SubtitleSaveResponse>('/subtitles/save', {
      method: 'POST',
      body: JSON.stringify(req),
    }),

  getPresets: (): Promise<SubtitlePresetsResponse> =>
    request<SubtitlePresetsResponse>('/subtitles/presets'),

  previewStyle: (req: SubtitleStylePreviewRequest): Promise<SubtitleStylePreviewResponse> =>
    request<SubtitleStylePreviewResponse>('/subtitles/preview-style', {
      method: 'POST',
      body: JSON.stringify(req),
    }),
};

// -------------------------------------------------------------
// Google Drive API
// -------------------------------------------------------------
export const gdriveApi = {
  getStatus: (): Promise<GDriveStatusResponse> =>
    request<GDriveStatusResponse>('/gdrive/status'),

  listVideos: (params?: { query?: string; limit?: number; force_refresh?: boolean }): Promise<GDriveVideoItem[]> => {
    const searchParams = new URLSearchParams();
    if (params?.query) searchParams.set('query', params.query);
    if (params?.limit) searchParams.set('limit', String(params.limit));
    if (params?.force_refresh) searchParams.set('force_refresh', 'true');
    const q = searchParams.toString();
    return request<GDriveVideoItem[]>(`/gdrive/videos${q ? `?${q}` : ''}`);
  },

  importVideo: (req: GDriveImportRequest): Promise<GDriveImportResponse> =>
    request<GDriveImportResponse>('/gdrive/import', {
      method: 'POST',
      body: JSON.stringify(req),
    }),

  exportToDrive: (req: GDriveExportRequest): Promise<GDriveExportResponse> =>
    request<GDriveExportResponse>('/gdrive/export', {
      method: 'POST',
      body: JSON.stringify(req),
    }),
};

// -------------------------------------------------------------
// System API
// -------------------------------------------------------------
export const systemApi = {
  getStatus: (): Promise<SystemStatusResponse> =>
    request<SystemStatusResponse>('/system/status'),

  getHealth: (): Promise<SystemHealthResponse> =>
    request<SystemHealthResponse>('/system/health'),
};
