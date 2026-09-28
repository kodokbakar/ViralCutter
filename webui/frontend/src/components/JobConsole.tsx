import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  Play,
  Square,
  Terminal,
  RotateCcw,
  Sliders,
  Copy,
  Check,
  AlertCircle,
  Clock,
  Sparkles,
  Layers,
  Scissors,
} from 'lucide-react';
import { jobsApi } from '../api/client';
import type { JobRunRequest, JobResponse, ActiveJobResponse } from '../api/types';

interface JobConsoleProps {
  activeJob: ActiveJobResponse | null;
  onRefreshActiveJob: () => void;
  defaultVideoPath?: string;
  defaultProjectName?: string;
}

export const JobConsole: React.FC<JobConsoleProps> = ({
  activeJob,
  onRefreshActiveJob,
  defaultVideoPath = '',
  defaultProjectName = '',
}) => {
  // Form State
  const [inputSource, setInputSource] = useState<'youtube' | 'upload' | 'gdrive' | 'existing'>('youtube');
  const [youtubeUrl, setYoutubeUrl] = useState('');
  const [videoPath, setVideoPath] = useState(defaultVideoPath);
  const [projectName, setProjectName] = useState(defaultProjectName);
  const [gdriveUrl, setGdriveUrl] = useState('');

  // Pipeline Parameters
  const [workflow, setWorkflow] = useState<'1' | '2' | '3'>('1');
  const [segments, setSegments] = useState(3);
  const [viral, setViral] = useState(true);
  const [minDuration, setMinDuration] = useState(15);
  const [maxDuration, setMaxDuration] = useState(90);

  // Whisper & Audio
  const [whisperModel, setWhisperModel] = useState('large-v3-turbo');
  const [language, setLanguage] = useState('auto');

  // AI Backend
  const [aiBackend, setAiBackend] = useState<'gemini' | 'g4f' | 'local' | 'custom' | 'manual'>('gemini');
  const [apiKey, setApiKey] = useState('');
  const [aiBaseUrl, setAiBaseUrl] = useState('');
  const [aiModelName, setAiModelName] = useState('');

  // Smart Clipping
  const [smartClipping, setSmartClipping] = useState(false);
  const [smartClippingMode, setSmartClippingMode] = useState<'splice' | 'continuous'>('splice');
  const [smartRemoveDeadAir, setSmartRemoveDeadAir] = useState(false);

  // Face Framing
  const [faceModel, setFaceModel] = useState<'insightface' | 'mediapipe'>('insightface');
  const [faceMode, setFaceMode] = useState<'auto' | '1' | '2' | 'none'>('auto');
  const [focusActiveSpeaker, setFocusActiveSpeaker] = useState(false);

  // UI / Execution State
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isCancelling, setIsCancelling] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [logs, setLogs] = useState<string[]>([]);
  const [autoScroll, setAutoScroll] = useState(true);
  const [copiedLogs, setCopiedLogs] = useState(false);

  const logContainerRef = useRef<HTMLDivElement>(null);
  const logBufferRef = useRef<string[]>([]);
  const animationFrameId = useRef<number | null>(null);

  // Sync defaults if props change
  useEffect(() => {
    if (defaultVideoPath) {
      setVideoPath(defaultVideoPath);
      setInputSource('upload');
    }
    if (defaultProjectName) {
      setProjectName(defaultProjectName);
    }
  }, [defaultVideoPath, defaultProjectName]);

  // Flush buffer to state on animation frame to avoid UI freezing
  const flushLogs = useCallback(() => {
    if (logBufferRef.current.length > 0) {
      const incoming = [...logBufferRef.current];
      logBufferRef.current = [];
      setLogs((prev) => {
        const combined = prev.concat(incoming);
        // Retain last 1,500 lines to prevent memory explosion
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
    const isRunning = activeJob?.active && activeJob.job?.status === 'running';
    if (!isRunning || !activeJob?.job?.job_id) return;

    const cleanup = jobsApi.streamLogs(
      activeJob.job.job_id,
      (line: string) => {
        logBufferRef.current.push(line);
      },
      () => {
        // SSE error or disconnect
      }
    );

    return () => {
      cleanup();
    };
  }, [activeJob?.active, activeJob?.job?.status, activeJob?.job?.job_id]);

  // Polling active job periodically
  useEffect(() => {
    const interval = setInterval(() => {
      onRefreshActiveJob();
    }, 3000);
    return () => clearInterval(interval);
  }, [onRefreshActiveJob]);

  // Handle Run
  const handleRunJob = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage(null);
    setIsSubmitting(true);

    const payload: JobRunRequest = {
      input_source: inputSource,
      workflow,
      segments: Number(segments),
      viral,
      min_duration: Number(minDuration),
      max_duration: Number(maxDuration),
      model: whisperModel,
      language,
      ai_backend: aiBackend,
      smart_clipping: smartClipping,
      smart_clipping_mode: smartClippingMode,
      smart_remove_dead_air: smartRemoveDeadAir,
      face_model: faceModel,
      face_mode: faceMode,
      focus_active_speaker: focusActiveSpeaker,
    };

    if (inputSource === 'youtube') {
      if (!youtubeUrl.trim()) {
        setErrorMessage('YouTube URL is required');
        setIsSubmitting(false);
        return;
      }
      payload.url = youtubeUrl.trim();
    } else if (inputSource === 'upload') {
      if (!videoPath.trim()) {
        setErrorMessage('Video path is required');
        setIsSubmitting(false);
        return;
      }
      payload.video_path = videoPath.trim();
    } else if (inputSource === 'gdrive') {
      if (!gdriveUrl.trim()) {
        setErrorMessage('Google Drive URL is required');
        setIsSubmitting(false);
        return;
      }
      payload.gdrive_url = gdriveUrl.trim();
    } else if (inputSource === 'existing') {
      if (!projectName.trim()) {
        setErrorMessage('Project name is required');
        setIsSubmitting(false);
        return;
      }
      payload.project_name = projectName.trim();
    }

    if (projectName.trim()) {
      payload.project_name = projectName.trim();
    }

    if (apiKey.trim()) payload.api_key = apiKey.trim();
    if (aiBaseUrl.trim()) payload.ai_base_url = aiBaseUrl.trim();
    if (aiModelName.trim()) payload.ai_model_name = aiModelName.trim();

    try {
      setLogs([]);
      logBufferRef.current = [`[INFO] Starting job execution...`];
      const res: JobResponse = await jobsApi.run(payload);
      logBufferRef.current.push(`[INFO] Job spawned with ID: ${res.job_id}`);
      onRefreshActiveJob();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to launch job';
      setErrorMessage(msg);
      logBufferRef.current.push(`[ERROR] ${msg}`);
    } finally {
      setIsSubmitting(false);
    }
  };

  // Handle Cancel
  const handleCancelJob = async () => {
    if (!activeJob?.job?.job_id) return;
    setIsCancelling(true);
    setErrorMessage(null);
    try {
      await jobsApi.cancel(activeJob.job.job_id);
      logBufferRef.current.push(`[INFO] Job cancellation requested.`);
      onRefreshActiveJob();
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

  const currentJob = activeJob?.job;
  const isJobRunning = Boolean(activeJob?.active && currentJob?.status === 'running');

  const getStatusBadge = (status?: string) => {
    switch (status) {
      case 'running':
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-amber-950/80 text-amber-300 border border-amber-800">
            <span className="w-1.5 h-1.5 mr-1.5 bg-amber-400 rounded-full animate-ping" />
            Running
          </span>
        );
      case 'completed':
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-emerald-950/80 text-emerald-300 border border-emerald-800">
            Completed
          </span>
        );
      case 'failed':
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-red-950/80 text-red-300 border border-red-800">
            Failed
          </span>
        );
      case 'cancelled':
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-zinc-800 text-zinc-300 border border-zinc-700">
            Cancelled
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-zinc-900 text-zinc-400 border border-zinc-800">
            Idle
          </span>
        );
    }
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
      {/* Parameters Form Panel */}
      <div className="lg:col-span-5 space-y-6">
        <form onSubmit={handleRunJob} className="bg-zinc-900 border border-zinc-800 rounded-xl p-5 space-y-5">
          <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
            <div className="flex items-center space-x-2">
              <Sliders className="h-5 w-5 text-red-400" />
              <h2 className="text-base font-semibold text-white">Pipeline Parameters</h2>
            </div>
            {getStatusBadge(currentJob?.status)}
          </div>

          {errorMessage && (
            <div className="flex items-start space-x-2 rounded-lg bg-red-950/50 border border-red-800/80 p-3 text-sm text-red-300">
              <AlertCircle className="h-4 w-4 mt-0.5 shrink-0 text-red-400" />
              <span>{errorMessage}</span>
            </div>
          )}

          {/* Section 1: Input Source */}
          <div className="space-y-3">
            <label className="text-xs font-medium uppercase tracking-wider text-zinc-400">Input Source</label>
            <div className="grid grid-cols-4 gap-2">
              {(['youtube', 'upload', 'gdrive', 'existing'] as const).map((source) => (
                <button
                  type="button"
                  key={source}
                  onClick={() => setInputSource(source)}
                  className={`rounded-lg py-1.5 text-xs font-medium capitalize border transition-colors ${
                    inputSource === source
                      ? 'bg-red-950/60 border-red-600/70 text-red-200'
                      : 'bg-zinc-800/60 border-zinc-700/60 text-zinc-400 hover:bg-zinc-800 hover:text-zinc-200'
                  }`}
                >
                  {source}
                </button>
              ))}
            </div>

            {inputSource === 'youtube' && (
              <div>
                <input
                  type="url"
                  placeholder="https://www.youtube.com/watch?v=..."
                  value={youtubeUrl}
                  onChange={(e) => setYoutubeUrl(e.target.value)}
                  className="w-full rounded-lg bg-zinc-950 border border-zinc-800 px-3 py-2 text-sm text-zinc-100 placeholder-zinc-500 focus:border-red-500 focus:outline-none"
                />
              </div>
            )}

            {inputSource === 'upload' && (
              <div>
                <input
                  type="text"
                  placeholder="/path/to/video.mp4 or uploaded file"
                  value={videoPath}
                  onChange={(e) => setVideoPath(e.target.value)}
                  className="w-full rounded-lg bg-zinc-950 border border-zinc-800 px-3 py-2 text-sm text-zinc-100 placeholder-zinc-500 focus:border-red-500 focus:outline-none"
                />
              </div>
            )}

            {inputSource === 'gdrive' && (
              <div>
                <input
                  type="text"
                  placeholder="https://drive.google.com/file/d/.../view"
                  value={gdriveUrl}
                  onChange={(e) => setGdriveUrl(e.target.value)}
                  className="w-full rounded-lg bg-zinc-950 border border-zinc-800 px-3 py-2 text-sm text-zinc-100 placeholder-zinc-500 focus:border-red-500 focus:outline-none"
                />
              </div>
            )}

            {inputSource === 'existing' && (
              <div>
                <input
                  type="text"
                  placeholder="Project name in VIRALS/"
                  value={projectName}
                  onChange={(e) => setProjectName(e.target.value)}
                  className="w-full rounded-lg bg-zinc-950 border border-zinc-800 px-3 py-2 text-sm text-zinc-100 placeholder-zinc-500 focus:border-red-500 focus:outline-none"
                />
              </div>
            )}
          </div>

          {/* Section 2: Workflow & Segmentation */}
          <div className="space-y-3 pt-2 border-t border-zinc-800/80">
            <div className="flex items-center space-x-1.5 text-xs font-medium uppercase tracking-wider text-zinc-400">
              <Layers className="h-3.5 w-3.5 text-red-400" />
              <span>Workflow & Segments</span>
            </div>

            <div className="grid grid-cols-3 gap-2">
              <label className="text-xs text-zinc-400 block col-span-3">Workflow</label>
              {[
                { id: '1', label: '1: Full' },
                { id: '2', label: '2: Cut' },
                { id: '3', label: '3: Subs' },
              ].map((wf) => (
                <button
                  type="button"
                  key={wf.id}
                  onClick={() => setWorkflow(wf.id as '1' | '2' | '3')}
                  className={`rounded-lg py-1.5 text-xs font-medium border transition-colors ${
                    workflow === wf.id
                      ? 'bg-zinc-800 border-zinc-600 text-white'
                      : 'bg-zinc-950 border-zinc-800 text-zinc-400 hover:bg-zinc-900'
                  }`}
                >
                  {wf.label}
                </button>
              ))}
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs text-zinc-400 block mb-1">Segments</label>
                <input
                  type="number"
                  min="1"
                  max="10"
                  value={segments}
                  onChange={(e) => setSegments(parseInt(e.target.value) || 1)}
                  className="w-full rounded-lg bg-zinc-950 border border-zinc-800 px-3 py-1.5 text-sm text-zinc-100 focus:border-red-500 focus:outline-none"
                />
              </div>
              <div className="flex items-center space-x-2 pt-5">
                <input
                  type="checkbox"
                  id="viral"
                  checked={viral}
                  onChange={(e) => setViral(e.target.checked)}
                  className="h-4 w-4 rounded border-zinc-700 bg-zinc-950 text-red-600 focus:ring-0 focus:ring-offset-0"
                />
                <label htmlFor="viral" className="text-xs font-medium text-zinc-300 cursor-pointer">
                  Viral Scoring
                </label>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs text-zinc-400 block mb-1">Min Duration (s)</label>
                <input
                  type="number"
                  min="5"
                  max="120"
                  value={minDuration}
                  onChange={(e) => setMinDuration(parseInt(e.target.value) || 15)}
                  className="w-full rounded-lg bg-zinc-950 border border-zinc-800 px-3 py-1.5 text-sm text-zinc-100 focus:border-red-500 focus:outline-none"
                />
              </div>
              <div>
                <label className="text-xs text-zinc-400 block mb-1">Max Duration (s)</label>
                <input
                  type="number"
                  min="15"
                  max="300"
                  value={maxDuration}
                  onChange={(e) => setMaxDuration(parseInt(e.target.value) || 90)}
                  className="w-full rounded-lg bg-zinc-950 border border-zinc-800 px-3 py-1.5 text-sm text-zinc-100 focus:border-red-500 focus:outline-none"
                />
              </div>
            </div>
          </div>

          {/* Section 3: AI & Whisper */}
          <div className="space-y-3 pt-2 border-t border-zinc-800/80">
            <div className="flex items-center space-x-1.5 text-xs font-medium uppercase tracking-wider text-zinc-400">
              <Sparkles className="h-3.5 w-3.5 text-red-400" />
              <span>Whisper & LLM Backend</span>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs text-zinc-400 block mb-1">Whisper Model</label>
                <select
                  value={whisperModel}
                  onChange={(e) => setWhisperModel(e.target.value)}
                  className="w-full rounded-lg bg-zinc-950 border border-zinc-800 px-2.5 py-1.5 text-sm text-zinc-100 focus:border-red-500 focus:outline-none"
                >
                  <option value="large-v3-turbo">large-v3-turbo</option>
                  <option value="medium">medium</option>
                  <option value="small">small</option>
                  <option value="base">base</option>
                  <option value="tiny">tiny</option>
                </select>
              </div>

              <div>
                <label className="text-xs text-zinc-400 block mb-1">Language</label>
                <select
                  value={language}
                  onChange={(e) => setLanguage(e.target.value)}
                  className="w-full rounded-lg bg-zinc-950 border border-zinc-800 px-2.5 py-1.5 text-sm text-zinc-100 focus:border-red-500 focus:outline-none"
                >
                  <option value="auto">Auto Detect</option>
                  <option value="en">English (en)</option>
                  <option value="id">Indonesian (id)</option>
                  <option value="es">Spanish (es)</option>
                  <option value="ja">Japanese (ja)</option>
                </select>
              </div>
            </div>

            <div>
              <label className="text-xs text-zinc-400 block mb-1">AI Backend</label>
              <select
                value={aiBackend}
                onChange={(e) => setAiBackend(e.target.value as any)}
                className="w-full rounded-lg bg-zinc-950 border border-zinc-800 px-2.5 py-1.5 text-sm text-zinc-100 focus:border-red-500 focus:outline-none"
              >
                <option value="gemini">Gemini</option>
                <option value="g4f">g4f (Free)</option>
                <option value="local">Local LLM</option>
                <option value="custom">Custom (OpenAI API)</option>
                <option value="manual">Manual</option>
              </select>
            </div>

            {aiBackend !== 'g4f' && aiBackend !== 'manual' && (
              <div className="space-y-2">
                <input
                  type="password"
                  placeholder="API Key (Gemini or Custom OpenAI)"
                  value={apiKey}
                  onChange={(e) => setApiKey(e.target.value)}
                  className="w-full rounded-lg bg-zinc-950 border border-zinc-800 px-3 py-1.5 text-sm text-zinc-100 placeholder-zinc-500 focus:border-red-500 focus:outline-none"
                />
                <input
                  type="text"
                  placeholder="Model Name Override (e.g. gpt-4o, gemini-2.0-flash)"
                  value={aiModelName}
                  onChange={(e) => setAiModelName(e.target.value)}
                  className="w-full rounded-lg bg-zinc-950 border border-zinc-800 px-3 py-1.5 text-sm text-zinc-100 placeholder-zinc-500 focus:border-red-500 focus:outline-none"
                />
                {aiBackend === 'custom' && (
                  <input
                    type="url"
                    placeholder="Custom Base URL (e.g. https://api.groq.com/openai/v1)"
                    value={aiBaseUrl}
                    onChange={(e) => setAiBaseUrl(e.target.value)}
                    className="w-full rounded-lg bg-zinc-950 border border-zinc-800 px-3 py-1.5 text-sm text-zinc-100 placeholder-zinc-500 focus:border-red-500 focus:outline-none"
                  />
                )}
              </div>
            )}
          </div>

          {/* Section 4: Smart Clipping & Face Detection */}
          <div className="space-y-3 pt-2 border-t border-zinc-800/80">
            <div className="flex items-center space-x-1.5 text-xs font-medium uppercase tracking-wider text-zinc-400">
              <Scissors className="h-3.5 w-3.5 text-red-400" />
              <span>Smart Clipping & Face Framing</span>
            </div>

            <div className="flex items-center justify-between">
              <label className="text-xs text-zinc-300">Enable Smart Clipping</label>
              <input
                type="checkbox"
                checked={smartClipping}
                onChange={(e) => setSmartClipping(e.target.checked)}
                className="h-4 w-4 rounded border-zinc-700 bg-zinc-950 text-red-600 focus:ring-0"
              />
            </div>

            {smartClipping && (
              <div className="grid grid-cols-2 gap-3 pl-2 border-l-2 border-red-900/50">
                <div>
                  <label className="text-xs text-zinc-400 block mb-1">Mode</label>
                  <select
                    value={smartClippingMode}
                    onChange={(e) => setSmartClippingMode(e.target.value as any)}
                    className="w-full rounded-lg bg-zinc-950 border border-zinc-800 px-2 py-1 text-xs text-zinc-100"
                  >
                    <option value="splice">Splice</option>
                    <option value="continuous">Continuous</option>
                  </select>
                </div>
                <div className="flex items-center space-x-2 pt-4">
                  <input
                    type="checkbox"
                    id="deadair"
                    checked={smartRemoveDeadAir}
                    onChange={(e) => setSmartRemoveDeadAir(e.target.checked)}
                    className="h-4 w-4 rounded border-zinc-700 bg-zinc-950 text-red-600"
                  />
                  <label htmlFor="deadair" className="text-xs text-zinc-400">
                    Jump-cut Silence
                  </label>
                </div>
              </div>
            )}

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs text-zinc-400 block mb-1">Face Detection</label>
                <select
                  value={faceModel}
                  onChange={(e) => setFaceModel(e.target.value as any)}
                  className="w-full rounded-lg bg-zinc-950 border border-zinc-800 px-2 py-1.5 text-xs text-zinc-100"
                >
                  <option value="insightface">InsightFace (High Accuracy)</option>
                  <option value="mediapipe">MediaPipe (Fast CPU)</option>
                </select>
              </div>
              <div>
                <label className="text-xs text-zinc-400 block mb-1">Framing Mode</label>
                <select
                  value={faceMode}
                  onChange={(e) => setFaceMode(e.target.value as any)}
                  className="w-full rounded-lg bg-zinc-950 border border-zinc-800 px-2 py-1.5 text-xs text-zinc-100"
                >
                  <option value="auto">Auto</option>
                  <option value="1">1 Speaker</option>
                  <option value="2">2 Speakers</option>
                  <option value="none">None (Full Center)</option>
                </select>
              </div>
            </div>

            <div className="flex items-center space-x-2 pt-1">
              <input
                type="checkbox"
                id="active_speaker"
                checked={focusActiveSpeaker}
                onChange={(e) => setFocusActiveSpeaker(e.target.checked)}
                className="h-4 w-4 rounded border-zinc-700 bg-zinc-950 text-red-600"
              />
              <label htmlFor="active_speaker" className="text-xs text-zinc-400 cursor-pointer">
                Focus Active Speaker
              </label>
            </div>
          </div>

          {/* Action Buttons */}
          <div className="pt-3 border-t border-zinc-800 flex space-x-3">
            <button
              type="submit"
              disabled={isSubmitting || isJobRunning}
              className={`flex-1 flex items-center justify-center space-x-2 rounded-lg py-2.5 px-4 text-sm font-semibold transition-colors ${
                isJobRunning
                  ? 'bg-zinc-800 text-zinc-500 cursor-not-allowed'
                  : 'bg-red-600 hover:bg-red-500 text-white shadow-lg shadow-red-600/20'
              }`}
            >
              <Play className="h-4 w-4 fill-current" />
              <span>{isSubmitting ? 'Starting...' : 'Run Processing'}</span>
            </button>

            {isJobRunning && (
              <button
                type="button"
                onClick={handleCancelJob}
                disabled={isCancelling}
                className="flex items-center space-x-2 rounded-lg bg-zinc-800 hover:bg-red-950 border border-zinc-700 hover:border-red-700 px-4 py-2.5 text-sm font-medium text-red-400 transition-colors"
              >
                <Square className="h-4 w-4 fill-current" />
                <span>{isCancelling ? 'Cancelling...' : 'Cancel Job'}</span>
              </button>
            )}
          </div>
        </form>
      </div>

      {/* Live SSE Log Console Panel */}
      <div className="lg:col-span-7 flex flex-col bg-zinc-900 border border-zinc-800 rounded-xl overflow-hidden min-h-[500px]">
        {/* Terminal Header */}
        <div className="flex items-center justify-between px-4 py-3 bg-zinc-950 border-b border-zinc-800">
          <div className="flex items-center space-x-2">
            <Terminal className="h-4 w-4 text-zinc-400" />
            <span className="text-xs font-mono uppercase tracking-wider text-zinc-300">
              Live Process Stream
            </span>
            {currentJob?.job_id && (
              <span className="font-mono text-xs text-zinc-500">
                ({currentJob.job_id.substring(0, 8)})
              </span>
            )}
          </div>

          <div className="flex items-center space-x-3">
            <label className="flex items-center space-x-1.5 text-xs text-zinc-400 cursor-pointer">
              <input
                type="checkbox"
                checked={autoScroll}
                onChange={(e) => setAutoScroll(e.target.checked)}
                className="h-3.5 w-3.5 rounded border-zinc-700 bg-zinc-950 text-red-600"
              />
              <span>Auto-scroll</span>
            </label>

            <button
              onClick={() => setLogs([])}
              className="p-1 rounded text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800"
              title="Clear Console"
            >
              <RotateCcw className="h-3.5 w-3.5" />
            </button>

            <button
              onClick={handleCopyLogs}
              className="flex items-center space-x-1 px-2 py-1 rounded text-xs bg-zinc-800 hover:bg-zinc-700 text-zinc-300"
            >
              {copiedLogs ? <Check className="h-3.5 w-3.5 text-emerald-400" /> : <Copy className="h-3.5 w-3.5" />}
              <span>{copiedLogs ? 'Copied' : 'Copy'}</span>
            </button>
          </div>
        </div>

        {/* Terminal Output */}
        <div
          ref={logContainerRef}
          className="flex-1 p-4 font-mono text-xs text-zinc-300 overflow-y-auto bg-black/90 space-y-1 select-text leading-relaxed"
        >
          {logs.length === 0 ? (
            <div className="h-full flex flex-col items-center justify-center text-zinc-600 space-y-2 py-20">
              <Terminal className="h-8 w-8 text-zinc-700" />
              <p>No active output stream. Launch a job to see live logs.</p>
            </div>
          ) : (
            logs.map((log, idx) => {
              const isError = log.includes('[ERROR]') || log.toLowerCase().includes('traceback');
              const isWarning = log.includes('[WARN]') || log.includes('WARNING');
              const isInfo = log.includes('[INFO]');
              return (
                <div
                  key={idx}
                  className={`break-all ${
                    isError
                      ? 'text-red-400'
                      : isWarning
                      ? 'text-amber-300'
                      : isInfo
                      ? 'text-zinc-400'
                      : 'text-zinc-200'
                  }`}
                >
                  {log}
                </div>
              );
            })
          )}
        </div>

        {/* Console Footer / Status Summary */}
        {currentJob && (
          <div className="flex items-center justify-between px-4 py-2.5 bg-zinc-950/80 border-t border-zinc-800/80 text-xs text-zinc-400">
            <div className="flex items-center space-x-3">
              {currentJob.started_at && (
                <span className="flex items-center space-x-1">
                  <Clock className="h-3.5 w-3.5 text-zinc-500" />
                  <span>
                    Started:{' '}
                    {typeof currentJob.started_at === 'number'
                      ? new Date(currentJob.started_at * 1000).toLocaleTimeString()
                      : String(currentJob.started_at)}
                  </span>
                </span>
              )}
              {currentJob.ended_at && (
                <span>
                  Finished:{' '}
                  {typeof currentJob.ended_at === 'number'
                    ? new Date(currentJob.ended_at * 1000).toLocaleTimeString()
                    : String(currentJob.ended_at)}
                </span>
              )}
            </div>
            <div>
              {currentJob.return_code !== null && currentJob.return_code !== undefined && (
                <span className={currentJob.return_code === 0 ? 'text-emerald-400' : 'text-red-400'}>
                  Exit Code: {currentJob.return_code}
                </span>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
