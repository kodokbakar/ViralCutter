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
  Cloud,
  Check,
  Terminal,
} from 'lucide-react';
import { systemApi, gdriveApi } from '../api/client';
import type { SystemStatusResponse, GDriveStatusResponse } from '../api/types';

export const SystemStatusPanel: React.FC = () => {
  const [status, setStatus] = useState<SystemStatusResponse | null>(null);
  const [gdriveStatus, setGdriveStatus] = useState<GDriveStatusResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchSystemData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [sys, gd] = await Promise.all([
        systemApi.getStatus(),
        gdriveApi.getStatus().catch(() => null),
      ]);
      setStatus(sys);
      setGdriveStatus(gd);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to retrieve system diagnostics';
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchSystemData();
  }, [fetchSystemData]);

  const diskUsed = status?.disk?.used_gb ?? 0;
  const diskTotal = status?.disk?.total_gb ?? 0;
  const diskFree = status?.disk?.free_gb ?? 0;
  const diskPercent = diskTotal > 0 ? Math.round((diskUsed / diskTotal) * 100) : 0;
  const isDiskLow = diskFree < 5.0 && diskTotal > 0;

  const ffmpegReady = Boolean(status?.ffmpeg?.ffmpeg_available && status?.ffmpeg?.ffprobe_available);
  const gpuAvailable = Boolean(status?.gpu?.available);

  return (
    <div className="space-y-6">
      {/* Header with Refresh */}
      <div className="flex items-center justify-between bg-zinc-900 border border-zinc-800 rounded-xl p-4">
        <div className="flex items-center space-x-2.5">
          <Activity className="h-5 w-5 text-red-400" />
          <div>
            <h2 className="text-base font-semibold text-white">System Diagnostics & Readiness</h2>
            <p className="text-xs text-zinc-400">Hardware acceleration, disk storage, and dependencies</p>
          </div>
        </div>

        <button
          onClick={fetchSystemData}
          disabled={loading}
          className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-xs font-medium text-zinc-200 transition-colors"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} />
          <span>Refresh</span>
        </button>
      </div>

      {error && (
        <div className="flex items-center space-x-2 text-xs text-red-400 bg-red-950/30 border border-red-800/40 p-3 rounded-lg">
          <AlertTriangle className="h-4 w-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Grid of Diagnostics Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {/* GPU / CUDA Card */}
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5 space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <Cpu className="h-5 w-5 text-red-400" />
              <h3 className="text-sm font-semibold text-white">GPU & CUDA</h3>
            </div>
            {gpuAvailable ? (
              <span className="flex items-center space-x-1 px-2 py-0.5 rounded-full text-xs font-medium bg-emerald-950/80 text-emerald-300 border border-emerald-800">
                <CheckCircle2 className="h-3 w-3" />
                <span>CUDA Ready</span>
              </span>
            ) : (
              <span className="flex items-center space-x-1 px-2 py-0.5 rounded-full text-xs font-medium bg-zinc-800 text-zinc-400 border border-zinc-700">
                CPU Only
              </span>
            )}
          </div>

          <div className="space-y-1.5 text-xs">
            <div className="flex justify-between py-1 border-b border-zinc-800/60">
              <span className="text-zinc-400">Device</span>
              <span className="font-mono text-zinc-200 truncate max-w-[180px]">
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
            {status?.gpu?.vram_total_mb && (
              <div className="flex justify-between py-1">
                <span className="text-zinc-400">VRAM</span>
                <span className="font-mono text-zinc-200">
                  {status.gpu.vram_free_mb ?? 0} MB / {status.gpu.vram_total_mb} MB Free
                </span>
              </div>
            )}
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
            <p className="text-xs text-zinc-500 pt-1">
              Storage root: VIRALS/ outputs directory
            </p>
          </div>
        </div>

        {/* FFmpeg Readiness Card */}
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5 space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <Video className="h-5 w-5 text-red-400" />
              <h3 className="text-sm font-semibold text-white">FFmpeg & Media Engine</h3>
            </div>
            {ffmpegReady ? (
              <span className="flex items-center space-x-1 px-2 py-0.5 rounded-full text-xs font-medium bg-emerald-950/80 text-emerald-300 border border-emerald-800">
                <CheckCircle2 className="h-3 w-3" />
                <span>Ready</span>
              </span>
            ) : (
              <span className="flex items-center space-x-1 px-2 py-0.5 rounded-full text-xs font-medium bg-red-950/80 text-red-300 border border-red-800">
                <XCircle className="h-3 w-3" />
                <span>Missing</span>
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
                  {status?.ffmpeg?.ffmpeg_available ? 'Installed' : 'Not found'}
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
                  {status?.ffmpeg?.ffprobe_available ? 'Installed' : 'Not found'}
                </span>
              </span>
            </div>

            <div className="flex justify-between py-1">
              <span className="text-zinc-400">Version</span>
              <span className="font-mono text-zinc-300 truncate max-w-[170px]">
                {status?.ffmpeg?.version || 'N/A'}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Secondary Cards: Google Drive & Python Tools Availability */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Google Drive Status */}
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5 space-y-3">
          <div className="flex items-center space-x-2 border-b border-zinc-800 pb-3">
            <Cloud className="h-5 w-5 text-red-400" />
            <h3 className="text-sm font-semibold text-white">Google Drive Integration</h3>
          </div>

          <div className="space-y-2 text-xs">
            <div className="flex justify-between py-1 border-b border-zinc-800/60">
              <span className="text-zinc-400">Status</span>
              <span className="font-semibold text-zinc-200 capitalize">
                {gdriveStatus?.available ? (
                  <span className="text-emerald-400">Available</span>
                ) : (
                  <span className="text-zinc-500">Unconfigured</span>
                )}
              </span>
            </div>

            <div className="flex justify-between py-1 border-b border-zinc-800/60">
              <span className="text-zinc-400">Mode</span>
              <span className="font-mono text-zinc-200">
                {gdriveStatus?.mode || 'unconfigured'}
              </span>
            </div>

            {gdriveStatus?.message && (
              <p className="text-xs text-zinc-400 pt-1 leading-relaxed">
                {gdriveStatus.message}
              </p>
            )}
          </div>
        </div>

        {/* AI & Python Tool Packages */}
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5 space-y-3">
          <div className="flex items-center space-x-2 border-b border-zinc-800 pb-3">
            <Terminal className="h-5 w-5 text-red-400" />
            <h3 className="text-sm font-semibold text-white">Python Runtime & Tools</h3>
          </div>

          <div className="space-y-2 text-xs">
            <div className="flex justify-between py-1 border-b border-zinc-800/60">
              <span className="text-zinc-400">Python Version</span>
              <span className="font-mono text-zinc-200">
                {status?.python?.version || 'Python 3.x'}
              </span>
            </div>

            {/* Tools Grid */}
            <div className="pt-1">
              <span className="text-zinc-400 block mb-2">Installed Model Libraries:</span>
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                {status?.tools &&
                  Object.entries(status.tools).map(([toolName, installed]) => (
                    <div
                      key={toolName}
                      className="flex items-center space-x-1.5 bg-zinc-950 px-2 py-1 rounded border border-zinc-800 font-mono"
                    >
                      {installed ? (
                        <Check className="h-3 w-3 text-emerald-400 shrink-0" />
                      ) : (
                        <XCircle className="h-3 w-3 text-zinc-600 shrink-0" />
                      )}
                      <span className={installed ? 'text-zinc-200' : 'text-zinc-500'}>
                        {toolName}
                      </span>
                    </div>
                  ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
