import React, { useState, useEffect, useRef } from 'react';
import {
  Subtitles,
  Terminal,
  Upload,
  Play,
  Square,
  AlertCircle,
  Copy,
  Check,
  Loader2,
  FileText,
} from 'lucide-react';
import { jobsApi, uploadApi } from '../api/client';
import type { JobRunRequest } from '../api/types';

export interface SubtitlesTabProps {
  defaultVideoPath?: string;
  defaultProjectName?: string;
}

export const SubtitlesTab: React.FC<SubtitlesTabProps> = ({
  defaultVideoPath = '',
  defaultProjectName = '',
}) => {
  // Input Selection
  const [videoPath, setVideoPath] = useState<string>(defaultVideoPath);
  const [projectName, setProjectName] = useState<string>(defaultProjectName);
  const [isUploading, setIsUploading] = useState<boolean>(false);
  const [uploadStatus, setUploadStatus] = useState<string>('');

  // Generation Parameters
  const [model, setModel] = useState<string>('large-v3-turbo');
  const [language, setLanguage] = useState<string>('auto');
  const [prompt, setPrompt] = useState<string>('');
  const [whisperPreset, setWhisperPreset] = useState<string>('balanced');
  const [translateTarget, setTranslateTarget] = useState<string>('None');

  // Execution & Logs
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [isCancelling, setIsCancelling] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const [logs, setLogs] = useState<string[]>([]);
  const [autoScroll, setAutoScroll] = useState<boolean>(true);
  const [copiedLogs, setCopiedLogs] = useState<boolean>(false);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const logContainerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (defaultVideoPath) setVideoPath(defaultVideoPath);
    if (defaultProjectName) setProjectName(defaultProjectName);
  }, [defaultVideoPath, defaultProjectName]);

  // Connect SSE log stream when a job is active
  useEffect(() => {
    if (!activeJobId) return;

    setLogs((prev) => [...prev, `[System] Connected to log stream for subtitle task ${activeJobId}`]);
    const cleanup = jobsApi.streamLogs(
      activeJobId,
      (line) => {
        setLogs((prev) => {
          const next = [...prev, line];
          return next.length > 1000 ? next.slice(next.length - 1000) : next;
        });
      },
      () => {
        // SSE disconnected / ended
      }
    );

    return () => {
      cleanup();
    };
  }, [activeJobId]);

  // Auto-scroll logs
  useEffect(() => {
    if (autoScroll && logContainerRef.current) {
      logContainerRef.current.scrollTop = logContainerRef.current.scrollHeight;
    }
  }, [logs, autoScroll]);

  // Handle File Upload
  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setIsUploading(true);
    setUploadStatus('Uploading video for subtitles...');
    setErrorMessage(null);

    try {
      const res = await uploadApi.uploadSingle(file, projectName.trim() || undefined);
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

  // Run Subtitles Generation Task
  const handleGenerateSubtitles = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage(null);

    if (!videoPath.trim() && !projectName.trim()) {
      setErrorMessage('Please specify a video file path or project name');
      return;
    }

    setIsSubmitting(true);
    setLogs(['[System] Initiating subtitle generation task...']);

    const payload: JobRunRequest = {
      workflow: '3', // Subtitles only
      video_path: videoPath.trim() || undefined,
      project_name: projectName.trim() || undefined,
      model,
      language,
      prompt_template: prompt.trim() || undefined,
      whisper_preset: whisperPreset,
      translate_target: translateTarget !== 'None' ? translateTarget : undefined,
    };

    try {
      const res = await jobsApi.run(payload);
      setActiveJobId(res.job_id);
      setLogs((prev) => [...prev, `[System] Subtitle task started. ID: ${res.job_id}`]);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to launch subtitle task';
      setErrorMessage(msg);
      setLogs((prev) => [...prev, `[System Error] ${msg}`]);
    } finally {
      setIsSubmitting(false);
    }
  };

  // Cancel Job
  const handleCancel = async () => {
    if (!activeJobId) return;
    setIsCancelling(true);
    try {
      await jobsApi.cancel(activeJobId);
      setLogs((prev) => [...prev, `[System] Subtitle task ${activeJobId} cancelled.`]);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Cancel failed';
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

  return (
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
      {/* Subtitle Parameters Form */}
      <div className="lg:col-span-6 space-y-6">
        <form onSubmit={handleGenerateSubtitles} className="bg-zinc-900 border border-zinc-800 rounded-xl p-5 space-y-5">
          <div className="flex items-center space-x-2 border-b border-zinc-800 pb-3">
            <Subtitles className="h-5 w-5 text-red-400" />
            <div>
              <h2 className="text-base font-semibold text-white">Subtitle Generator</h2>
              <p className="text-xs text-zinc-400">AI audio transcription & subtitle generation</p>
            </div>
          </div>

          {errorMessage && (
            <div className="flex items-center space-x-2 text-xs text-red-400 bg-red-950/40 border border-red-800/60 p-3 rounded-lg">
              <AlertCircle className="h-4 w-4 shrink-0" />
              <span>{errorMessage}</span>
            </div>
          )}

          {/* Video Input */}
          <div className="space-y-2">
            <div className="flex justify-between items-center">
              <label htmlFor="subtitles-video-path" className="block text-xs font-medium text-zinc-300">Video File or Project</label>
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                disabled={isUploading}
                className="text-xs text-red-400 hover:text-red-300 flex items-center space-x-1 disabled:opacity-50"
              >
                {isUploading ? <Loader2 className="h-3 w-3 animate-spin" /> : <Upload className="h-3 w-3" />}
                <span>{isUploading ? 'Uploading...' : 'Upload New'}</span>
              </button>
            </div>
            <input
              type="file"
              ref={fileInputRef}
              onChange={handleFileUpload}
              accept="video/*"
              className="hidden"
            />
            <input
              id="subtitles-video-path"
              type="text"
              value={videoPath}
              onChange={(e) => setVideoPath(e.target.value)}
              placeholder="/path/to/video.mp4 or select file"
              className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-100 focus:outline-none focus:border-red-500"
            />
            {uploadStatus && <p className="text-xs text-emerald-400">{uploadStatus}</p>}
          </div>

          {/* Model & Language Controls */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <label htmlFor="subtitles-whisper-model" className="block text-xs font-medium text-zinc-300">Whisper Model</label>
              <select
                id="subtitles-whisper-model"
                aria-label="Whisper Model"
                value={model}
                onChange={(e) => setModel(e.target.value)}
                className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-100 focus:outline-none focus:border-red-500"
              >
                <option value="large-v3-turbo">large-v3-turbo (Fast & Accurate)</option>
                <option value="large-v3">large-v3 (Accurate, Heavy)</option>
                <option value="medium">medium (Balanced)</option>
                <option value="small">small (Fast)</option>
                <option value="base">base (Ultra Fast)</option>
                <option value="tiny">tiny (Fastest)</option>
              </select>
            </div>

            <div className="space-y-1.5">
              <label htmlFor="subtitles-language" className="block text-xs font-medium text-zinc-300">Language</label>
              <select
                id="subtitles-language"
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
                <option value="zh">Chinese (zh)</option>
              </select>
            </div>
          </div>

          {/* Prompt & Transcription Hints */}
          <div className="space-y-1.5">
            <label htmlFor="subtitles-prompt" className="block text-xs font-medium text-zinc-300">Prompt / Transcription Vocabulary</label>
            <textarea
              id="subtitles-prompt"
              rows={3}
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder="Names, technical terms, specific vocabulary or spelling hints to guide Whisper..."
              className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-100 focus:outline-none focus:border-red-500"
            />
          </div>

          {/* Whisper Preset & Translation */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <label htmlFor="subtitles-whisper-preset" className="block text-xs font-medium text-zinc-300">Preset Strategy</label>
              <select
                id="subtitles-whisper-preset"
                aria-label="Preset Strategy"
                value={whisperPreset}
                onChange={(e) => setWhisperPreset(e.target.value)}
                className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-100 focus:outline-none focus:border-red-500"
              >
                <option value="balanced">Balanced</option>
                <option value="fast">Fast (Lower Precision)</option>
                <option value="accurate">Accurate (High Precision)</option>
                <option value="custom">Custom</option>
              </select>
            </div>

            <div className="space-y-1.5">
              <label htmlFor="subtitles-translate-target" className="block text-xs font-medium text-zinc-300">Translate Target</label>
              <select
                id="subtitles-translate-target"
                aria-label="Translate Target"
                value={translateTarget}
                onChange={(e) => setTranslateTarget(e.target.value)}
                className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-100 focus:outline-none focus:border-red-500"
              >
                <option value="None">None (Original Language)</option>
                <option value="en">English (en)</option>
                <option value="es">Spanish (es)</option>
                <option value="pt">Portuguese (pt)</option>
                <option value="id">Indonesian (id)</option>
              </select>
            </div>
          </div>

          {/* Trigger Task Button */}
          <button
            type="submit"
            data-testid="generate-subtitles-button"
            disabled={isSubmitting || Boolean(activeJobId)}
            className="w-full flex items-center justify-center space-x-2 rounded-lg bg-red-600 hover:bg-red-500 text-white px-4 py-2.5 text-sm font-semibold transition-colors disabled:opacity-50"
          >
            {isSubmitting ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                <span>Launching Subtitle Task...</span>
              </>
            ) : (
              <>
                <Play className="h-4 w-4 fill-white" />
                <span>Generate Subtitles</span>
              </>
            )}
          </button>
        </form>
      </div>

      {/* Task Output & Console */}
      <div className="lg:col-span-6 flex flex-col space-y-4">
        <div className="flex-1 bg-zinc-900 border border-zinc-800 rounded-xl flex flex-col overflow-hidden min-h-[460px]">
          <div className="flex items-center justify-between border-b border-zinc-800 bg-zinc-950/60 px-4 py-2.5">
            <div className="flex items-center space-x-2">
              <Terminal className="h-4 w-4 text-red-400" />
              <span className="text-xs font-mono font-semibold text-zinc-200">Subtitle Task Stream</span>
              {activeJobId && (
                <span className="rounded bg-red-950/80 border border-red-800 px-2 py-0.5 text-[10px] font-mono text-red-300">
                  {activeJobId}
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

              {activeJobId && (
                <button
                  type="button"
                  onClick={handleCancel}
                  disabled={isCancelling}
                  className="flex items-center space-x-1 px-2 py-1 rounded bg-red-950/80 hover:bg-red-900 text-red-300 border border-red-800/80"
                >
                  <Square className="h-3 w-3" />
                  <span>Cancel</span>
                </button>
              )}

              <button
                type="button"
                onClick={handleCopyLogs}
                className="flex items-center space-x-1 px-2 py-1 rounded bg-zinc-800 hover:bg-zinc-700 text-zinc-300"
              >
                {copiedLogs ? <Check className="h-3 w-3 text-emerald-400" /> : <Copy className="h-3 w-3" />}
                <span>Copy</span>
              </button>

              <button
                type="button"
                onClick={() => setLogs([])}
                className="px-2 py-1 rounded bg-zinc-800 hover:bg-zinc-700 text-zinc-400 hover:text-zinc-200"
              >
                Clear
              </button>
            </div>
          </div>

          <div
            ref={logContainerRef}
            className="flex-1 p-4 font-mono text-xs text-zinc-300 overflow-y-auto space-y-1 bg-black/40"
          >
            {logs.length === 0 ? (
              <div className="h-full flex flex-col items-center justify-center text-zinc-600 space-y-2 py-12">
                <FileText className="h-8 w-8 stroke-[1.5]" />
                <span>Ready to generate subtitles. Configure parameters and click generate.</span>
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
  );
};

export default SubtitlesTab;
