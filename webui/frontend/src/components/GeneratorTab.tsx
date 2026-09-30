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
  Download,
  ExternalLink,
  ChevronDown,
  ChevronUp,
  CheckCircle2,
  Video,
  UserCheck,
  Sparkles,
  Share2,
} from 'lucide-react';
import { jobsApi, uploadApi, systemApi, libraryApi, gdriveApi, previewApi } from '../api/client';
import type { JobRunRequest, ActiveJobResponse, TestAiResponse, AssetItem } from '../api/types';

export interface GeneratorTabProps {
  activeJob?: ActiveJobResponse | null;
  onRefreshActiveJob?: () => void;
  defaultVideoPath?: string;
  defaultProjectName?: string;
  onNavigateTab?: (tab: string, projectName?: string) => void;
}

export type GeneratorPreset = 'viral_shorts' | 'fast' | 'balanced' | 'accurate' | 'custom';
export type VideoOrientation = '9:16' | '16:9' | '1:1';
export type InputMode = 'upload' | 'youtube' | 'path';

function usePersistedState<T>(key: string, defaultValue: T): [T, React.Dispatch<React.SetStateAction<T>>] {
  const [state, setState] = useState<T>(() => {
    try {
      if (typeof window !== 'undefined' && window.localStorage) {
        const saved = window.localStorage.getItem(`viralcutter_${key}`);
        if (saved !== null) {
          return JSON.parse(saved);
        }
      }
    } catch {
      // Fallback to default
    }
    return defaultValue;
  });

  useEffect(() => {
    try {
      if (typeof window !== 'undefined' && window.localStorage) {
        window.localStorage.setItem(`viralcutter_${key}`, JSON.stringify(state));
      }
    } catch {
      // Ignore write errors
    }
  }, [key, state]);

  return [state, setState];
}

function formatBytes(bytes?: number): string {
  if (!bytes) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
}

