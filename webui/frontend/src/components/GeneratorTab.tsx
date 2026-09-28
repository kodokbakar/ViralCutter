import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  Play,
  Square,
  Terminal,
  Sliders,
  Copy,
  Check,
  AlertCircle,
  Upload,
  Loader2,
} from 'lucide-react';
import { jobsApi, uploadApi } from '../api/client';
import type { JobRunRequest, ActiveJobResponse } from '../api/types';

export interface GeneratorTabProps {
  activeJob?: ActiveJobResponse | null;
  onRefreshActiveJob?: () => void;
  defaultVideoPath?: string;
  defaultProjectName?: string;
}

export type GeneratorPreset = 'viral_shorts' | 'fast' | 'balanced' | 'accurate' | 'custom';
export type VideoOrientation = '9:16' | '16:9' | '1:1';
export type InputMode = 'upload' | 'youtube' | 'path';

export const GeneratorTab: React.FC<GeneratorTabProps> = ({
  activeJob,
  onRefreshActiveJob,
  defaultVideoPath = '',
  defaultProjectName = '',
}) => {
  // Parameter Controls
  const [preset, setPreset] = useState<GeneratorPreset>('viral_shorts');
  const [targetDuration, setTargetDuration] = useState<number>(60);
  const [orientation, setOrientation] = useState<VideoOrientation>('9:16');
  const [model, setModel] = useState<string>('large-v3-turbo');

  // Extended Pipeline Parameters
  const [workflow, setWorkflow] = useState<'1' | '2' | '3'>('1');
  const [segments, setSegments] = useState<number>(3);
  const [viral, setViral] = useState<boolean>(true);
  const [language, setLanguage] = useState<string>('auto');

  // File Selection
  const [inputMode, setInputMode] = useState<InputMode>('upload');
  const [youtubeUrl, setYoutubeUrl] = useState<string>('');
  const [videoPath, setVideoPath] = useState<string>(defaultVideoPath);
  const [projectName, setProjectName] = useState<string>(defaultProjectName);

  // Upload State
  const [isUploading, setIsUploading] = useState<boolean>(false);
  const [uploadProgress, setUploadProgress] = useState<number>(0);
  const [uploadStatus, setUploadStatus] = useState<string>('');

  // Execution & Log Stream State
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [isCancelling, setIsCancelling] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [logs, setLogs] = useState<string[]>([]);
  const [autoScroll, setAutoScroll] = useState<boolean>(true);
  const [copiedLogs, setCopiedLogs] = useState<boolean>(false);
  const [trackedJobId, setTrackedJobId] = useState<string | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const logContainerRef = useRef<HTMLDivElement>(null);
  const logBufferRef = useRef<string[]>([]);
  const animationFrameId = useRef<number | null>(null);

  // Handle Preset Changes
  const handlePresetChange = (newPreset: GeneratorPreset) => {
    setPreset(newPreset);
    switch (newPreset) {
      case 'viral_shorts':
        setModel('large-v3-turbo');
        setTargetDuration(60);
        setOrientation('9:16');
        setWorkflow('1');
        setViral(true);
        setSegments(3);
        break;
      case 'fast':
        setModel('tiny');
        setTargetDuration(30);
        setOrientation('9:16');
        setWorkflow('2'); // Cut only
        setViral(true);
        setSegments(2);
        break;
      case 'balanced':
        setModel('large-v3-turbo');
        setTargetDuration(60);
        setOrientation('9:16');
        setWorkflow('1');
        setViral(true);
        setSegments(3);
        break;
      case 'accurate':
        setModel('large-v3');
        setTargetDuration(90);
        setOrientation('9:16');
        setWorkflow('1');
        setViral(true);
        setSegments(5);
        break;
      case 'custom':
        break;
    }
  };

  // Sync Default Props
  useEffect(() => {
    if (defaultVideoPath) {
      setVideoPath(defaultVideoPath);
      setInputMode('path');
    }
    if (defaultProjectName) {
      setProjectName(defaultProjectName);
    }
  }, [defaultVideoPath, defaultProjectName]);

  // Sync active job if external prop updates
  useEffect(() => {
    if (activeJob?.active && activeJob.job?.job_id) {
      setTrackedJobId(activeJob.job.job_id);
    }
  }, [activeJob]);

  // Buffer and flush logs smoothly
  const flushLogs = useCallback(() => {
    if (logBufferRef.current.length > 0) {
      const incoming = [...logBufferRef.current];
      logBufferRef.current = [];
      setLogs((prev) => {
        const combined = prev.concat(incoming);
        return combined.length > 1500 ? combined.slice(combined.length - 1500) : combined;
      });
    }
    animationFrameId.current = requestAnimationFrame(flushLogs);
  }, []);

  useEffect(() => {
    animationFrameId.current = requestAnimationFrame(flushLogs);
    return () => {
      if (animationFrameId.current !== null) {
        cancelAnimationFrame(animationFrameId.current);
      }
    };
  }, [flushLogs]);

  // Auto-scroll when logs change
  useEffect(() => {
    if (autoScroll && logContainerRef.current) {
      logContainerRef.current.scrollTop = logContainerRef.current.scrollHeight;
    }
  }, [logs, autoScroll]);

  // Live SSE stream connection
  useEffect(() => {
    if (!trackedJobId) return;

    logBufferRef.current.push(`[System] Connecting to SSE log stream for job ${trackedJobId}...`);

    const cleanup = jobsApi.streamLogs(
      trackedJobId,
      (line) => {
        logBufferRef.current.push(line);
      },
      () => {
        // SSE connection closed or reconnecting
      }
    );

    return () => {
      cleanup();
    };
  }, [trackedJobId]);

  // File Upload Handler
  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setIsUploading(true);
    setUploadProgress(0);
    setUploadStatus('Uploading file...');
    setErrorMessage(null);

    try {
      let res;
      if (file.size > 20 * 1024 * 1024) {
        res = await uploadApi.uploadFileChunked(
          file,
          projectName.trim() || undefined,
          (pct) => setUploadProgress(pct)
        );
      } else {
        setUploadProgress(50);
        res = await uploadApi.uploadSingle(file, projectName.trim() || undefined);
        setUploadProgress(100);
      }
      setVideoPath(res.filepath);
      setUploadStatus(`Uploaded: ${res.filename}`);
      if (!projectName && res.filename) {
        setProjectName(res.filename.replace(/\.[^/.]+$/, ''));
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Upload failed';
      setErrorMessage(msg);
      setUploadStatus('');
    } finally {
      setIsUploading(false);
    }
  };

  // Run Job Trigger
  const handleRunJob = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage(null);

    // Validate file selection
    if (inputMode === 'youtube' && !youtubeUrl.trim()) {
      setErrorMessage('Please enter a valid YouTube URL');
      return;
    }
    if ((inputMode === 'upload' || inputMode === 'path') && !videoPath.trim()) {
      setErrorMessage('Please select or upload a video file first');
      return;
    }

    setIsSubmitting(true);
    setLogs([]);
    logBufferRef.current = ['[System] Submitting job request...'];

    // Map orientation to face_mode and no_face_mode
    let faceMode = 'auto';
    let noFaceMode = 'padding';
    if (orientation === '16:9') {
      faceMode = 'none';
      noFaceMode = 'zoom';
    } else if (orientation === '1:1') {
      faceMode = 'auto';
      noFaceMode = 'padding';
    }

    const minDur = Math.max(10, targetDuration - 15);
    const maxDur = targetDuration;

    const requestPayload: JobRunRequest = {
      input_source: inputMode === 'youtube' ? 'youtube' : 'upload',
      url: inputMode === 'youtube' ? youtubeUrl.trim() : undefined,
      video_path: (inputMode === 'upload' || inputMode === 'path') ? videoPath.trim() : undefined,
      project_name: projectName.trim() || undefined,
      workflow,
      model,
      language,
      whisper_preset: preset === 'fast' ? 'fast' : preset === 'accurate' ? 'accurate' : 'balanced',
      min_duration: minDur,
      max_duration: maxDur,
      segments,
      viral,
      face_mode: faceMode,
      no_face_mode: noFaceMode,
    };

    try {
      const res = await jobsApi.run(requestPayload);
      setTrackedJobId(res.job_id);
      logBufferRef.current.push(`[System] Job launched successfully. ID: ${res.job_id}`);
      onRefreshActiveJob?.();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to launch job';
      setErrorMessage(msg);
      logBufferRef.current.push(`[System Error] ${msg}`);
    } finally {
      setIsSubmitting(false);
    }
  };

  // Cancel Job Trigger
  const handleCancelJob = async () => {
    const activeId = activeJob?.job?.job_id || trackedJobId;
    if (!activeId) return;

    setIsCancelling(true);
    try {
      await jobsApi.cancel(activeId);
      logBufferRef.current.push(`[System] Job ${activeId} cancellation requested.`);
      onRefreshActiveJob?.();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to cancel job';
      setErrorMessage(msg);
    } finally {
      setIsCancelling(false);
    }
  };

  const handleCopyLogs = () => {
    navigator.clipboard.writeText(logs.join('\n'));
    setCopiedLogs(true);
    setTimeout(() => setCopiedLogs(false), 2000);
  };

  const currentRunning = activeJob?.active && activeJob.job;

  return (
    <div className="space-y-6">
      {/* Active Job Status Banner */}
      {currentRunning && (
        <div className="bg-red-950/40 border border-red-800/60 rounded-xl p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="space-y-1">
            <div className="flex items-center space-x-2">
              <span className="relative flex h-3 w-3">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-3 w-3 bg-red-500"></span>
              </span>
              <span className="text-sm font-semibold text-white">
                Active Job: <code className="font-mono text-xs text-red-300">{activeJob.job?.job_id}</code>
              </span>
              <span className="rounded bg-red-900/60 px-2 py-0.5 text-xs font-medium text-red-200 uppercase">
                {activeJob.job?.status}
              </span>
            </div>
            <div className="flex items-center space-x-4 text-xs text-zinc-400">
              {activeJob.job?.stage && <span>Stage: {activeJob.job.stage}</span>}
              {typeof activeJob.job?.percent === 'number' && <span>{activeJob.job.percent}%</span>}
              {activeJob.job?.elapsed && <span>Elapsed: {activeJob.job.elapsed}</span>}
            </div>
            {typeof activeJob.job?.percent === 'number' && (
              <div className="w-full bg-zinc-800 rounded-full h-1.5 mt-2 max-w-md">
                <div
                  className="bg-red-500 h-1.5 rounded-full transition-all duration-300"
                  style={{ width: `${Math.min(100, Math.max(0, activeJob.job.percent))}%` }}
                />
              </div>
            )}
          </div>

          <button
            onClick={handleCancelJob}
            disabled={isCancelling}
            className="flex items-center justify-center space-x-1.5 px-4 py-2 rounded-lg bg-red-800 hover:bg-red-700 text-white text-xs font-semibold transition-colors disabled:opacity-50"
          >
            {isCancelling ? <Loader2 className="h-4 w-4 animate-spin" /> : <Square className="h-4 w-4" />}
            <span>Cancel Job</span>
          </button>
        </div>
      )}

      {/* Main Grid: Controls + Live Stream Console */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Generator Controls Form */}
        <div className="lg:col-span-6 space-y-6">
          <form onSubmit={handleRunJob} className="bg-zinc-900 border border-zinc-800 rounded-xl p-5 space-y-5">
            <div className="flex items-center space-x-2 border-b border-zinc-800 pb-3">
              <Sliders className="h-5 w-5 text-red-400" />
              <h2 className="text-base font-semibold text-white">Generator Controls</h2>
            </div>

            {/* Error Message */}
            {errorMessage && (
              <div className="flex items-center space-x-2 text-xs text-red-400 bg-red-950/40 border border-red-800/60 p-3 rounded-lg">
                <AlertCircle className="h-4 w-4 shrink-0" />
                <span>{errorMessage}</span>
              </div>
            )}

            {/* 1. Preset Selector */}
            <div className="space-y-1.5">
              <label htmlFor="generator-preset-select" className="block text-xs font-medium text-zinc-300">Preset</label>
              <select
                id="generator-preset-select"
                aria-label="Preset"
                value={preset}
                onChange={(e) => handlePresetChange(e.target.value as GeneratorPreset)}
                className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-100 focus:outline-none focus:border-red-500"
              >
                <option value="viral_shorts">Viral Shorts (9:16, 60s, Balanced Whisper)</option>
                <option value="fast">Fast Preview (Cut Only, 30s, Tiny Whisper)</option>
                <option value="balanced">Balanced (Full Pipeline, large-v3-turbo)</option>
                <option value="accurate">Accurate (Full Pipeline, large-v3)</option>
                <option value="custom">Custom Parameters</option>
              </select>
            </div>

            {/* 2. Target Duration & Orientation Controls */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <div className="flex justify-between items-center">
                  <label htmlFor="target-duration-input" className="block text-xs font-medium text-zinc-300">Target Duration</label>
                  <span className="text-xs font-mono text-red-400">{targetDuration}s</span>
                </div>
                <input
                  id="target-duration-input"
                  type="range"
                  aria-label="Target Duration"
                  min={15}
                  max={180}
                  step={5}
                  value={targetDuration}
                  onChange={(e) => setTargetDuration(Number(e.target.value))}
                  className="w-full accent-red-500 cursor-pointer"
                />
              </div>

              <div className="space-y-1.5">
                <label htmlFor="orientation-select" className="block text-xs font-medium text-zinc-300">Orientation</label>
                <select
                  id="orientation-select"
                  aria-label="Orientation"
                  value={orientation}
                  onChange={(e) => setOrientation(e.target.value as VideoOrientation)}
                  className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-100 focus:outline-none focus:border-red-500"
                >
                  <option value="9:16">9:16 (Vertical Shorts / TikTok)</option>
                  <option value="16:9">16:9 (Landscape YouTube)</option>
                  <option value="1:1">1:1 (Square Feed)</option>
                </select>
              </div>
            </div>

            {/* 3. Whisper Model & Language Selectors */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <label htmlFor="whisper-model-select" className="block text-xs font-medium text-zinc-300">Whisper Model</label>
                <select
                  id="whisper-model-select"
                  aria-label="Whisper Model"
                  value={model}
                  onChange={(e) => setModel(e.target.value)}
                  className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-100 focus:outline-none focus:border-red-500"
                >
                  <option value="large-v3-turbo">large-v3-turbo (Recommended)</option>
                  <option value="large-v3">large-v3 (Accurate)</option>
                  <option value="medium">medium (Standard)</option>
                  <option value="small">small (Lightweight)</option>
                  <option value="base">base (Ultra Fast)</option>
                  <option value="tiny">tiny (Fastest)</option>
                </select>
              </div>

              <div className="space-y-1.5">
                <label htmlFor="language-select" className="block text-xs font-medium text-zinc-300">Language</label>
                <select
                  id="language-select"
                  aria-label="Language"
                  value={language}
                  onChange={(e) => setLanguage(e.target.value)}
                  className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-100 focus:outline-none focus:border-red-500"
                >
                  <option value="auto">Auto Detect</option>
                  <option value="en">English (en)</option>
                  <option value="pt">Portuguese (pt)</option>
                  <option value="es">Spanish (es)</option>
                  <option value="id">Indonesian (id)</option>
                  <option value="fr">French (fr)</option>
                  <option value="de">German (de)</option>
                  <option value="ja">Japanese (ja)</option>
                </select>
              </div>
            </div>

            {/* 4. File Selection */}
            <div className="space-y-3 border-t border-zinc-800 pt-4">
              <div className="flex items-center justify-between">
                <span className="text-xs font-medium text-zinc-300">Video Source</span>
                <div className="flex space-x-1 text-xs">
                  <button
                    type="button"
                    onClick={() => setInputMode('upload')}
                    className={`px-2.5 py-1 rounded ${
                      inputMode === 'upload' ? 'bg-red-600 text-white' : 'bg-zinc-800 text-zinc-400 hover:text-zinc-200'
                    }`}
                  >
                    Upload
                  </button>
                  <button
                    type="button"
                    onClick={() => setInputMode('youtube')}
                    className={`px-2.5 py-1 rounded ${
                      inputMode === 'youtube' ? 'bg-red-600 text-white' : 'bg-zinc-800 text-zinc-400 hover:text-zinc-200'
                    }`}
                  >
                    YouTube
                  </button>
                  <button
                    type="button"
                    onClick={() => setInputMode('path')}
                    className={`px-2.5 py-1 rounded ${
                      inputMode === 'path' ? 'bg-red-600 text-white' : 'bg-zinc-800 text-zinc-400 hover:text-zinc-200'
                    }`}
                  >
                    File Path
                  </button>
                </div>
              </div>

              {inputMode === 'upload' && (
                <div className="space-y-2">
                  <input
                    type="file"
                    ref={fileInputRef}
                    onChange={handleFileUpload}
                    accept="video/*"
                    className="hidden"
                  />
                  <button
                    type="button"
                    onClick={() => fileInputRef.current?.click()}
                    disabled={isUploading}
                    className="w-full border-2 border-dashed border-zinc-700 hover:border-red-500 rounded-lg p-4 text-center text-xs text-zinc-400 hover:text-zinc-200 transition-colors flex flex-col items-center justify-center space-y-2"
                  >
                    <Upload className="h-6 w-6 text-zinc-500" />
                    <span>{videoPath ? `Selected: ${videoPath}` : 'Click to select or drop video file'}</span>
                  </button>

                  {isUploading && (
                    <div className="space-y-1">
                      <div className="flex justify-between text-xs text-zinc-400">
                        <span>{uploadStatus}</span>
                        <span>{uploadProgress}%</span>
                      </div>
                      <div className="w-full bg-zinc-800 rounded-full h-1.5">
                        <div
                          className="bg-red-500 h-1.5 rounded-full transition-all duration-200"
                          style={{ width: `${uploadProgress}%` }}
                        />
                      </div>
                    </div>
                  )}
                </div>
              )}

              {inputMode === 'youtube' && (
                <div className="space-y-1.5">
                  <input
                    type="url"
                    value={youtubeUrl}
                    onChange={(e) => setYoutubeUrl(e.target.value)}
                    placeholder="https://www.youtube.com/watch?v=..."
                    className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-100 focus:outline-none focus:border-red-500"
                  />
                </div>
              )}

              {inputMode === 'path' && (
                <div className="space-y-1.5">
                  <input
                    type="text"
                    value={videoPath}
                    onChange={(e) => setVideoPath(e.target.value)}
                    placeholder="/path/to/source/video.mp4"
                    className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-100 focus:outline-none focus:border-red-500"
                  />
                </div>
              )}

              <div className="space-y-1.5">
                <label htmlFor="project-name-input" className="block text-xs font-medium text-zinc-400">Project Name (Optional)</label>
                <input
                  id="project-name-input"
                  type="text"
                  value={projectName}
                  onChange={(e) => setProjectName(e.target.value)}
                  placeholder="e.g. MyShortsProject"
                  className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-xs text-zinc-200 focus:outline-none focus:border-zinc-500"
                />
              </div>
            </div>

            {/* Run Trigger Button */}
            <button
              type="submit"
              data-testid="run-job-button"
              disabled={isSubmitting || Boolean(currentRunning)}
              className="w-full flex items-center justify-center space-x-2 rounded-lg bg-red-600 hover:bg-red-500 text-white px-4 py-2.5 text-sm font-semibold transition-colors disabled:opacity-50 disabled:cursor-not-allowed shadow-md shadow-red-950/50"
            >
              {isSubmitting ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  <span>Launching Job...</span>
                </>
              ) : (
                <>
                  <Play className="h-4 w-4 fill-white" />
                  <span>Generate Viral Clips</span>
                </>
              )}
            </button>
          </form>
        </div>

        {/* Live SSE Stream Console */}
        <div className="lg:col-span-6 flex flex-col space-y-4">
          <div className="flex-1 bg-zinc-900 border border-zinc-800 rounded-xl flex flex-col overflow-hidden min-h-[460px]">
            {/* Console Toolbar */}
            <div className="flex items-center justify-between border-b border-zinc-800 bg-zinc-950/60 px-4 py-2.5">
              <div className="flex items-center space-x-2">
                <Terminal className="h-4 w-4 text-red-400" />
                <span className="text-xs font-mono font-semibold text-zinc-200">Execution Log Stream</span>
                {trackedJobId && (
                  <span className="rounded bg-zinc-800 px-1.5 py-0.5 text-[10px] font-mono text-zinc-400">
                    {trackedJobId}
                  </span>
                )}
              </div>

              <div className="flex items-center space-x-2 text-xs">
                <label className="flex items-center space-x-1.5 text-zinc-400 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={autoScroll}
                    onChange={(e) => setAutoScroll(e.target.checked)}
                    className="rounded bg-zinc-800 border-zinc-700 text-red-600 focus:ring-0 h-3.5 w-3.5"
                  />
                  <span>Auto-scroll</span>
                </label>

                <button
                  type="button"
                  onClick={handleCopyLogs}
                  className="flex items-center space-x-1 px-2 py-1 rounded bg-zinc-800 hover:bg-zinc-700 text-zinc-300 transition-colors"
                >
                  {copiedLogs ? <Check className="h-3 w-3 text-emerald-400" /> : <Copy className="h-3 w-3" />}
                  <span>Copy</span>
                </button>

                <button
                  type="button"
                  onClick={() => setLogs([])}
                  className="px-2 py-1 rounded bg-zinc-800 hover:bg-zinc-700 text-zinc-400 hover:text-zinc-200 transition-colors"
                >
                  Clear
                </button>
              </div>
            </div>

            {/* Console Log Lines */}
            <div
              ref={logContainerRef}
              className="flex-1 p-4 font-mono text-xs text-zinc-300 overflow-y-auto space-y-1 bg-black/40"
            >
              {logs.length === 0 ? (
                <div className="h-full flex flex-col items-center justify-center text-zinc-600 space-y-2 py-12">
                  <Terminal className="h-8 w-8 stroke-[1.5]" />
                  <span>No log output yet. Launch a job to see real-time output.</span>
                </div>
              ) : (
                logs.map((line, idx) => (
                  <div
                    key={idx}
                    className={`leading-relaxed whitespace-pre-wrap break-all ${
                      line.includes('[System Error]') || line.includes('ERROR')
                        ? 'text-red-400'
                        : line.includes('[System]')
                        ? 'text-cyan-400 font-semibold'
                        : line.includes('WARNING')
                        ? 'text-amber-400'
                        : line.includes('Progress:') || line.includes('%')
                        ? 'text-emerald-400'
                        : 'text-zinc-300'
                    }`}
                  >
                    {line}
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default GeneratorTab;
