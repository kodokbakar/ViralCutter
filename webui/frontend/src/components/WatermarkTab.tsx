import React, { useState, useRef, useEffect } from 'react';
import {
  Image as ImageIcon,
  Type,
  Upload,
  Eye,
  Play,
  CheckCircle2,
  AlertCircle,
  Loader2,
} from 'lucide-react';
import { uploadApi, jobsApi } from '../api/client';
import type { JobRunRequest } from '../api/types';

export interface WatermarkTabProps {
  defaultVideoPath?: string;
  defaultProjectName?: string;
}

export type WatermarkPosition =
  | 'top_left'
  | 'top_center'
  | 'top_right'
  | 'center'
  | 'bottom_left'
  | 'bottom_center'
  | 'bottom_right';

export const WatermarkTab: React.FC<WatermarkTabProps> = ({
  defaultVideoPath = '',
  defaultProjectName = '',
}) => {
  // Mode: Image or Text
  const [mode, setMode] = useState<'image' | 'text'>('image');

  // Video & Project selection
  const [videoPath, setVideoPath] = useState<string>(defaultVideoPath);
  const [projectName, setProjectName] = useState<string>(defaultProjectName);

  // Watermark Image Upload State
  const [imageFile, setImageFile] = useState<File | null>(null);
  const [imagePreviewUrl, setImagePreviewUrl] = useState<string | null>(null);
  const [serverImagePath, setServerImagePath] = useState<string>('');
  const [isUploading, setIsUploading] = useState<boolean>(false);
  const [uploadSuccess, setUploadSuccess] = useState<string | null>(null);

  // Watermark Text State
  const [watermarkText, setWatermarkText] = useState<string>('@ViralCutter');
  const [textColor, setTextColor] = useState<string>('#FFFFFF');
  const [fontSize, setFontSize] = useState<number>(36);

  // Positioning Controls
  const [position, setPosition] = useState<WatermarkPosition>('top_right');

  // Sliders: Opacity & Scale & Margins
  const [opacity, setOpacity] = useState<number>(0.85);
  const [scale, setScale] = useState<number>(15); // percentage (5% - 50%)
  const [hMargin, setHMargin] = useState<number>(20); // px in preview
  const [vMargin, setVMargin] = useState<number>(20);

  // Submission State
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [actionMessage, setActionMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (defaultVideoPath) setVideoPath(defaultVideoPath);
    if (defaultProjectName) setProjectName(defaultProjectName);
  }, [defaultVideoPath, defaultProjectName]);

  // Handle Image Selection and Upload
  const handleImageSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setImageFile(file);
    const localUrl = URL.createObjectURL(file);
    setImagePreviewUrl(localUrl);

    setIsUploading(true);
    setActionMessage(null);
    setUploadSuccess(null);

    try {
      const res = await uploadApi.uploadSingle(file, projectName.trim() || undefined);
      setServerImagePath(res.filepath);
      setUploadSuccess(`Uploaded: ${res.filename}`);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Watermark upload failed';
      setActionMessage({ type: 'error', text: msg });
    } finally {
      setIsUploading(false);
    }
  };

  // Run Job with Watermark
  const handleApplyWatermark = async (e: React.FormEvent) => {
    e.preventDefault();
    setActionMessage(null);

    if (mode === 'image' && !serverImagePath && !imageFile) {
      setActionMessage({ type: 'error', text: 'Please upload a watermark image first' });
      return;
    }
    if (mode === 'text' && !watermarkText.trim()) {
      setActionMessage({ type: 'error', text: 'Please enter watermark text' });
      return;
    }

    setIsSubmitting(true);

    const payload: JobRunRequest = {
      video_path: videoPath.trim() || undefined,
      project_name: projectName.trim() || undefined,
      watermark_mode: mode,
      watermark_image: mode === 'image' ? (serverImagePath || imageFile?.name) : undefined,
      watermark_text: mode === 'text' ? watermarkText.trim() : undefined,
      watermark_text_color: textColor,
      watermark_font_size: fontSize,
      watermark_position: position,
      watermark_scale: scale,
      watermark_opacity: opacity,
      watermark_h_margin: hMargin * 2,
      watermark_v_margin: vMargin * 2,
    };

    try {
      const res = await jobsApi.run(payload);
      setActionMessage({
        type: 'success',
        text: `Job launched with watermark settings! Job ID: ${res.job_id}`,
      });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to launch job';
      setActionMessage({ type: 'error', text: msg });
    } finally {
      setIsSubmitting(false);
    }
  };

  // Helper to compute CSS position styles inside preview box
  const getWatermarkOverlayStyle = (): React.CSSProperties => {
    const base: React.CSSProperties = {
      position: 'absolute',
      opacity,
      maxWidth: `${scale * 1.8}%`,
      transition: 'all 0.15s ease-out',
      pointerEvents: 'none',
      userSelect: 'none',
    };

    switch (position) {
      case 'top_left':
        return { ...base, top: `${vMargin}px`, left: `${hMargin}px` };
      case 'top_center':
        return {
          ...base,
          top: `${vMargin}px`,
          left: '50%',
          transform: 'translateX(-50%)',
        };
      case 'top_right':
        return { ...base, top: `${vMargin}px`, right: `${hMargin}px` };
      case 'center':
        return {
          ...base,
          top: '50%',
          left: '50%',
          transform: 'translate(-50%, -50%)',
        };
      case 'bottom_left':
        return { ...base, bottom: `${vMargin}px`, left: `${hMargin}px` };
      case 'bottom_center':
        return {
          ...base,
          bottom: `${vMargin}px`,
          left: '50%',
          transform: 'translateX(-50%)',
        };
      case 'bottom_right':
        return { ...base, bottom: `${vMargin}px`, right: `${hMargin}px` };
      default:
        return base;
    }
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
      {/* Controls Form */}
      <div className="lg:col-span-7 space-y-6">
        <form onSubmit={handleApplyWatermark} className="bg-zinc-900 border border-zinc-800 rounded-xl p-5 space-y-5">
          <div className="flex items-center space-x-2 border-b border-zinc-800 pb-3">
            <ImageIcon className="h-5 w-5 text-red-400" />
            <div>
              <h2 className="text-base font-semibold text-white">Watermark Configuration</h2>
              <p className="text-xs text-zinc-400">Positioning, opacity, scale, and overlay controls</p>
            </div>
          </div>

          {actionMessage && (
            <div
              className={`flex items-center space-x-2 text-xs p-3 rounded-lg border ${
                actionMessage.type === 'success'
                  ? 'bg-emerald-950/40 border-emerald-800/60 text-emerald-300'
                  : 'bg-red-950/40 border-red-800/60 text-red-400'
              }`}
            >
              {actionMessage.type === 'success' ? (
                <CheckCircle2 className="h-4 w-4 shrink-0" />
              ) : (
                <AlertCircle className="h-4 w-4 shrink-0" />
              )}
              <span>{actionMessage.text}</span>
            </div>
          )}

          {/* Mode Switcher */}
          <div className="flex space-x-2 border-b border-zinc-800 pb-3">
            <button
              type="button"
              onClick={() => setMode('image')}
              className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                mode === 'image'
                  ? 'bg-red-600 text-white shadow-sm'
                  : 'bg-zinc-800 text-zinc-400 hover:text-zinc-200'
              }`}
            >
              <ImageIcon className="h-3.5 w-3.5" />
              <span>Image Watermark</span>
            </button>

            <button
              type="button"
              onClick={() => setMode('text')}
              className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                mode === 'text'
                  ? 'bg-red-600 text-white shadow-sm'
                  : 'bg-zinc-800 text-zinc-400 hover:text-zinc-200'
              }`}
            >
              <Type className="h-3.5 w-3.5" />
              <span>Text Watermark</span>
            </button>
          </div>

          {/* 1. Upload or Text Input */}
          {mode === 'image' ? (
            <div className="space-y-2">
              <label htmlFor="watermark-file-input" className="block text-xs font-medium text-zinc-300">Watermark Image File</label>
              <input
                id="watermark-file-input"
                type="file"
                ref={fileInputRef}
                onChange={handleImageSelect}
                accept="image/png,image/jpeg,image/svg+xml,image/webp"
                className="hidden"
              />
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                disabled={isUploading}
                className="w-full border-2 border-dashed border-zinc-700 hover:border-red-500 rounded-lg p-4 text-center text-xs text-zinc-400 hover:text-zinc-200 transition-colors flex flex-col items-center justify-center space-y-2"
              >
                {isUploading ? (
                  <Loader2 className="h-6 w-6 animate-spin text-red-400" />
                ) : (
                  <Upload className="h-6 w-6 text-zinc-500" />
                )}
                <span>
                  {imageFile
                    ? `Selected: ${imageFile.name}`
                    : 'Click to upload watermark logo (PNG, SVG, WEBP, JPG)'}
                </span>
              </button>
              {uploadSuccess && <p className="text-xs text-emerald-400 font-mono">{uploadSuccess}</p>}
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-4 gap-3">
              <div className="sm:col-span-2 space-y-1.5">
                <label htmlFor="watermark-text-input" className="block text-xs font-medium text-zinc-300">Watermark Text</label>
                <input
                  id="watermark-text-input"
                  type="text"
                  value={watermarkText}
                  onChange={(e) => setWatermarkText(e.target.value)}
                  placeholder="@ChannelName"
                  className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-100 focus:outline-none focus:border-red-500"
                />
              </div>
              <div className="space-y-1.5">
                <label htmlFor="watermark-font-size" className="block text-xs font-medium text-zinc-300">Font Size</label>
                <input
                  id="watermark-font-size"
                  type="number"
                  min={12}
                  max={72}
                  value={fontSize}
                  onChange={(e) => setFontSize(Number(e.target.value))}
                  className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-100 focus:outline-none focus:border-red-500"
                />
              </div>
              <div className="space-y-1.5">
                <label htmlFor="watermark-text-color" className="block text-xs font-medium text-zinc-300">Color</label>
                <input
                  id="watermark-text-color"
                  type="color"
                  value={textColor}
                  onChange={(e) => setTextColor(e.target.value)}
                  className="w-full h-9 bg-zinc-800 border border-zinc-700 rounded-lg cursor-pointer px-1 py-1"
                />
              </div>
            </div>
          )}

          {/* 2. Positioning Controls (3x3 Grid) */}
          <div className="space-y-2">
            <span className="block text-xs font-medium text-zinc-300">Position</span>
            <div className="grid grid-cols-3 gap-2 max-w-xs">
              {[
                { id: 'top_left', label: 'Top-Left' },
                { id: 'top_center', label: 'Top-Center' },
                { id: 'top_right', label: 'Top-Right' },
                { id: 'center', label: 'Center' },
                { id: 'bottom_left', label: 'Bottom-Left' },
                { id: 'bottom_center', label: 'Bottom-Center' },
                { id: 'bottom_right', label: 'Bottom-Right' },
              ].map((btn) => {
                const isSelected = position === btn.id;
                return (
                  <button
                    key={btn.id}
                    type="button"
                    onClick={() => setPosition(btn.id as WatermarkPosition)}
                    className={`px-2.5 py-2 rounded-lg text-xs font-medium transition-colors border ${
                      isSelected
                        ? 'bg-red-600 border-red-500 text-white font-semibold'
                        : 'bg-zinc-800 border-zinc-700 text-zinc-400 hover:text-zinc-200'
                    }`}
                  >
                    {btn.label}
                  </button>
                );
              })}
            </div>
          </div>

          {/* 3. Opacity, Scale & Margin Sliders */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 border-t border-zinc-800 pt-4">
            <div className="space-y-1.5">
              <div className="flex justify-between items-center text-xs">
                <label htmlFor="watermark-opacity-slider" className="font-medium text-zinc-300">Opacity</label>
                <span className="font-mono text-red-400">{Math.round(opacity * 100)}%</span>
              </div>
              <input
                id="watermark-opacity-slider"
                type="range"
                aria-label="Opacity"
                min={0.1}
                max={1.0}
                step={0.05}
                value={opacity}
                onChange={(e) => setOpacity(Number(e.target.value))}
                className="w-full accent-red-500 cursor-pointer"
              />
            </div>

            <div className="space-y-1.5">
              <div className="flex justify-between items-center text-xs">
                <label htmlFor="watermark-scale-slider" className="font-medium text-zinc-300">Scale</label>
                <span className="font-mono text-red-400">{scale}%</span>
              </div>
              <input
                id="watermark-scale-slider"
                type="range"
                aria-label="Scale"
                min={5}
                max={50}
                step={1}
                value={scale}
                onChange={(e) => setScale(Number(e.target.value))}
                className="w-full accent-red-500 cursor-pointer"
              />
            </div>

            <div className="space-y-1.5">
              <div className="flex justify-between items-center text-xs">
                <label htmlFor="watermark-hmargin-slider" className="font-medium text-zinc-300">H-Margin</label>
                <span className="font-mono text-zinc-400">{hMargin}px</span>
              </div>
              <input
                id="watermark-hmargin-slider"
                type="range"
                aria-label="H-Margin"
                min={5}
                max={80}
                step={5}
                value={hMargin}
                onChange={(e) => setHMargin(Number(e.target.value))}
                className="w-full accent-zinc-500 cursor-pointer"
              />
            </div>

            <div className="space-y-1.5">
              <div className="flex justify-between items-center text-xs">
                <label htmlFor="watermark-vmargin-slider" className="font-medium text-zinc-300">V-Margin</label>
                <span className="font-mono text-zinc-400">{vMargin}px</span>
              </div>
              <input
                id="watermark-vmargin-slider"
                type="range"
                aria-label="V-Margin"
                min={5}
                max={80}
                step={5}
                value={vMargin}
                onChange={(e) => setVMargin(Number(e.target.value))}
                className="w-full accent-zinc-500 cursor-pointer"
              />
            </div>
          </div>

          {/* Target Video (Optional) */}
          <div className="space-y-1.5">
            <label htmlFor="watermark-video-path" className="block text-xs font-medium text-zinc-400">Target Video Path (Optional)</label>
            <input
              id="watermark-video-path"
              type="text"
              value={videoPath}
              onChange={(e) => setVideoPath(e.target.value)}
              placeholder="/path/to/video.mp4"
              className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-xs text-zinc-200 focus:outline-none focus:border-red-500"
            />
          </div>

          {/* Apply Watermark Button */}
          <button
            type="submit"
            data-testid="apply-watermark-button"
            disabled={isSubmitting}
            className="w-full flex items-center justify-center space-x-2 rounded-lg bg-red-600 hover:bg-red-500 text-white px-4 py-2.5 text-sm font-semibold transition-colors disabled:opacity-50"
          >
            {isSubmitting ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                <span>Applying Watermark...</span>
              </>
            ) : (
              <>
                <Play className="h-4 w-4 fill-white" />
                <span>Apply Watermark & Run</span>
              </>
            )}
          </button>
        </form>
      </div>

      {/* 4. Preview Overlay Panel */}
      <div className="lg:col-span-5 flex flex-col items-center justify-center space-y-3">
        <div className="flex items-center space-x-2 text-xs font-medium text-zinc-400">
          <Eye className="h-4 w-4 text-red-400" />
          <span>Interactive Preview Overlay (9:16 Shorts)</span>
        </div>

        {/* Mock Phone Frame (9:16) */}
        <div className="relative w-64 h-[440px] bg-gradient-to-b from-zinc-800 via-zinc-900 to-black rounded-2xl border-4 border-zinc-700 shadow-2xl overflow-hidden flex flex-col justify-between p-3 select-none">
          {/* Simulated Video Content */}
          <div className="absolute inset-0 flex flex-col items-center justify-center text-zinc-600 opacity-40 pointer-events-none">
            <Play className="h-16 w-16 stroke-1 fill-zinc-700/50" />
            <span className="text-[11px] font-mono mt-2">Video Background</span>
          </div>

          {/* Top Info Bar */}
          <div className="relative z-10 flex justify-between items-center text-[10px] text-zinc-400 font-mono">
            <span>ViralCutter</span>
            <span className="px-1.5 py-0.5 rounded bg-black/60 text-zinc-300">9:16</span>
          </div>

          {/* THE WATERMARK OVERLAY */}
          {mode === 'image' ? (
            imagePreviewUrl ? (
              <img
                src={imagePreviewUrl}
                alt="Watermark Overlay"
                style={getWatermarkOverlayStyle()}
                className="object-contain"
              />
            ) : (
              <div
                style={getWatermarkOverlayStyle()}
                className="bg-red-600/80 text-white font-bold text-[10px] px-2 py-1 rounded shadow"
              >
                LOGO
              </div>
            )
          ) : (
            <div
              style={{
                ...getWatermarkOverlayStyle(),
                color: textColor,
                fontSize: `${Math.round(fontSize * 0.35)}px`,
                fontWeight: 'bold',
                textShadow: '0 2px 4px rgba(0,0,0,0.8)',
              }}
            >
              {watermarkText || '@Watermark'}
            </div>
          )}

          {/* Bottom Captions Simulation */}
          <div className="relative z-10 text-center pb-2">
            <span className="bg-black/60 px-2 py-1 rounded text-[10px] font-semibold text-yellow-300">
              Sample Subtitle Text
            </span>
          </div>
        </div>

        <p className="text-[11px] text-zinc-500 text-center max-w-xs">
          Watermark position, scale ({scale}%), and opacity ({Math.round(opacity * 100)}%) update in real-time.
        </p>
      </div>
    </div>
  );
};

export default WatermarkTab;