export const GeneratorTab: React.FC<GeneratorTabProps> = ({
  activeJob,
  onRefreshActiveJob,
  defaultVideoPath = '',
  defaultProjectName = '',
  onNavigateTab,
}) => {
  // Preset & Core Pipeline Parameters
  const [preset, setPreset] = useState<GeneratorPreset>('viral_shorts');
  const [targetDuration, setTargetDuration] = useState<number>(60);
  const [orientation, setOrientation] = useState<VideoOrientation>('9:16');
  const [model, setModel] = useState<string>('large-v3-turbo');
  const [workflow, setWorkflow] = useState<'1' | '2' | '3'>('1');
  const [language, setLanguage] = useState<string>('auto');

  // Whisper Performance Tuning (Persisted)
  const [whisperBatchSize, setWhisperBatchSize] = usePersistedState<number>('whisper_batch_size', 8);
  const [whisperChunkSize, setWhisperChunkSize] = usePersistedState<number>('whisper_chunk_size', 10);

  // Segmentation & Duration Parity Parameters (Persisted)
  const [segments, setSegments] = usePersistedState<number>('segments', 3);
  const [viral, setViral] = usePersistedState<boolean>('viral', true);
  const [themes, setThemes] = usePersistedState<string>('themes', '');
  const [minDuration, setMinDuration] = usePersistedState<number>('min_duration', 15);
  const [maxDuration, setMaxDuration] = usePersistedState<number>('max_duration', 90);
  const [preRoll, setPreRoll] = usePersistedState<number>('pre_roll', 1.25);
  const [postRoll, setPostRoll] = usePersistedState<number>('post_roll', 0.75);

  // Subtitle Workflow Toggles (Persisted)
  const [burnSubtitles, setBurnSubtitles] = usePersistedState<boolean>('burn_subtitles', true);
  const [useCustomSubs, setUseCustomSubs] = usePersistedState<boolean>('use_custom_subs', false);
  const [enableHookHeader, setEnableHookHeader] = usePersistedState<boolean>('enable_hook_header', true);
  const [hookHeaderStyle, setHookHeaderStyle] = usePersistedState<'yellow_box' | 'white_box' | 'neon'>(
    'hook_header_style',
    'yellow_box'
  );

  // AI Backend Parameters (Persisted)
  const [aiBackend, setAiBackend] = usePersistedState<'gemini' | 'g4f' | 'local' | 'custom' | 'manual'>(
    'ai_backend',
    'gemini'
  );
  const [apiKey, setApiKey] = usePersistedState<string>('api_key', '');
  const [aiBaseUrl, setAiBaseUrl] = usePersistedState<string>('ai_base_url', '');
  const [aiModelName, setAiModelName] = usePersistedState<string>('ai_model_name', '');
  const [isTestingAi, setIsTestingAi] = useState<boolean>(false);
  const [aiTestResult, setAiTestResult] = useState<TestAiResponse | null>(null);

  // Face & Framing Settings (Persisted)
  const [faceMode, setFaceMode] = usePersistedState<string>('face_mode', 'auto');
  const [faceModel, setFaceModel] = usePersistedState<string>('face_model', 'insightface');
  const [noFaceMode, setNoFaceMode] = usePersistedState<string>('no_face_mode', 'padding');
  const [facePreset, setFacePreset] = usePersistedState<string>('face_preset', 'default');
  const [faceFilterThreshold, setFaceFilterThreshold] = usePersistedState<number>('face_filter_threshold', 0.35);
  const [faceTwoThreshold, setFaceTwoThreshold] = usePersistedState<number>('face_two_threshold', 0.60);
  const [faceConfidenceThreshold, setFaceConfidenceThreshold] = usePersistedState<number>('face_confidence_threshold', 0.30);
  const [faceDeadZone, setFaceDeadZone] = usePersistedState<string>('face_dead_zone', '40');

  // Active Speaker & Motion Settings (Persisted)
  const [showFaceAdvanced, setShowFaceAdvanced] = useState<boolean>(false);
  const [focusActiveSpeaker, setFocusActiveSpeaker] = usePersistedState<boolean>('focus_active_speaker', false);
  const [activeSpeakerMar, setActiveSpeakerMar] = usePersistedState<number>('active_speaker_mar', 0.03);
  const [activeSpeakerScoreDiff, setActiveSpeakerScoreDiff] = usePersistedState<number>('active_speaker_score_diff', 1.5);
  const [activeSpeakerDecay, setActiveSpeakerDecay] = usePersistedState<number>('active_speaker_decay', 2.0);
  const [includeMotion, setIncludeMotion] = usePersistedState<boolean>('include_motion', false);
  const [activeSpeakerMotionThreshold, setActiveSpeakerMotionThreshold] = usePersistedState<number>(
    'active_speaker_motion_threshold',
    3.0
  );
  const [activeSpeakerMotionSensitivity, setActiveSpeakerMotionSensitivity] = usePersistedState<number>(
    'active_speaker_motion_sensitivity',
    0.05
  );

  // Smart Clipping Parameters (Persisted)
  const [showSmartClipping, setShowSmartClipping] = useState<boolean>(false);
  const [smartClipping, setSmartClipping] = usePersistedState<boolean>('smart_clipping', false);
  const [smartClippingMode, setSmartClippingMode] = usePersistedState<'splice' | 'continuous'>('smart_clipping_mode', 'splice');
  const [smartSnapMargin, setSmartSnapMargin] = usePersistedState<number>('smart_snap_margin', 0.05);
  const [smartRemoveDeadAir, setSmartRemoveDeadAir] = usePersistedState<boolean>('smart_remove_dead_air', false);
  const [smartSilenceThreshold, setSmartSilenceThreshold] = usePersistedState<number>('smart_silence_threshold', 0.6);

  // AI Prompt Template Editor (Persisted)
  const [showPromptEditor, setShowPromptEditor] = useState<boolean>(false);
  const [promptTemplate, setPromptTemplate] = usePersistedState<string>('prompt_template', '');
  const [promptSavedMsg, setPromptSavedMsg] = useState<boolean>(false);

  // File Selection State
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

  // Completed Clips Preview & Export State
  const [outputClips, setOutputClips] = useState<AssetItem[]>([]);
  const [selectedClip, setSelectedClip] = useState<AssetItem | null>(null);
  const [isExportingGdrive, setIsExportingGdrive] = useState<boolean>(false);
  const [gdriveExportMsg, setGdriveExportMsg] = useState<string | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const logContainerRef = useRef<HTMLDivElement>(null);
  const logBufferRef = useRef<string[]>([]);

  // Preset Handler
  const handlePresetChange = (newPreset: GeneratorPreset) => {
    setPreset(newPreset);
    switch (newPreset) {
      case 'viral_shorts':
        setModel('large-v3-turbo');
        setTargetDuration(60);
        setMaxDuration(60);
        setMinDuration(15);
        setOrientation('9:16');
        setWorkflow('1');
        setBurnSubtitles(true);
        setViral(true);
        setSegments(3);
        break;
      case 'fast':
        setModel('tiny');
        setTargetDuration(30);
        setMaxDuration(30);
        setMinDuration(10);
        setOrientation('9:16');
        setWorkflow('2'); // Cut only
        setBurnSubtitles(false);
        setViral(true);
        setSegments(2);
        break;
      case 'balanced':
        setModel('large-v3-turbo');
        setTargetDuration(60);
        setMaxDuration(60);
        setMinDuration(15);
        setOrientation('9:16');
        setWorkflow('1');
        setBurnSubtitles(true);
        setViral(true);
        setSegments(3);
        break;
      case 'accurate':
        setModel('large-v3');
        setTargetDuration(90);
        setMaxDuration(90);
        setMinDuration(20);
        setOrientation('9:16');
        setWorkflow('1');
        setBurnSubtitles(true);
        setViral(true);
        setSegments(5);
        break;
      case 'custom':
        break;
    }
  };

  // Face Presets Handler
  const handleFacePresetChange = (p: string) => {
    setFacePreset(p);
    switch (p) {
      case 'default':
        setFaceFilterThreshold(0.35);
        setFaceTwoThreshold(0.60);
        setFaceConfidenceThreshold(0.30);
        setFaceDeadZone('40');
        break;
      case 'stable':
        setFaceFilterThreshold(0.45);
        setFaceTwoThreshold(0.70);
        setFaceConfidenceThreshold(0.40);
        setFaceDeadZone('60');
        break;
      case 'sensitive':
        setFaceFilterThreshold(0.20);
        setFaceTwoThreshold(0.50);
        setFaceConfidenceThreshold(0.20);
        setFaceDeadZone('20');
        break;
      case 'high_precision':
        setFaceFilterThreshold(0.50);
        setFaceTwoThreshold(0.75);
        setFaceConfidenceThreshold(0.50);
        setFaceDeadZone('50');
        break;
    }
  };

  // Synchronize Default Props
  useEffect(() => {
    if (defaultVideoPath) {
      setVideoPath(defaultVideoPath);
      setInputMode('path');
    }
    if (defaultProjectName) {
      setProjectName(defaultProjectName);
    }
  }, [defaultVideoPath, defaultProjectName]);

  // Synchronize Active Job
  useEffect(() => {
    if (activeJob?.active && activeJob.job?.job_id) {
      setTrackedJobId(activeJob.job.job_id);
    }
  }, [activeJob]);

  // Smooth Log Buffering with Background-Resilient Timer
  const flushLogs = useCallback(() => {
    if (logBufferRef.current.length > 0) {
      const incoming = [...logBufferRef.current];
      logBufferRef.current = [];
      setLogs((prev) => {
        const combined = prev.concat(incoming);
        return combined.length > 1500 ? combined.slice(combined.length - 1500) : combined;
      });
    }
  }, []);

  useEffect(() => {
    const timerId = setInterval(flushLogs, 100);
    return () => {
      clearInterval(timerId);
    };
  }, [flushLogs]);

  // Smart Auto-scroll: Only auto-scroll if near bottom
  useEffect(() => {
    if (autoScroll && logContainerRef.current) {
      const { scrollHeight, scrollTop, clientHeight } = logContainerRef.current;
      const isAtBottom = scrollHeight - scrollTop <= clientHeight + 80;
      if (isAtBottom) {
        logContainerRef.current.scrollTop = scrollHeight;
      }
    }
  }, [logs, autoScroll]);

  // Refresh Output Clips When Job Completes
  const fetchCompletedClips = useCallback(async (proj: string) => {
    if (!proj) return;
    try {
      const assets = await libraryApi.listAssets(proj);
      const clips = (assets || []).filter(
        (a: AssetItem) => a.asset_type === 'video' || a.name.toLowerCase().endsWith('.mp4')
      );
      setOutputClips(clips);
      if (clips.length > 0 && !selectedClip) {
        setSelectedClip(clips[0]);
      }
    } catch {
      // Ignored if project folder doesn't exist yet
    }
  }, [selectedClip]);

  useEffect(() => {
    if (activeJob?.job?.status === 'completed' && projectName) {
      fetchCompletedClips(projectName);
    }
  }, [activeJob, projectName, fetchCompletedClips]);

  // Stable callback refs to keep SSE stream subscription independent of non-critical props
  const onRefreshActiveJobRef = useRef(onRefreshActiveJob);
  useEffect(() => {
    onRefreshActiveJobRef.current = onRefreshActiveJob;
  }, [onRefreshActiveJob]);

  const projectNameRef = useRef(projectName);
  useEffect(() => {
    projectNameRef.current = projectName;
  }, [projectName]);

  const fetchCompletedClipsRef = useRef(fetchCompletedClips);
  useEffect(() => {
    fetchCompletedClipsRef.current = fetchCompletedClips;
  }, [fetchCompletedClips]);

  // Live SSE Stream Connection
  useEffect(() => {
    if (!trackedJobId) return;

    logBufferRef.current.push(`[System] Connecting to SSE log stream for job ${trackedJobId}...`);
    flushLogs();

    const cleanup = jobsApi.streamLogs(
      trackedJobId,
      (line) => {
        if (!line || line.startsWith(':')) return;

        if (logBufferRef.current.length === 0) {
          logBufferRef.current.push(line);
          flushLogs();
        } else {
          logBufferRef.current.push(line);
        }

        if (line.includes('COMPLETED') || line.includes('Finished processing')) {
          onRefreshActiveJobRef.current?.();
          if (projectNameRef.current) {
            fetchCompletedClipsRef.current(projectNameRef.current);
          }
        }
      },
      () => {
        onRefreshActiveJobRef.current?.();
        if (projectNameRef.current) {
          fetchCompletedClipsRef.current(projectNameRef.current);
        }
      }
    );

    return () => {
      cleanup();
    };
  }, [trackedJobId, flushLogs]);

  // AI Connection Test
  const handleTestAiConnection = async () => {
    setIsTestingAi(true);
    setAiTestResult(null);
    try {
      const res = await systemApi.testAi({
        backend: aiBackend,
        base_url: aiBaseUrl.trim() || undefined,
        api_key: apiKey.trim() || undefined,
        model_name: aiModelName.trim() || undefined,
      });
      setAiTestResult(res);
    } catch (err: unknown) {
      setAiTestResult({
        success: false,
        message: err instanceof Error ? err.message : 'Connection test failed',
      });
    } finally {
      setIsTestingAi(false);
    }
  };

  // Export to Google Drive Handler
  const handleExportToGDrive = async () => {
    if (!projectName.trim()) {
      setErrorMessage('Project name is required to export to Google Drive');
      return;
    }
    setIsExportingGdrive(true);
    setGdriveExportMsg(null);
    try {
      const res = await gdriveApi.exportToDrive({
        project_name: projectName.trim(),
        destination_folder: '/content/drive/MyDrive/ViralCutter_Exports',
      });
      setGdriveExportMsg(`Exported to: ${res.destination}`);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Google Drive export failed';
      setGdriveExportMsg(`Export failed: ${msg}`);
    } finally {
      setIsExportingGdrive(false);
    }
  };

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

    // Map orientation and face controls
    let effectiveFaceMode = faceMode;
    let effectiveNoFaceMode = noFaceMode;
    if (orientation === '16:9') {
      effectiveFaceMode = 'none';
      effectiveNoFaceMode = 'zoom';
    } else if (orientation === '1:1' && faceMode === 'auto') {
      effectiveFaceMode = 'auto';
      effectiveNoFaceMode = 'padding';
    }

    // Determine workflow: if burnSubtitles is false, force Cut Only ("2")
    const effectiveWorkflow = !burnSubtitles ? '2' : workflow;

    const requestPayload: JobRunRequest = {
      input_source: inputMode === 'youtube' ? 'youtube' : 'upload',
      url: inputMode === 'youtube' ? youtubeUrl.trim() : undefined,
      video_path: inputMode === 'upload' || inputMode === 'path' ? videoPath.trim() : undefined,
      project_name: projectName.trim() || undefined,
      workflow: effectiveWorkflow,
      model,
      language,
      whisper_preset: preset === 'fast' ? 'fast' : preset === 'accurate' ? 'accurate' : 'balanced',
      whisper_batch_size: whisperBatchSize,
      whisper_chunk_size: whisperChunkSize,

      // Segmentation & Duration
      segments,
      viral,
      themes: !viral && themes.trim() ? themes.trim() : undefined,
      min_duration: minDuration,
      max_duration: maxDuration,
      pre_roll: preRoll,
      post_roll: postRoll,

      // AI Backend
      ai_backend: aiBackend,
      api_key: apiKey.trim() || undefined,
      ai_base_url: aiBaseUrl.trim() || undefined,
      ai_model_name: aiModelName.trim() || undefined,
      prompt_template: promptTemplate.trim() || undefined,

      // Face Detection & Framing
      face_mode: effectiveFaceMode,
      face_model: faceModel,
      no_face_mode: effectiveNoFaceMode,
      face_filter_threshold: faceFilterThreshold,
      face_two_threshold: faceTwoThreshold,
      face_confidence_threshold: faceConfidenceThreshold,
      face_dead_zone: faceDeadZone,

      // Active Speaker & Motion
      focus_active_speaker: focusActiveSpeaker,
      active_speaker_mar: activeSpeakerMar,
      active_speaker_score_diff: activeSpeakerScoreDiff,
      active_speaker_decay: activeSpeakerDecay,
      include_motion: includeMotion,
      active_speaker_motion_threshold: activeSpeakerMotionThreshold,
      active_speaker_motion_sensitivity: activeSpeakerMotionSensitivity,

      // Smart Clipping
      smart_clipping: smartClipping,
      smart_clipping_mode: smartClippingMode,
      smart_snap_margin: smartSnapMargin,
      smart_remove_dead_air: smartRemoveDeadAir,
      smart_silence_threshold: smartSilenceThreshold,

      // Subtitles & Hook Header
      use_custom_subs: useCustomSubs,
      enable_hook_header: enableHookHeader,
      hook_header_style: hookHeaderStyle,
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
              <label htmlFor="generator-preset-select" className="block text-xs font-medium text-zinc-300">
                Preset
              </label>
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
                  <label htmlFor="target-duration-input" className="block text-xs font-medium text-zinc-300">
                    Target Duration
                  </label>
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
                  onChange={(e) => {
                    const val = Number(e.target.value);
                    setTargetDuration(val);
                    setMaxDuration(val);
                  }}
                  className="w-full accent-red-500 cursor-pointer"
                />
              </div>

              <div className="space-y-1.5">
                <label htmlFor="orientation-select" className="block text-xs font-medium text-zinc-300">
                  Orientation
                </label>
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
                <label htmlFor="whisper-model-select" className="block text-xs font-medium text-zinc-300">
                  Whisper Model
                </label>
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
                <label htmlFor="language-select" className="block text-xs font-medium text-zinc-300">
                  Language
                </label>
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

            {/* Whisper Performance Tuning */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <label htmlFor="whisper-batch-size-input" className="block text-xs font-medium text-zinc-300">
                  Whisper Batch Size
                </label>
                <input
                  id="whisper-batch-size-input"
                  type="number"
                  min={1}
                  max={64}
                  value={whisperBatchSize}
                  onChange={(e) => setWhisperBatchSize(Math.max(1, Math.min(64, parseInt(e.target.value) || 1)))}
                  className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-100 focus:outline-none focus:border-red-500"
                />
              </div>

              <div className="space-y-1.5">
                <label htmlFor="whisper-chunk-size-input" className="block text-xs font-medium text-zinc-300">
                  Whisper Chunk Size (s)
                </label>
                <input
                  id="whisper-chunk-size-input"
                  type="number"
                  min={5}
                  max={60}
                  value={whisperChunkSize}
                  onChange={(e) => setWhisperChunkSize(Math.max(5, Math.min(60, parseInt(e.target.value) || 5)))}
                  className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-100 focus:outline-none focus:border-red-500"
                />
              </div>
            </div>

            {/* 4. Segmentation & Timing Parity Controls */}
            <div className="space-y-3 border-t border-zinc-800 pt-4">
              <span className="text-xs font-medium uppercase tracking-wider text-zinc-400 block">
                Segmentation & Timing
              </span>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                <div className="space-y-1">
                  <label className="text-[11px] text-zinc-400 block">Segments</label>
                  <input
                    type="number"
                    min={1}
                    max={20}
                    value={segments}
                    onChange={(e) => setSegments(parseInt(e.target.value) || 1)}
                    className="w-full rounded bg-zinc-800 border border-zinc-700 px-2.5 py-1.5 text-xs text-zinc-100"
                  />
                </div>
                <div className="space-y-1">
                  <label className="text-[11px] text-zinc-400 block">Min Dur (s)</label>
                  <input
                    type="number"
                    min={5}
                    max={120}
                    value={minDuration}
                    onChange={(e) => setMinDuration(parseInt(e.target.value) || 10)}
                    className="w-full rounded bg-zinc-800 border border-zinc-700 px-2.5 py-1.5 text-xs text-zinc-100"
                  />
                </div>
                <div className="space-y-1">
                  <label className="text-[11px] text-zinc-400 block">Max Dur (s)</label>
                  <input
                    type="number"
                    min={15}
                    max={300}
                    value={maxDuration}
                    onChange={(e) => setMaxDuration(parseInt(e.target.value) || 60)}
                    className="w-full rounded bg-zinc-800 border border-zinc-700 px-2.5 py-1.5 text-xs text-zinc-100"
                  />
                </div>
                <div className="space-y-1">
                  <label className="text-[11px] text-zinc-400 block">Pre/Post Roll</label>
                  <div className="flex space-x-1">
                    <input
                      type="number"
                      step={0.25}
                      value={preRoll}
                      onChange={(e) => setPreRoll(parseFloat(e.target.value) || 1.0)}
                      className="w-1/2 rounded bg-zinc-800 border border-zinc-700 px-1 py-1.5 text-xs text-zinc-100"
                      title="Pre-roll seconds"
                    />
                    <input
                      type="number"
                      step={0.25}
                      value={postRoll}
                      onChange={(e) => setPostRoll(parseFloat(e.target.value) || 0.75)}
                      className="w-1/2 rounded bg-zinc-800 border border-zinc-700 px-1 py-1.5 text-xs text-zinc-100"
                      title="Post-roll seconds"
                    />
                  </div>
                </div>
              </div>

              {/* Viral vs Custom Themes Toggle */}
              <div className="flex items-center justify-between pt-1">
                <label className="flex items-center space-x-2 text-xs text-zinc-300 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={viral}
                    onChange={(e) => setViral(e.target.checked)}
                    className="rounded bg-zinc-800 border-zinc-700 text-red-600 focus:ring-0 h-4 w-4"
                  />
                  <span>Viral Scoring Engine</span>
                </label>
                {!viral && (
                  <input
                    type="text"
                    placeholder="Themes (e.g. tech, comedy, drama)"
                    value={themes}
                    onChange={(e) => setThemes(e.target.value)}
                    className="w-1/2 rounded bg-zinc-800 border border-zinc-700 px-2.5 py-1 text-xs text-zinc-100 placeholder-zinc-500"
                  />
                )}
              </div>
            </div>

            {/* 5. Subtitle Workflow Toggles */}
            <div className="space-y-3 border-t border-zinc-800 pt-4">
              <span className="text-xs font-medium uppercase tracking-wider text-zinc-400 block">
                Subtitle &amp; Hook Overlay
              </span>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <label className="flex items-center justify-between p-2.5 rounded-lg bg-zinc-950/60 border border-zinc-800 cursor-pointer">
                  <span className="text-xs text-zinc-200">Burn Subtitles</span>
                  <input
                    id="burn-subtitles-toggle"
                    type="checkbox"
                    checked={burnSubtitles}
                    onChange={(e) => setBurnSubtitles(e.target.checked)}
                    className="rounded bg-zinc-800 border-zinc-700 text-red-600 focus:ring-0 h-4 w-4"
                  />
                </label>

                <label className="flex items-center justify-between p-2.5 rounded-lg bg-zinc-950/60 border border-zinc-800 cursor-pointer">
                  <span className="text-xs text-zinc-200">Use Custom Subtitles</span>
                  <input
                    id="use-custom-subtitles-checkbox"
                    type="checkbox"
                    checked={useCustomSubs}
                    onChange={(e) => setUseCustomSubs(e.target.checked)}
                    className="rounded bg-zinc-800 border-zinc-700 text-red-600 focus:ring-0 h-4 w-4"
                  />
                </label>

                <label className="flex items-center justify-between p-2.5 rounded-lg bg-zinc-950/60 border border-zinc-800 cursor-pointer">
                  <div>
                    <span className="text-xs text-zinc-200 block">Hook Title Overlay</span>
                    <span className="text-[10px] text-zinc-500">Stop-the-scroll top banner</span>
                  </div>
                  <input
                    id="hook-header-toggle"
                    type="checkbox"
                    checked={enableHookHeader}
                    onChange={(e) => setEnableHookHeader(e.target.checked)}
                    className="rounded bg-zinc-800 border-zinc-700 text-red-600 focus:ring-0 h-4 w-4"
                  />
                </label>

                {enableHookHeader && (
                  <div className="flex items-center justify-between p-2.5 rounded-lg bg-zinc-950/60 border border-zinc-800">
                    <label htmlFor="hook-header-style-select" className="text-xs text-zinc-200">
                      Hook Style
                    </label>
                    <select
                      id="hook-header-style-select"
                      aria-label="Hook Style"
                      value={hookHeaderStyle}
                      onChange={(e) => setHookHeaderStyle(e.target.value as 'yellow_box' | 'white_box' | 'neon')}
                      className="bg-zinc-800 border border-zinc-700 rounded px-2 py-1 text-xs text-zinc-100 focus:outline-none focus:border-red-500"
                    >
                      <option value="yellow_box">Yellow Box</option>
                      <option value="white_box">White Box</option>
                      <option value="neon">Neon</option>
                    </select>
                  </div>
                )}
              </div>
            </div>

            {/* 6. AI Backend Configuration + Test Connection */}
            <div className="space-y-3 border-t border-zinc-800 pt-4">
              <div className="flex items-center justify-between">
                <label htmlFor="ai-backend-select" className="block text-xs font-medium text-zinc-300">
                  AI Backend
                </label>
                <button
                  type="button"
                  data-testid="test-ai-button"
                  onClick={handleTestAiConnection}
                  disabled={isTestingAi}
                  className="flex items-center space-x-1.5 px-2.5 py-1 rounded bg-zinc-800 hover:bg-zinc-700 text-zinc-300 text-xs font-medium border border-zinc-700 disabled:opacity-50 transition-colors"
                >
                  {isTestingAi ? <Loader2 className="h-3 w-3 animate-spin" /> : <Sparkles className="h-3 w-3 text-red-400" />}
                  <span>{isTestingAi ? 'Testing...' : 'Test Connection'}</span>
                </button>
              </div>

              <select
                id="ai-backend-select"
                aria-label="AI Backend"
                value={aiBackend}
                onChange={(e) => {
                  setAiBackend(e.target.value as any);
                  setAiTestResult(null);
                }}
                className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-100 focus:outline-none focus:border-red-500"
              >
                <option value="gemini">Gemini</option>
                <option value="g4f">g4f (Free)</option>
                <option value="local">Local LLM</option>
                <option value="custom">Custom (OpenAI API)</option>
                <option value="manual">Manual</option>
              </select>

              {/* AI Test Result Alert */}
              {aiTestResult && (
                <div
                  className={`flex items-center space-x-2 text-xs p-2.5 rounded-lg border ${
                    aiTestResult.success
                      ? 'bg-emerald-950/40 border-emerald-800/60 text-emerald-300'
                      : 'bg-red-950/40 border-red-800/60 text-red-400'
                  }`}
                >
                  {aiTestResult.success ? (
                    <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-400" />
                  ) : (
                    <AlertCircle className="h-4 w-4 shrink-0 text-red-400" />
                  )}
                  <span>
                    {aiTestResult.message}
                    {typeof aiTestResult.latency_ms === 'number' && ` (${aiTestResult.latency_ms}ms)`}
                  </span>
                </div>
              )}

              {aiBackend !== 'g4f' && aiBackend !== 'manual' && (
                <div className="space-y-3">
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    <div className="space-y-1.5">
                      <label htmlFor="api-key-input" className="block text-xs font-medium text-zinc-400">
                        API Key {aiBackend === 'gemini' ? '(Gemini)' : '(Custom OpenAI)'}
                      </label>
                      <input
                        id="api-key-input"
                        type="password"
                        placeholder="Enter API Key"
                        value={apiKey}
                        onChange={(e) => setApiKey(e.target.value)}
                        className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-100 placeholder-zinc-500 focus:outline-none focus:border-red-500"
                      />
                    </div>
                    <div className="space-y-1.5">
                      <label htmlFor="ai-model-input" className="block text-xs font-medium text-zinc-400">
                        Model Name Override
                      </label>
                      <input
                        id="ai-model-input"
                        type="text"
                        placeholder="e.g. gpt-4o, gemini-2.0-flash"
                        value={aiModelName}
                        onChange={(e) => setAiModelName(e.target.value)}
                        className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-100 placeholder-zinc-500 focus:outline-none focus:border-red-500"
                      />
                    </div>
                  </div>
                  {aiBackend === 'custom' && (
                    <div className="space-y-1.5">
                      <label htmlFor="ai-base-url-input" className="block text-xs font-medium text-zinc-400">
                        Custom Base URL
                      </label>
                      <input
                        id="ai-base-url-input"
                        type="url"
                        placeholder="e.g. https://api.groq.com/openai/v1"
                        value={aiBaseUrl}
                        onChange={(e) => setAiBaseUrl(e.target.value)}
                        className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-100 placeholder-zinc-500 focus:outline-none focus:border-red-500"
                      />
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* 7. Face Processing Controls Panel */}
            <div className="space-y-3 border-t border-zinc-800 pt-4">
              <span className="text-xs font-medium uppercase tracking-wider text-zinc-400 block">
                Face &amp; Framing Settings
              </span>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <div className="space-y-1">
                  <label className="text-[11px] text-zinc-400 block">Face Mode</label>
                  <select
                    value={faceMode}
                    onChange={(e) => setFaceMode(e.target.value)}
                    className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-2.5 py-1.5 text-xs text-zinc-100"
                  >
                    <option value="auto">Auto (Speaker Track)</option>
                    <option value="1">1 (Single Speaker)</option>
                    <option value="2">2 (Split Screen)</option>
                    <option value="none">None (Original Frame)</option>
                  </select>
                </div>

                <div className="space-y-1">
                  <label className="text-[11px] text-zinc-400 block">Face Model</label>
                  <select
                    value={faceModel}
                    onChange={(e) => setFaceModel(e.target.value)}
                    className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-2.5 py-1.5 text-xs text-zinc-100"
                  >
                    <option value="insightface">InsightFace (Accurate)</option>
                    <option value="mediapipe">MediaPipe (Fast CPU)</option>
                  </select>
                </div>

                <div className="space-y-1">
                  <label className="text-[11px] text-zinc-400 block">No-Face Mode</label>
                  <select
                    value={noFaceMode}
                    onChange={(e) => setNoFaceMode(e.target.value)}
                    className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-2.5 py-1.5 text-xs text-zinc-100"
                  >
                    <option value="padding">Padding (Blur / Black)</option>
                    <option value="zoom">Zoom (Crop to Fill)</option>
                  </select>
                </div>
              </div>

              {/* Face Preset Selector */}
              <div className="space-y-1">
                <label className="text-[11px] text-zinc-400 block">Face Detection Preset</label>
                <select
                  value={facePreset}
                  onChange={(e) => handleFacePresetChange(e.target.value)}
                  className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-2.5 py-1.5 text-xs text-zinc-100"
                >
                  <option value="default">Default (Balanced - 0.35 / 0.60 / 0.30)</option>
                  <option value="stable">Stable (Focus Main Speaker - 0.45 / 0.70 / 0.40)</option>
                  <option value="sensitive">Sensitive (Catch All Faces - 0.20 / 0.50 / 0.20)</option>
                  <option value="high_precision">High Precision (0.50 / 0.75 / 0.50)</option>
                </select>
              </div>

              {/* Collapsible Advanced Speaker & Motion */}
              <button
                type="button"
                onClick={() => setShowFaceAdvanced(!showFaceAdvanced)}
                className="flex items-center space-x-1 text-xs text-zinc-400 hover:text-zinc-200 transition-colors pt-1"
              >
                <UserCheck className="h-3.5 w-3.5" />
                <span>Active Speaker &amp; Motion Controls</span>
                {showFaceAdvanced ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
              </button>

              {showFaceAdvanced && (
                <div className="bg-zinc-950/70 border border-zinc-800 rounded-lg p-3 space-y-3">
                  <label className="flex items-center space-x-2 text-xs text-zinc-300 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={focusActiveSpeaker}
                      onChange={(e) => setFocusActiveSpeaker(e.target.checked)}
                      className="rounded bg-zinc-800 border-zinc-700 text-red-600 focus:ring-0 h-4 w-4"
                    />
                    <span>Focus Active Speaker (Mouth Aspect Ratio)</span>
                  </label>

                  {focusActiveSpeaker && (
                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 pt-1">
                      <div className="space-y-1">
                        <label className="text-[11px] text-zinc-400 block">MAR Thresh ({activeSpeakerMar})</label>
                        <input
                          type="range"
                          min={0.01}
                          max={0.10}
                          step={0.01}
                          value={activeSpeakerMar}
                          onChange={(e) => setActiveSpeakerMar(parseFloat(e.target.value))}
                          className="w-full accent-red-500"
                        />
                      </div>
                      <div className="space-y-1">
                        <label className="text-[11px] text-zinc-400 block">Score Diff ({activeSpeakerScoreDiff})</label>
                        <input
                          type="range"
                          min={0.5}
                          max={3.0}
                          step={0.1}
                          value={activeSpeakerScoreDiff}
                          onChange={(e) => setActiveSpeakerScoreDiff(parseFloat(e.target.value))}
                          className="w-full accent-red-500"
                        />
                      </div>
                      <div className="space-y-1">
                        <label className="text-[11px] text-zinc-400 block">Decay Rate ({activeSpeakerDecay})</label>
                        <input
                          type="range"
                          min={0.5}
                          max={5.0}
                          step={0.25}
                          value={activeSpeakerDecay}
                          onChange={(e) => setActiveSpeakerDecay(parseFloat(e.target.value))}
                          className="w-full accent-red-500"
                        />
                      </div>
                    </div>
                  )}

                  <label className="flex items-center space-x-2 text-xs text-zinc-300 cursor-pointer pt-1">
                    <input
                      type="checkbox"
                      checked={includeMotion}
                      onChange={(e) => setIncludeMotion(e.target.checked)}
                      className="rounded bg-zinc-800 border-zinc-700 text-red-600 focus:ring-0 h-4 w-4"
                    />
                    <span>Include Body Motion Sensitivity</span>
                  </label>

                  {includeMotion && (
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-1">
                      <div className="space-y-1">
                        <label className="text-[11px] text-zinc-400 block">
                          Motion Threshold ({activeSpeakerMotionThreshold})
                        </label>
                        <input
                          type="range"
                          min={1.0}
                          max={10.0}
                          step={0.5}
                          value={activeSpeakerMotionThreshold}
                          onChange={(e) => setActiveSpeakerMotionThreshold(parseFloat(e.target.value))}
                          className="w-full accent-red-500"
                        />
                      </div>
                      <div className="space-y-1">
                        <label className="text-[11px] text-zinc-400 block">
                          Motion Sensitivity ({activeSpeakerMotionSensitivity})
                        </label>
                        <input
                          type="range"
                          min={0.01}
                          max={0.20}
                          step={0.01}
                          value={activeSpeakerMotionSensitivity}
                          onChange={(e) => setActiveSpeakerMotionSensitivity(parseFloat(e.target.value))}
                          className="w-full accent-red-500"
                        />
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* 8. Smart Clipping Controls */}
            <div className="space-y-3 border-t border-zinc-800 pt-4">
              <div className="flex items-center justify-between">
                <button
                  type="button"
                  onClick={() => setShowSmartClipping(!showSmartClipping)}
                  className="flex items-center space-x-1.5 text-xs font-medium uppercase tracking-wider text-zinc-400 hover:text-zinc-200"
                >
                  <span>Smart-Clipping Controls</span>
                  {showSmartClipping ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
                </button>
                <label className="flex items-center space-x-1.5 text-xs text-zinc-300 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={smartClipping}
                    onChange={(e) => setSmartClipping(e.target.checked)}
                    className="rounded bg-zinc-800 border-zinc-700 text-red-600 focus:ring-0 h-3.5 w-3.5"
                  />
                  <span>Enable</span>
                </label>
              </div>

              {showSmartClipping && (
                <div className="bg-zinc-950/70 border border-zinc-800 rounded-lg p-3 space-y-3">
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    <div className="space-y-1">
                      <label className="text-[11px] text-zinc-400 block">Clipping Mode</label>
                      <select
                        value={smartClippingMode}
                        onChange={(e) => setSmartClippingMode(e.target.value as 'splice' | 'continuous')}
                        className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-2.5 py-1.5 text-xs text-zinc-100"
                      >
                        <option value="splice">Splice (Hook + Core + Payoff)</option>
                        <option value="continuous">Continuous (Single Topic Flow)</option>
                      </select>
                    </div>

                    <div className="space-y-1">
                      <label className="text-[11px] text-zinc-400 block">Snap Margin ({smartSnapMargin}s)</label>
                      <input
                        type="number"
                        step={0.01}
                        min={0.01}
                        max={0.5}
                        value={smartSnapMargin}
                        onChange={(e) => setSmartSnapMargin(parseFloat(e.target.value) || 0.05)}
                        className="w-full rounded bg-zinc-800 border border-zinc-700 px-2.5 py-1 text-xs text-zinc-100"
                      />
                    </div>
                  </div>

                  <div className="flex items-center justify-between pt-1">
                    <label className="flex items-center space-x-2 text-xs text-zinc-300 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={smartRemoveDeadAir}
                        onChange={(e) => setSmartRemoveDeadAir(e.target.checked)}
                        className="rounded bg-zinc-800 border-zinc-700 text-red-600 focus:ring-0 h-4 w-4"
                      />
                      <span>Remove Dead Air / Silence Jump-Cuts</span>
                    </label>

                    {smartRemoveDeadAir && (
                      <div className="flex items-center space-x-1.5">
                        <span className="text-[11px] text-zinc-400">Silence Thresh:</span>
                        <input
                          type="number"
                          step={0.1}
                          min={0.2}
                          max={3.0}
                          value={smartSilenceThreshold}
                          onChange={(e) => setSmartSilenceThreshold(parseFloat(e.target.value) || 0.6)}
                          className="w-16 rounded bg-zinc-800 border border-zinc-700 px-2 py-1 text-xs text-zinc-100 text-center"
                        />
                        <span className="text-[11px] text-zinc-500">s</span>
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>

            {/* 9. AI Prompt Template Editor */}
            <div className="space-y-3 border-t border-zinc-800 pt-4">
              <div className="flex items-center justify-between">
                <button
                  type="button"
                  onClick={() => setShowPromptEditor(!showPromptEditor)}
                  className="flex items-center space-x-1.5 text-xs font-medium uppercase tracking-wider text-zinc-400 hover:text-zinc-200"
                >
                  <span>AI Prompt Template</span>
                  {showPromptEditor ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
                </button>
                {promptTemplate && (
                  <span className="text-[10px] text-red-400 font-mono">Custom Active</span>
                )}
              </div>

              {showPromptEditor && (
                <div className="bg-zinc-950/70 border border-zinc-800 rounded-lg p-3 space-y-3">
                  <textarea
                    rows={4}
                    value={promptTemplate}
                    onChange={(e) => {
                      setPromptTemplate(e.target.value);
                      setPromptSavedMsg(false);
                    }}
                    placeholder="Enter custom prompt instructions for the LLM to identify viral hooks and segments..."
                    className="w-full rounded bg-zinc-900 border border-zinc-800 p-2.5 text-xs font-mono text-zinc-200 placeholder-zinc-600 focus:outline-none focus:border-red-500"
                  />
                  <div className="flex items-center justify-between text-xs">
                    <button
                      type="button"
                      onClick={() => {
                        setPromptTemplate('');
                        setPromptSavedMsg(false);
                      }}
                      className="text-zinc-400 hover:text-zinc-200"
                    >
                      Reset to Default
                    </button>
                    <div className="flex items-center space-x-2">
                      {promptSavedMsg && <span className="text-emerald-400 text-[11px]">Saved!</span>}
                      <button
                        type="button"
                        onClick={() => setPromptSavedMsg(true)}
                        className="px-2.5 py-1 rounded bg-zinc-800 hover:bg-zinc-700 text-zinc-200"
                      >
                        Save Template
                      </button>
                    </div>
                  </div>
                </div>
              )}
            </div>

            {/* 10. File Selection */}
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
                <label htmlFor="project-name-input" className="block text-xs font-medium text-zinc-400">
                  Project Name (Optional)
                </label>
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
        <div className="lg:col-span-6 flex flex-col space-y-6">
          {/* Execution Log Stream */}
          <div className="bg-zinc-900 border border-zinc-800 rounded-xl flex flex-col overflow-hidden h-full">
            {/* Sticky Header */}
            <div className="flex items-center justify-between border-b border-zinc-800 bg-zinc-950 px-4 py-2.5 sticky top-0 z-10">
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

            {/* Fixed-Height Container */}
            <div
              ref={logContainerRef}
              className="h-[520px] lg:h-[640px] w-full overflow-y-auto font-mono text-xs bg-zinc-950 p-4 rounded-b-lg space-y-1"
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

      {/* Generated Clips & Output Preview Section (Full Width / Span 12) */}
      <div
        data-testid="generator-output-preview"
        className="w-full bg-zinc-900 border border-zinc-800 rounded-xl p-5 space-y-4"
      >
        <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
          <div className="flex items-center space-x-2">
            <Video className="h-5 w-5 text-red-400" />
            <h3 className="text-base font-semibold text-white">Generated Clips &amp; Output Preview</h3>
          </div>
          {projectName && (
            <button
              type="button"
              onClick={() => fetchCompletedClips(projectName)}
              className="text-xs text-zinc-400 hover:text-zinc-200 transition-colors"
            >
              Refresh Clips
            </button>
          )}
        </div>

        {outputClips.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12 text-center text-zinc-500 space-y-2 border border-dashed border-zinc-800 rounded-lg">
            <Video className="h-8 w-8 stroke-[1.5]" />
            <p className="text-xs">No generated video clips available yet.</p>
            <p className="text-[11px] text-zinc-600">
              Clips will appear here automatically when generation completes.
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
            {/* 9:16 Video Player Card */}
            <div className="lg:col-span-5 flex flex-col items-center justify-center bg-zinc-950 p-4 rounded-xl border border-zinc-800">
              {selectedClip ? (
                <div className="w-full max-w-[320px] aspect-[9/16] bg-black rounded-lg overflow-hidden shadow-2xl flex items-center justify-center border border-zinc-800/80">
                  <video
                    key={selectedClip.path}
                    src={previewApi.getVideoUrl(selectedClip.path)}
                    controls
                    playsInline
                    className="w-full h-full object-contain"
                  />
                </div>
              ) : (
                <div className="w-full max-w-[320px] aspect-[9/16] bg-zinc-900 rounded-lg flex items-center justify-center text-zinc-600">
                  <span className="text-xs">Select a clip to preview</span>
                </div>
              )}
            </div>

            {/* Clip Details, Actions & Clips Grid */}
            <div className="lg:col-span-7 space-y-5">
              {selectedClip && (
                <div className="bg-zinc-950/80 p-4 rounded-xl border border-zinc-800 space-y-3">
                  <div className="flex items-center justify-between">
                    <div>
                      <span className="inline-block px-2 py-0.5 rounded bg-red-950/80 border border-red-800 text-[10px] font-mono text-red-300 uppercase">
                        Isolated Output Preview
                      </span>
                      <h4 className="text-sm font-semibold text-zinc-100 truncate mt-1">{selectedClip.name}</h4>
                      <p className="text-[11px] font-mono text-zinc-500">{formatBytes(selectedClip.size)}</p>
                    </div>
                  </div>

                  <div className="flex flex-wrap gap-2 pt-1">
                    <a
                      href={previewApi.getVideoUrl(selectedClip.path)}
                      download={selectedClip.name}
                      className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-xs font-medium text-zinc-200 border border-zinc-700 transition-colors"
                    >
                      <Download className="h-3.5 w-3.5" />
                      <span>Download MP4</span>
                    </a>

                    <button
                      type="button"
                      onClick={() => onNavigateTab?.('subtitle-editor', projectName)}
                      className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-xs font-medium text-zinc-200 border border-zinc-700 transition-colors"
                    >
                      <ExternalLink className="h-3.5 w-3.5" />
                      <span>Subtitle Editor</span>
                    </button>

                    <button
                      type="button"
                      onClick={handleExportToGDrive}
                      disabled={isExportingGdrive}
                      className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-red-950/60 hover:bg-red-900/80 text-xs font-medium text-red-200 border border-red-800/80 transition-colors disabled:opacity-50"
                    >
                      {isExportingGdrive ? (
                        <Loader2 className="h-3.5 w-3.5 animate-spin" />
                      ) : (
                        <Share2 className="h-3.5 w-3.5" />
                      )}
                      <span>Export to Google Drive</span>
                    </button>
                  </div>

                  {gdriveExportMsg && (
                    <p
                      className={`text-xs p-2 rounded ${
                        gdriveExportMsg.includes('failed')
                          ? 'text-red-400 bg-red-950/30'
                          : 'text-emerald-400 bg-emerald-950/30'
                      }`}
                    >
                      {gdriveExportMsg}
                    </p>
                  )}
                </div>
              )}

              {/* Clips Thumbnail Grid */}
              <div className="space-y-2">
                <span className="text-xs font-medium uppercase tracking-wider text-zinc-400 block">
                  Generated Clips ({outputClips.length})
                </span>
                <div className="grid grid-cols-2 sm:grid-cols-3 xl:grid-cols-4 gap-2 pt-1">
                  {outputClips.map((clip) => (
                    <button
                      key={clip.path}
                      type="button"
                      onClick={() => setSelectedClip(clip)}
                      className={`p-2.5 rounded-lg border text-left transition-colors truncate flex flex-col justify-between ${
                        selectedClip?.path === clip.path
                          ? 'bg-red-950/40 border-red-600 text-zinc-100'
                          : 'bg-zinc-950/60 border-zinc-800 text-zinc-400 hover:text-zinc-200 hover:border-zinc-700'
                      }`}
                    >
                      <div className="flex items-center space-x-1.5 overflow-hidden w-full">
                        <Video className="h-3 w-3 shrink-0 text-red-400" />
                        <p className="text-xs font-medium truncate">{clip.name}</p>
                      </div>
                      <p className="text-[10px] font-mono text-zinc-500 pl-4.5">{formatBytes(clip.size)}</p>
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default GeneratorTab;
