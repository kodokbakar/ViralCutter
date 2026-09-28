import React, { useState, useEffect, useCallback } from 'react';
import {
  Activity,
  HardDrive,
  Cpu,
  Video,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  RefreshCw,
  Check,
  Terminal,
  Square,
  Loader2,
  Clock,
} from 'lucide-react';
import { systemApi, jobsApi } from '../api/client';
import type { SystemStatusResponse, ActiveJobResponse } from '../api/types';

export interface DiagnosticsTabProps {
  onRefresh?: () => void;
}

export const DiagnosticsTab: React.FC<DiagnosticsTabProps> = ({ onRefresh }) => {
  const [status, setStatus] = useState<SystemStatusResponse | null>(null);
  const [activeJobData, setActiveJobData] = useState<ActiveJobResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [cancellingJobId, setCancellingJobId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const fetchDiagnostics = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [sysStatus, activeJob] = await Promise.all([
        systemApi.getStatus(),
        jobsApi.getActive().catch(() => null),
      ]);
      setStatus(sysStatus);
      setActiveJobData(activeJob);
      onRefresh?.();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to retrieve diagnostics';
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, [onRefresh]);

  useEffect(() => {
    fetchDiagnostics();
  }, [fetchDiagnostics]);

  const handleCancelJob = async (jobId: string) => {
    setCancellingJobId(jobId);
    try {
      await jobsApi.cancel(jobId);
      await fetchDiagnostics();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Cancel failed';
      setError(msg);
    } finally {
      setCancellingJobId(null);
    }
  };

  const diskUsed = status?.disk?.used_gb ?? 0;
  const diskTotal = status?.disk?.total_gb ?? 0;
  const diskFree = status?.disk?.free_gb ?? 0;
  const diskPercent = diskTotal > 0 ? Math.round((diskUsed / diskTotal) * 100) : 0;
  const isDiskLow = diskFree < 5.0 && diskTotal > 0;

  const ffmpegReady = Boolean(status?.ffmpeg?.ffmpeg_available && status?.ffmpeg?.ffprobe_available);
  const gpuAvailable = Boolean(status?.gpu?.available);

  const activeJob = activeJobData?.active && activeJobData.job ? activeJobData.job : null;

  return (
    <div className="space-y-6">
      {/* Header with Refresh */}
      <div className="flex items-center justify-between bg-zinc-900 border border-zinc-800 rounded-xl p-4">
        <div className="flex items-center space-x-2.5">
          <Activity className="h-5 w-5 text-red-400" />
          <div>
            <h2 className="text-base font-semibold text-white">System Diagnostics & Active Jobs</h2>
            <p className="text-xs text-zinc-400">
              Hardware acceleration, Whisper dependencies, storage metrics, and job monitor
            </p>
          </div>
        </div>

        <button
          onClick={fetchDiagnostics}
          disabled={loading}
          className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-xs font-medium text-zinc-200 transition-colors"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} />
          <span>Refresh All</span>
        </button>
      </div>

      {error && (
        <div className="flex items-center space-x-2 text-xs text-red-400 bg-red-950/40 border border-red-800/60 p-3 rounded-lg">
          <AlertTriangle className="h-4 w-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* 1. Hardware Metrics Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {/* GPU / CUDA Card */}
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5 space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <Cpu className="h-5 w-5 text-red-400" />
              <h3 className="text-sm font-semibold text-white">GPU & VRAM</h3>
            </div>
            {gpuAvailable ? (
              <span className="flex items-center space-x-1 px-2 py-0.5 rounded-full text-xs font-medium bg-emerald-950/80 text-emerald-300 border border-emerald-800">
                <CheckCircle2 className="h-3 w-3" />
                <span>CUDA Ready</span>
              </span>
            ) : (
              <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-zinc-800 text-zinc-400 border border-zinc-700">
                CPU Only
              </span>
            )}
          </div>

          <div className="space-y-1.5 text-xs">
            <div className="flex justify-between py-1 border-b border-zinc-800/60">
              <span className="text-zinc-400">Device</span>
              <span className="font-mono text-zinc-200 truncate max-w-[170px]">
                {status?.gpu?.name || (gpuAvailable ? 'CUDA Device' : 'None detected')}
              </span>
            </div>
            <div className="flex justify-between py-1 border-b border-zinc-800/60">
              <span className="text-zinc-400">Device Count</span>
              <span className="font-mono text-zinc-200">{status?.gpu?.device_count ?? 0}</span>
            </div>
            <div className="flex justify-between py-1 border-b border-zinc-800/60">
              <span className="text-zinc-400">CUDA Version</span>
              <span className="font-mono text-zinc-200">{status?.gpu?.cuda_version || 'N/A'}</span>
            </div>
            <div className="flex justify-between py-1">
              <span className="text-zinc-400">VRAM Free</span>
              <span className="font-mono text-zinc-200">
                {status?.gpu?.vram_free_mb ? `${status.gpu.vram_free_mb} MB` : 'N/A'}
              </span>
            </div>
          </div>
        </div>

        {/* Disk Storage Card */}
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5 space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <HardDrive className="h-5 w-5 text-red-400" />
              <h3 className="text-sm font-semibold text-white">Disk Storage</h3>
            </div>
            {isDiskLow ? (
              <span className="flex items-center space-x-1 px-2 py-0.5 rounded-full text-xs font-medium bg-red-950/80 text-red-300 border border-red-800">
                <AlertTriangle className="h-3 w-3" />
                <span>Low Space</span>
              </span>
            ) : (
              <span className="text-xs text-zinc-400 font-mono">
                {diskFree.toFixed(1)} GB Free
              </span>
            )}
          </div>

          <div className="space-y-2">
            <div className="flex justify-between text-xs text-zinc-400 font-mono">
              <span>{diskUsed.toFixed(1)} GB Used</span>
              <span>{diskTotal.toFixed(1)} GB Total</span>
            </div>
            <div className="w-full bg-zinc-800 rounded-full h-2.5 overflow-hidden">
              <div
                className={`h-2.5 rounded-full transition-all ${
                  isDiskLow ? 'bg-red-500' : 'bg-red-600'
                }`}
                style={{ width: `${diskPercent}%` }}
              />
            </div>
            <p className="text-[11px] text-zinc-500 pt-1">
              Output storage: VIRALS/ projects root
            </p>
          </div>
        </div>

        {/* FFmpeg & Whisper Dependency Health Check */}
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5 space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <Video className="h-5 w-5 text-red-400" />
              <h3 className="text-sm font-semibold text-white">FFmpeg & Whisper</h3>
            </div>
            {ffmpegReady ? (
              <span className="flex items-center space-x-1 px-2 py-0.5 rounded-full text-xs font-medium bg-emerald-950/80 text-emerald-300 border border-emerald-800">
                <CheckCircle2 className="h-3 w-3" />
                <span>Healthy</span>
              </span>
            ) : (
              <span className="flex items-center space-x-1 px-2 py-0.5 rounded-full text-xs font-medium bg-red-950/80 text-red-300 border border-red-800">
                <XCircle className="h-3 w-3" />
                <span>Missing Deps</span>
              </span>
            )}
          </div>

          <div className="space-y-1.5 text-xs">
            <div className="flex justify-between items-center py-1 border-b border-zinc-800/60">
              <span className="text-zinc-400">FFmpeg Binary</span>
              <span className="flex items-center space-x-1">
                {status?.ffmpeg?.ffmpeg_available ? (
                  <Check className="h-3.5 w-3.5 text-emerald-400" />
                ) : (
                  <XCircle className="h-3.5 w-3.5 text-red-400" />
                )}
                <span className="font-mono text-zinc-300">
                  {status?.ffmpeg?.ffmpeg_available ? 'Available' : 'Missing'}
                </span>
              </span>
            </div>

            <div className="flex justify-between items-center py-1 border-b border-zinc-800/60">
              <span className="text-zinc-400">FFprobe Binary</span>
              <span className="flex items-center space-x-1">
                {status?.ffmpeg?.ffprobe_available ? (
                  <Check className="h-3.5 w-3.5 text-emerald-400" />
                ) : (
                  <XCircle className="h-3.5 w-3.5 text-red-400" />
                )}
                <span className="font-mono text-zinc-300">
                  {status?.ffmpeg?.ffprobe_available ? 'Available' : 'Missing'}
                </span>
              </span>
            </div>

            <div className="flex justify-between items-center py-1">
              <span className="text-zinc-400">Whisper Backend</span>
              <span className="font-mono text-emerald-400">faster-whisper</span>
            </div>
          </div>
        </div>
      </div>

      {/* 2. Active Jobs Table */}
      <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5 space-y-4">
        <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
          <div className="flex items-center space-x-2">
            <Terminal className="h-5 w-5 text-red-400" />
            <h3 className="text-sm font-semibold text-white">Active Jobs Monitor</h3>
          </div>
          <span className="text-xs text-zinc-400 font-mono">
            {activeJob ? '1 Running Job' : 'No Running Jobs'}
          </span>
        </div>

        {activeJob ? (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs text-zinc-300">
              <thead className="bg-zinc-950/60 uppercase font-mono text-[11px] text-zinc-400 border-b border-zinc-800">
                <tr>
                  <th className="px-4 py-3">Job ID</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3">Stage</th>
                  <th className="px-4 py-3">Progress</th>
                  <th className="px-4 py-3">Elapsed</th>
                  <th className="px-4 py-3">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-800">
                <tr className="hover:bg-zinc-800/40">
                  <td className="px-4 py-3 font-mono text-red-300 font-medium">
                    {activeJob.job_id}
                  </td>
                  <td className="px-4 py-3">
                    <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-red-950/80 text-red-300 border border-red-800 uppercase">
                      <span className="h-1.5 w-1.5 rounded-full bg-red-400 animate-ping"></span>
                      <span>{activeJob.status}</span>
                    </span>
                  </td>
                  <td className="px-4 py-3 font-mono text-zinc-300">
                    {activeJob.stage || 'PROCESSING'}
                  </td>
                  <td className="px-4 py-3">
                    <div className="w-32 bg-zinc-800 rounded-full h-1.5 overflow-hidden">
                      <div
                        className="bg-red-500 h-1.5 rounded-full transition-all duration-300"
                        style={{ width: `${Math.min(100, Math.max(0, activeJob.percent ?? 0))}%` }}
                      />
                    </div>
                    <span className="text-[10px] text-zinc-400 font-mono mt-0.5 block">
                      {activeJob.percent ?? 0}%
                    </span>
                  </td>
                  <td className="px-4 py-3 font-mono text-zinc-400">
                    {activeJob.elapsed || 'N/A'}
                  </td>
                  <td className="px-4 py-3">
                    <button
                      onClick={() => handleCancelJob(activeJob.job_id)}
                      disabled={cancellingJobId === activeJob.job_id}
                      className="flex items-center space-x-1 px-2.5 py-1 rounded bg-red-950 hover:bg-red-900 text-red-300 border border-red-800 transition-colors disabled:opacity-50"
                    >
                      {cancellingJobId === activeJob.job_id ? (
                        <Loader2 className="h-3.5 w-3.5 animate-spin" />
                      ) : (
                        <Square className="h-3.5 w-3.5" />
                      )}
                      <span>Cancel</span>
                    </button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        ) : (
          <div className="text-center py-8 text-xs text-zinc-500 space-y-1">
            <Clock className="h-8 w-8 mx-auto text-zinc-600 stroke-[1.5]" />
            <p>No jobs currently active or queued.</p>
            <p className="text-[11px] text-zinc-600">Jobs launched from Generator or Subtitles will appear here.</p>
          </div>
        )}
      </div>
    </div>
  );
};

export default DiagnosticsTab;
