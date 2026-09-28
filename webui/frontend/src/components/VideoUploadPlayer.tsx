import React, { useState, useRef, useEffect, useCallback } from 'react';
import {
  UploadCloud,
  Film,
  Play,
  FileVideo,
  Image as ImageIcon,
  CheckCircle2,
  AlertCircle,
  Loader2,
  Info,
  Send,
} from 'lucide-react';
import { uploadApi, previewApi } from '../api/client';
import type { VideoMetadata } from '../api/types';

interface VideoUploadPlayerProps {
  onSelectVideoForJob?: (videoPath: string, projectName?: string) => void;
}

export const VideoUploadPlayer: React.FC<VideoUploadPlayerProps> = ({
  onSelectVideoForJob,
}) => {
  // Upload State
  const [isDragOver, setIsDragOver] = useState(false);
  const [projectName, setProjectName] = useState('');
  const [useChunked, setUseChunked] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [uploadStatusText, setUploadStatusText] = useState('');
  const [uploadError, setUploadError] = useState<string | null>(null);

  // Player & Preview State
  const [videoPath, setVideoPath] = useState('');
  const [videoUrl, setVideoUrl] = useState('');
  const [metadata, setMetadata] = useState<VideoMetadata | null>(null);
  const [loadingMetadata, setLoadingMetadata] = useState(false);

  // Thumbnail State
  const [thumbnailTime, setThumbnailTime] = useState(1.0);
  const [generatingThumb, setGeneratingThumb] = useState(false);
  const [thumbnailUrl, setThumbnailUrl] = useState<string | null>(null);
  const [thumbError, setThumbError] = useState<string | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const videoElementRef = useRef<HTMLVideoElement>(null);

  // Load video preview & metadata
  const handleLoadVideo = useCallback(async (path: string) => {
    if (!path.trim()) return;
    setVideoPath(path);
    setVideoUrl(previewApi.getVideoUrl(path));
    setLoadingMetadata(true);
    setThumbnailUrl(null);
    setThumbError(null);

    try {
      const meta = await previewApi.getMetadata(path);
      setMetadata(meta);
    } catch {
      setMetadata(null);
    } finally {
      setLoadingMetadata(false);
    }
  }, []);

  useEffect(() => {
    if (videoPath) {
      handleLoadVideo(videoPath);
    }
  }, [videoPath, handleLoadVideo]);

  // Execute Upload
  const handleFileUpload = async (file: File) => {
    if (!file) return;

    setUploading(true);
    setUploadProgress(0);
    setUploadError(null);
    setUploadStatusText('Preparing upload...');

    try {
      let result;
      if (useChunked || file.size > 20 * 1024 * 1024) {
        setUploadStatusText('Uploading via chunked transfer...');
        result = await uploadApi.uploadFileChunked(
          file,
          projectName.trim() || undefined,
          (percent, chunk, total) => {
            setUploadProgress(percent);
            setUploadStatusText(`Uploading chunk ${chunk} of ${total} (${percent}%)`);
          }
        );
      } else {
        setUploadStatusText('Uploading file...');
        setUploadProgress(50);
        result = await uploadApi.uploadSingle(file, projectName.trim() || undefined);
        setUploadProgress(100);
      }

      setUploadStatusText(`Upload complete: ${result.filename}`);
      setVideoPath(result.filepath);
      if (result.project_name) {
        setProjectName(result.project_name);
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Upload failed';
      setUploadError(msg);
      setUploadStatusText('');
    } finally {
      setUploading(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleFileUpload(e.dataTransfer.files[0]);
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
  };

  // Generate Thumbnail
  const handleGenerateThumbnail = async () => {
    if (!videoPath) return;
    setGeneratingThumb(true);
    setThumbError(null);
    try {
      const res = await previewApi.createThumbnail({
        path: videoPath,
        timestamp: Number(thumbnailTime) || 1.0,
      });
      // The thumbnail is served via preview streaming or can be loaded directly
      setThumbnailUrl(previewApi.getThumbnailUrl(res.thumbnail_path));
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Thumbnail extraction failed';
      setThumbError(msg);
    } finally {
      setGeneratingThumb(false);
    }
  };

  const formatFileSize = (bytes?: number | null) => {
    if (!bytes) return 'Unknown';
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const formatDuration = (seconds?: number) => {
    if (seconds === undefined) return '--:--';
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs < 10 ? '0' : ''}${secs}`;
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
      {/* Upload Dropzone & Staging Panel */}
      <div className="lg:col-span-5 space-y-6">
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5 space-y-5">
          <div className="flex items-center space-x-2 border-b border-zinc-800 pb-3">
            <UploadCloud className="h-5 w-5 text-red-400" />
            <h2 className="text-base font-semibold text-white">Media Upload & Staging</h2>
          </div>

          {/* Project Name & Options */}
          <div className="space-y-3">
            <div>
              <label className="text-xs font-medium text-zinc-400 block mb-1">
                Project Folder Name (Optional)
              </label>
              <input
                type="text"
                placeholder="e.g. podcast_ep12 (saved into VIRALS/)"
                value={projectName}
                onChange={(e) => setProjectName(e.target.value)}
                disabled={uploading}
                className="w-full rounded-lg bg-zinc-950 border border-zinc-800 px-3 py-2 text-sm text-zinc-100 placeholder-zinc-500 focus:border-red-500 focus:outline-none"
              />
            </div>

            <div className="flex items-center justify-between text-xs text-zinc-400">
              <label htmlFor="chunked-upload" className="cursor-pointer">
                Chunked Upload (Recommended for large videos)
              </label>
              <input
                type="checkbox"
                id="chunked-upload"
                checked={useChunked}
                onChange={(e) => setUseChunked(e.target.checked)}
                disabled={uploading}
                className="h-4 w-4 rounded border-zinc-700 bg-zinc-950 text-red-600 focus:ring-0"
              />
            </div>
          </div>

          {/* Drag & Drop Zone */}
          <div
            onDrop={handleDrop}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onClick={() => !uploading && fileInputRef.current?.click()}
            className={`border-2 border-dashed rounded-xl p-8 flex flex-col items-center justify-center text-center cursor-pointer transition-colors ${
              isDragOver
                ? 'border-red-500 bg-red-950/20'
                : 'border-zinc-800 hover:border-zinc-700 bg-zinc-950/40 hover:bg-zinc-950/80'
            } ${uploading ? 'pointer-events-none opacity-60' : ''}`}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept="video/*"
              className="hidden"
              onChange={(e) => {
                if (e.target.files && e.target.files.length > 0) {
                  handleFileUpload(e.target.files[0]);
                }
              }}
            />
            <div className="h-12 w-12 rounded-full bg-zinc-900 border border-zinc-800 flex items-center justify-center mb-3 text-red-400">
              {uploading ? (
                <Loader2 className="h-6 w-6 animate-spin text-red-400" />
              ) : (
                <FileVideo className="h-6 w-6" />
              )}
            </div>
            <p className="text-sm font-medium text-zinc-200">
              Drag and drop video here, or <span className="text-red-400">browse</span>
            </p>
            <p className="text-xs text-zinc-500 mt-1">MP4, MOV, MKV, AVI, WEBM supported</p>
          </div>

          {/* Upload Progress & Messages */}
          {uploading && (
            <div className="space-y-2">
              <div className="w-full bg-zinc-800 rounded-full h-2 overflow-hidden">
                <div
                  className="bg-red-600 h-2 transition-all duration-200"
                  style={{ width: `${uploadProgress}%` }}
                />
              </div>
              <p className="text-xs text-zinc-400 text-center font-mono">{uploadStatusText}</p>
            </div>
          )}

          {uploadError && (
            <div className="flex items-start space-x-2 rounded-lg bg-red-950/50 border border-red-800/80 p-3 text-sm text-red-300">
              <AlertCircle className="h-4 w-4 mt-0.5 shrink-0 text-red-400" />
              <span>{uploadError}</span>
            </div>
          )}

          {/* Quick Path Input */}
          <div className="pt-3 border-t border-zinc-800 space-y-2">
            <label className="text-xs font-medium text-zinc-400 block">
              Or load existing video from server path:
            </label>
            <div className="flex space-x-2">
              <input
                type="text"
                placeholder="/home/user/video.mp4"
                value={videoPath}
                onChange={(e) => setVideoPath(e.target.value)}
                className="flex-1 rounded-lg bg-zinc-950 border border-zinc-800 px-3 py-1.5 text-xs text-zinc-100 placeholder-zinc-500 focus:border-red-500 focus:outline-none"
              />
              <button
                type="button"
                onClick={() => handleLoadVideo(videoPath)}
                className="px-3 py-1.5 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-xs font-medium text-zinc-200 transition-colors"
              >
                Load
              </button>
            </div>
          </div>

          {/* Send to Job Console Action */}
          {videoPath && onSelectVideoForJob && (
            <button
              type="button"
              onClick={() => onSelectVideoForJob(videoPath, projectName)}
              className="w-full flex items-center justify-center space-x-2 rounded-lg bg-zinc-800 hover:bg-zinc-700 border border-zinc-700 py-2 px-3 text-xs font-semibold text-zinc-200 transition-colors"
            >
              <Send className="h-3.5 w-3.5 text-red-400" />
              <span>Send This Video to Job Processing Console</span>
            </button>
          )}
        </div>
      </div>

      {/* Video Player & Metadata Panel */}
      <div className="lg:col-span-7 space-y-6">
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl overflow-hidden">
          <div className="flex items-center justify-between px-5 py-3 border-b border-zinc-800">
            <div className="flex items-center space-x-2">
              <Play className="h-4 w-4 text-red-400" />
              <h2 className="text-base font-semibold text-white">Video Preview Player</h2>
            </div>
            {videoPath && (
              <span className="text-xs font-mono text-zinc-400 truncate max-w-[260px]">
                {videoPath.split('/').pop()}
              </span>
            )}
          </div>

          {/* HTML5 Video with HTTP 206 Partial Content Range Support */}
          <div className="relative aspect-video bg-black flex items-center justify-center">
            {videoUrl ? (
              <video
                ref={videoElementRef}
                controls
                preload="metadata"
                className="w-full h-full object-contain"
                src={videoUrl}
              >
                Your browser does not support the video tag.
              </video>
            ) : (
              <div className="flex flex-col items-center justify-center text-zinc-600 space-y-2">
                <Film className="h-10 w-10 text-zinc-700" />
                <p className="text-xs">No video loaded. Upload or select a video on the left.</p>
              </div>
            )}
          </div>

          {/* Metadata Display Card */}
          <div className="p-5 border-t border-zinc-800 bg-zinc-950/60">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center space-x-1.5 text-xs font-medium uppercase tracking-wider text-zinc-400">
                <Info className="h-4 w-4 text-red-400" />
                <span>Media Stream Diagnostics</span>
              </div>
              {loadingMetadata && <Loader2 className="h-3.5 w-3.5 animate-spin text-zinc-500" />}
            </div>

            {metadata ? (
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
                <div className="bg-zinc-900/80 border border-zinc-800 rounded-lg p-2.5">
                  <span className="text-zinc-500 block">Resolution</span>
                  <span className="font-mono text-zinc-200 font-medium">
                    {metadata.width} × {metadata.height}
                  </span>
                </div>
                <div className="bg-zinc-900/80 border border-zinc-800 rounded-lg p-2.5">
                  <span className="text-zinc-500 block">Duration</span>
                  <span className="font-mono text-zinc-200 font-medium">
                    {formatDuration(metadata.duration)} ({metadata.duration.toFixed(1)}s)
                  </span>
                </div>
                <div className="bg-zinc-900/80 border border-zinc-800 rounded-lg p-2.5">
                  <span className="text-zinc-500 block">Framerate</span>
                  <span className="font-mono text-zinc-200 font-medium">{metadata.fps} fps</span>
                </div>
                <div className="bg-zinc-900/80 border border-zinc-800 rounded-lg p-2.5">
                  <span className="text-zinc-500 block">Codec / Bitrate</span>
                  <span className="font-mono text-zinc-200 font-medium">
                    {metadata.codec || 'N/A'}{metadata.bitrate ? ` (${formatFileSize(metadata.bitrate / 8)}/s)` : ''}
                  </span>
                </div>
              </div>
            ) : (
              <p className="text-xs text-zinc-500">
                {videoPath ? 'Metadata extraction pending...' : 'Load a video to view stream metadata.'}
              </p>
            )}

            {/* Thumbnail Generator */}
            {videoPath && (
              <div className="mt-4 pt-4 border-t border-zinc-800/80 flex flex-wrap items-center justify-between gap-3">
                <div className="flex items-center space-x-2">
                  <label className="text-xs text-zinc-400">Thumbnail at second:</label>
                  <input
                    type="number"
                    min="0"
                    step="0.5"
                    value={thumbnailTime}
                    onChange={(e) => setThumbnailTime(parseFloat(e.target.value) || 0)}
                    className="w-16 rounded bg-zinc-900 border border-zinc-800 px-2 py-1 text-xs text-zinc-100"
                  />
                  <button
                    type="button"
                    onClick={handleGenerateThumbnail}
                    disabled={generatingThumb}
                    className="flex items-center space-x-1.5 px-3 py-1 rounded bg-zinc-800 hover:bg-zinc-700 text-xs font-medium text-zinc-200 transition-colors"
                  >
                    {generatingThumb ? (
                      <Loader2 className="h-3 w-3 animate-spin" />
                    ) : (
                      <ImageIcon className="h-3 w-3 text-red-400" />
                    )}
                    <span>Generate Thumbnail</span>
                  </button>
                </div>

                {thumbnailUrl && (
                  <div className="flex items-center space-x-2 text-xs text-emerald-400">
                    <CheckCircle2 className="h-3.5 w-3.5" />
                    <span>Thumbnail generated</span>
                  </div>
                )}
              </div>
            )}

            {thumbError && <p className="text-xs text-red-400 mt-2">{thumbError}</p>}
          </div>
        </div>
      </div>
    </div>
  );
};
