import React, { useRef, useEffect, useState, useCallback } from 'react';
import { Crop, RotateCcw, Film, Upload, Loader2, AlignCenter, AlignLeft, AlignRight } from 'lucide-react';
import type { SampleFrameItem } from '../api/types';

export interface VerticalCropEditorProps {
  imageSrc?: string;
  videoSrc?: string;
  sampleFrames?: SampleFrameItem[];
  activeSampleIndex?: number;
  onSelectSampleFrame?: (index: number) => void;
  isLoadingSamples?: boolean;
  cropBox: string;
  onChange: (cropBox: string) => void;
}

export interface BoxRect {
  x: number;
  y: number;
  w: number;
  h: number;
}

// In a 16:9 source frame, normalized width to height ratio for an exact 9:16 pixel crop is:
// (w_norm * 16) / (h_norm * 9) = 9/16 => w_norm / h_norm = 81 / 256 ≈ 0.31640625
export const AR_VERTICAL = 81 / 256;
export const DEFAULT_VERTICAL_BOX: BoxRect = {
  x: 0.3418,
  y: 0.0,
  w: 0.3164,
  h: 1.0,
};

export function parseBox(str: string, defaultVal: BoxRect): BoxRect {
  try {
    if (!str) return defaultVal;
    const parts = str.split(',').map((s) => parseFloat(s.trim()));
    if (parts.length === 4 && parts.every((n) => !isNaN(n) && isFinite(n))) {
      return { x: parts[0], y: parts[1], w: parts[2], h: parts[3] };
    }
  } catch {
    // fallback
  }
  return defaultVal;
}

export function formatBox(b: BoxRect): string {
  return `${b.x.toFixed(4)},${b.y.toFixed(4)},${b.w.toFixed(4)},${b.h.toFixed(4)}`;
}

type HandleType = 'nw' | 'ne' | 'se' | 'sw';

function getHandleAt(
  mx: number,
  my: number,
  b: BoxRect,
  canvasW: number,
  canvasH: number
): HandleType | null {
  const px = mx * canvasW;
  const py = my * canvasH;
  const bx = b.x * canvasW;
  const by = b.y * canvasH;
  const bw = b.w * canvasW;
  const bh = b.h * canvasH;
  const hitRadius = 10;

  const corners: Array<[number, number, HandleType]> = [
    [bx, by, 'nw'],
    [bx + bw, by, 'ne'],
    [bx + bw, by + bh, 'se'],
    [bx, by + bh, 'sw'],
  ];

  for (const [hx, hy, type] of corners) {
    if (Math.hypot(px - hx, py - hy) <= hitRadius) {
      return type;
    }
  }
  return null;
}

export const VerticalCropEditor: React.FC<VerticalCropEditorProps> = ({
  imageSrc,
  videoSrc,
  sampleFrames,
  activeSampleIndex,
  onSelectSampleFrame,
  isLoadingSamples,
  cropBox,
  onChange,
}) => {
  const sourceCanvasRef = useRef<HTMLCanvasElement>(null);
  const previewCanvasRef = useRef<HTMLCanvasElement>(null);
  const imageRef = useRef<HTMLImageElement | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [box, setBox] = useState<BoxRect>(() =>
    parseBox(cropBox, DEFAULT_VERTICAL_BOX)
  );
  const [selectedFrameIdx, setSelectedFrameIdx] = useState<number>(() => activeSampleIndex ?? 0);
  const [customImageUri, setCustomImageUri] = useState<string | null>(null);

  const [activeDrag, setActiveDrag] = useState<{
    type: 'move' | HandleType;
    startX: number;
    startY: number;
    startBox: BoxRect;
  } | null>(null);

  const lastEmittedRef = useRef<string>('');

  useEffect(() => {
    if (activeSampleIndex !== undefined && activeSampleIndex >= 0) {
      setSelectedFrameIdx(activeSampleIndex);
    }
  }, [activeSampleIndex]);

  // Sync state to parent on change
  useEffect(() => {
    const formatted = formatBox(box);
    if (lastEmittedRef.current !== formatted) {
      lastEmittedRef.current = formatted;
      onChange(formatted);
    }
  }, [box, onChange]);

  // Re-sync if parent prop changes externally
  useEffect(() => {
    if (cropBox && cropBox !== lastEmittedRef.current) {
      const parsed = parseBox(cropBox, DEFAULT_VERTICAL_BOX);
      setBox(parsed);
      lastEmittedRef.current = cropBox;
    }
  }, [cropBox]);

  // Draw 16:9 Source Canvas with 9:16 single bounding box
  const drawSource = useCallback(() => {
    const canvas = sourceCanvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    ctx.clearRect(0, 0, canvas.width, canvas.height);

    if (imageRef.current) {
      ctx.drawImage(imageRef.current, 0, 0, canvas.width, canvas.height);
    } else {
      ctx.fillStyle = '#18181b';
      ctx.fillRect(0, 0, canvas.width, canvas.height);
      ctx.strokeStyle = '#27272a';
      ctx.strokeRect(0, 0, canvas.width, canvas.height);
      ctx.fillStyle = '#71717a';
      ctx.font = '12px sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText('No video frame loaded', canvas.width / 2, canvas.height / 2);
    }

    const bx = box.x * canvas.width;
    const by = box.y * canvas.height;
    const bw = box.w * canvas.width;
    const bh = box.h * canvas.height;

    // Dim non-cropped area (overlay mask)
    ctx.fillStyle = 'rgba(0, 0, 0, 0.45)';
    // Top
    ctx.fillRect(0, 0, canvas.width, by);
    // Bottom
    ctx.fillRect(0, by + bh, canvas.width, canvas.height - (by + bh));
    // Left
    ctx.fillRect(0, by, bx, bh);
    // Right
    ctx.fillRect(bx + bw, by, canvas.width - (bx + bw), bh);

    // Box highlight
    ctx.fillStyle = 'rgba(239, 68, 68, 0.15)';
    ctx.fillRect(bx, by, bw, bh);

    // Box border
    ctx.lineWidth = 2;
    ctx.strokeStyle = '#ef4444';
    ctx.strokeRect(bx, by, bw, bh);

    // Center grid lines (rule of thirds)
    ctx.lineWidth = 1;
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.25)';
    ctx.beginPath();
    // vertical thirds
    ctx.moveTo(bx + bw / 3, by);
    ctx.lineTo(bx + bw / 3, by + bh);
    ctx.moveTo(bx + (2 * bw) / 3, by);
    ctx.lineTo(bx + (2 * bw) / 3, by + bh);
    // horizontal thirds
    ctx.moveTo(bx, by + bh / 3);
    ctx.lineTo(bx + bw, by + bh / 3);
    ctx.moveTo(bx, by + (2 * bh) / 3);
    ctx.lineTo(bx + bw, by + (2 * bh) / 3);
    ctx.stroke();

    // Label banner
    ctx.fillStyle = '#ef4444';
    const bannerW = Math.min(bw, 140);
    ctx.fillRect(bx, by - 22, bannerW, 22);
    ctx.fillStyle = '#ffffff';
    ctx.font = 'bold 11px sans-serif';
    ctx.textAlign = 'left';
    ctx.fillText('9:16 Vertical Crop', bx + 6, by - 7);

    // Corner handles
    const handleSize = 8;
    ctx.fillStyle = '#ffffff';
    ctx.strokeStyle = '#ef4444';
    ctx.lineWidth = 1.5;
    [
      [bx, by],
      [bx + bw, by],
      [bx + bw, by + bh],
      [bx, by + bh],
    ].forEach(([hx, hy]) => {
      ctx.fillRect(hx - handleSize / 2, hy - handleSize / 2, handleSize, handleSize);
      ctx.strokeRect(hx - handleSize / 2, hy - handleSize / 2, handleSize, handleSize);
    });
  }, [box]);

  // Draw 9:16 Live Preview Canvas
  const drawPreview = useCallback(() => {
    const canvas = previewCanvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    ctx.clearRect(0, 0, canvas.width, canvas.height);

    const targetW = canvas.width;
    const targetH = canvas.height;

    const img = imageRef.current;
    if (img && img.naturalWidth > 0 && img.naturalHeight > 0) {
      const sx = box.x * img.naturalWidth;
      const sy = box.y * img.naturalHeight;
      const sw = box.w * img.naturalWidth;
      const sh = box.h * img.naturalHeight;
      ctx.drawImage(img, sx, sy, sw, sh, 0, 0, targetW, targetH);
    } else {
      ctx.fillStyle = '#18181b';
      ctx.fillRect(0, 0, targetW, targetH);
      ctx.fillStyle = '#ef444430';
      ctx.fillRect(0, 0, targetW, targetH);
      ctx.fillStyle = '#a1a1aa';
      ctx.font = '11px sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText('9:16 Live Preview', targetW / 2, targetH / 2);
    }
  }, [box]);

  // Determine active frame source
  const activeSampleFrame =
    sampleFrames && sampleFrames.length > 0
      ? sampleFrames[selectedFrameIdx] || sampleFrames[0]
      : null;

  const activeSrc =
    customImageUri ||
    (activeSampleFrame ? activeSampleFrame.data_uri || activeSampleFrame.path : imageSrc || videoSrc);

  useEffect(() => {
    if (!activeSrc) {
      imageRef.current = null;
      drawSource();
      drawPreview();
      return;
    }
    const img = new Image();
    img.crossOrigin = 'anonymous';
    img.src = activeSrc;
    img.onload = () => {
      imageRef.current = img;
      drawSource();
      drawPreview();
    };
    img.onerror = () => {
      imageRef.current = null;
      drawSource();
      drawPreview();
    };
  }, [activeSrc, drawSource, drawPreview]);

  useEffect(() => {
    drawSource();
    drawPreview();
  }, [drawSource, drawPreview]);

  // Drag & Resize Calculation
  const handleDragMove = useCallback(
    (mx: number, my: number) => {
      if (!activeDrag) return;
      const dx = mx - activeDrag.startX;
      const dy = my - activeDrag.startY;
      const b = activeDrag.startBox;

      if (activeDrag.type === 'move') {
        const nextX = Math.max(0, Math.min(1.0 - b.w, b.x + dx));
        const nextY = Math.max(0, Math.min(1.0 - b.h, b.y + dy));
        setBox({ ...b, x: nextX, y: nextY });
        return;
      }

      const ar = AR_VERTICAL;
      const minH = 0.25;
      const minW = minH * ar;
      let x = b.x;
      let y = b.y;
      let w = b.w;
      let h = b.h;

      if (activeDrag.type === 'se') {
        const dw = (dx + dy * ar) / 2;
        let newW = Math.max(minW, b.w + dw);
        let newH = newW / ar;
        if (b.x + newW > 1.0) {
          newW = 1.0 - b.x;
          newH = newW / ar;
        }
        if (b.y + newH > 1.0) {
          newH = 1.0 - b.y;
          newW = newH * ar;
        }
        w = Math.max(minW, newW);
        h = w / ar;
        x = b.x;
        y = b.y;
      } else if (activeDrag.type === 'sw') {
        const fixedRight = b.x + b.w;
        const dw = (-dx + dy * ar) / 2;
        let newW = Math.max(minW, b.w + dw);
        let newH = newW / ar;
        if (fixedRight - newW < 0.0) {
          newW = fixedRight;
          newH = newW / ar;
        }
        if (b.y + newH > 1.0) {
          newH = 1.0 - b.y;
          newW = newH * ar;
        }
        w = Math.max(minW, newW);
        h = w / ar;
        x = fixedRight - w;
        y = b.y;
      } else if (activeDrag.type === 'ne') {
        const fixedBottom = b.y + b.h;
        const dw = (dx - dy * ar) / 2;
        let newW = Math.max(minW, b.w + dw);
        let newH = newW / ar;
        if (b.x + newW > 1.0) {
          newW = 1.0 - b.x;
          newH = newW / ar;
        }
        if (fixedBottom - newH < 0.0) {
          newH = fixedBottom;
          newW = newH * ar;
        }
        w = Math.max(minW, newW);
        h = w / ar;
        x = b.x;
        y = fixedBottom - h;
      } else if (activeDrag.type === 'nw') {
        const fixedRight = b.x + b.w;
        const fixedBottom = b.y + b.h;
        const dw = (-dx - dy * ar) / 2;
        let newW = Math.max(minW, b.w + dw);
        let newH = newW / ar;
        if (fixedRight - newW < 0.0) {
          newW = fixedRight;
          newH = newW / ar;
        }
        if (fixedBottom - newH < 0.0) {
          newH = fixedBottom;
          newW = newH * ar;
        }
        w = Math.max(minW, newW);
        h = w / ar;
        x = fixedRight - w;
        y = fixedBottom - h;
      }

      setBox({
        x: Math.max(0, Math.min(1.0 - w, x)),
        y: Math.max(0, Math.min(1.0 - h, y)),
        w: Math.min(1.0, w),
        h: Math.min(1.0, h),
      });
    },
    [activeDrag, box]
  );

  const handleMouseDown = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = sourceCanvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const mx = (e.clientX - rect.left) / rect.width;
    const my = (e.clientY - rect.top) / rect.height;

    const handle = getHandleAt(mx, my, box, canvas.width, canvas.height);
    if (handle) {
      setActiveDrag({
        type: handle,
        startX: mx,
        startY: my,
        startBox: { ...box },
      });
      return;
    }

    if (mx >= box.x && mx <= box.x + box.w && my >= box.y && my <= box.y + box.h) {
      setActiveDrag({
        type: 'move',
        startX: mx,
        startY: my,
        startBox: { ...box },
      });
    }
  };

  const updateCursor = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = sourceCanvasRef.current;
    if (!canvas) return;
    if (activeDrag) return;

    const rect = canvas.getBoundingClientRect();
    const mx = (e.clientX - rect.left) / rect.width;
    const my = (e.clientY - rect.top) / rect.height;

    const handle = getHandleAt(mx, my, box, canvas.width, canvas.height);
    if (handle) {
      canvas.style.cursor =
        handle === 'nw' || handle === 'se' ? 'nwse-resize' : 'nesw-resize';
      return;
    }

    if (mx >= box.x && mx <= box.x + box.w && my >= box.y && my <= box.y + box.h) {
      canvas.style.cursor = 'move';
      return;
    }

    canvas.style.cursor = 'default';
  };

  // Window drag listeners
  useEffect(() => {
    if (!activeDrag) return;
    const canvas = sourceCanvasRef.current;
    if (!canvas) return;

    const onWindowMove = (e: MouseEvent) => {
      const rect = canvas.getBoundingClientRect();
      const mx = (e.clientX - rect.left) / rect.width;
      const my = (e.clientY - rect.top) / rect.height;
      handleDragMove(mx, my);
    };

    const onWindowUp = () => {
      setActiveDrag(null);
    };

    window.addEventListener('mousemove', onWindowMove);
    window.addEventListener('mouseup', onWindowUp);
    return () => {
      window.removeEventListener('mousemove', onWindowMove);
      window.removeEventListener('mouseup', onWindowUp);
    };
  }, [activeDrag, handleDragMove]);

  // Presets
  const applyPreset = (pos: 'center' | 'left' | 'right') => {
    setBox((prev) => {
      const h = prev.h;
      const w = prev.w;
      const y = (1.0 - h) / 2;
      let x = (1.0 - w) / 2;

      if (pos === 'left') {
        x = 0.04;
      } else if (pos === 'right') {
        x = 1.0 - w - 0.04;
      }
      return { x: Math.max(0, Math.min(1.0 - w, x)), y: Math.max(0, Math.min(1.0 - h, y)), w, h };
    });
  };


  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4 space-y-4">
      {/* Header & Preset Toolbar */}
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-zinc-800 pb-2">
        <div className="flex items-center space-x-2">
          <Crop className="h-4 w-4 text-red-400" />
          <span className="text-xs font-semibold text-white">Manual 9:16 Vertical Crop</span>
        </div>
        <div className="flex items-center space-x-1.5">
          <button
            type="button"
            onClick={() => applyPreset('left')}
            className="px-2.5 py-1 rounded bg-zinc-800 hover:bg-zinc-700 text-[11px] text-zinc-300 transition-colors flex items-center space-x-1"
          >
            <AlignLeft className="h-3 w-3" />
            <span>Left</span>
          </button>
          <button
            type="button"
            onClick={() => applyPreset('center')}
            className="px-2.5 py-1 rounded bg-zinc-800 hover:bg-zinc-700 text-[11px] text-zinc-300 transition-colors flex items-center space-x-1"
          >
            <AlignCenter className="h-3 w-3" />
            <span>Center</span>
          </button>
          <button
            type="button"
            onClick={() => applyPreset('right')}
            className="px-2.5 py-1 rounded bg-zinc-800 hover:bg-zinc-700 text-[11px] text-zinc-300 transition-colors flex items-center space-x-1"
          >
            <AlignRight className="h-3 w-3" />
            <span>Right</span>
          </button>
          <button
            type="button"
            title="Reset to default 1080x1920 center"
            aria-label="Reset framing"
            onClick={() => setBox(DEFAULT_VERTICAL_BOX)}
            className="px-2.5 py-1 rounded bg-zinc-800 hover:bg-zinc-700 text-[11px] text-zinc-400 hover:text-zinc-200 transition-colors flex items-center space-x-1"
          >
            <RotateCcw className="h-3 w-3" />
            <span>Reset</span>
          </button>
        </div>
      </div>

      {/* 3 Source Sample Frames Selector Toolbar */}
      <div className="flex flex-wrap items-center justify-between gap-2 p-2.5 bg-zinc-950/80 rounded-lg border border-zinc-800/80">
        <div className="flex items-center space-x-2">
          <span className="text-[11px] font-medium text-zinc-300 flex items-center space-x-1.5 shrink-0">
            <Film className="h-3.5 w-3.5 text-red-400" />
            <span>Source Frames:</span>
          </span>

          {isLoadingSamples ? (
            <span className="text-[11px] text-zinc-400 flex items-center space-x-1.5 font-mono">
              <Loader2 className="h-3 w-3 animate-spin text-red-400" />
              <span>Extracting 3 sample frames...</span>
            </span>
          ) : sampleFrames && sampleFrames.length > 0 ? (
            <div className="flex items-center space-x-1.5 overflow-x-auto py-0.5">
              {sampleFrames.map((frame, idx) => (
                <button
                  key={frame.index ?? idx}
                  type="button"
                  onClick={() => {
                    setCustomImageUri(null);
                    setSelectedFrameIdx(idx);
                    onSelectSampleFrame?.(idx);
                  }}
                  className={`flex items-center space-x-1.5 px-2.5 py-1 rounded text-xs font-mono transition-all border ${
                    customImageUri === null && selectedFrameIdx === idx
                      ? 'bg-red-950/80 text-red-300 border-red-500/80 ring-1 ring-red-500/30 font-semibold'
                      : 'bg-zinc-900 text-zinc-400 border-zinc-800 hover:text-zinc-200 hover:border-zinc-700'
                  }`}
                >
                  <span
                    className={`w-1.5 h-1.5 rounded-full ${
                      customImageUri === null && selectedFrameIdx === idx
                        ? 'bg-red-400 animate-pulse'
                        : 'bg-zinc-600'
                    }`}
                  />
                  <span>Sample {idx + 1} ({frame.time_label})</span>
                </button>
              ))}
            </div>
          ) : (
            <span className="text-[11px] text-zinc-500 italic">
              Upload video above to load 3 sample frames
            </span>
          )}
        </div>

        {/* Optional Custom Frame Image Uploader */}
        <div className="flex items-center space-x-1.5">
          <input
            type="file"
            ref={fileInputRef}
            accept="image/*"
            className="hidden"
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) {
                const reader = new FileReader();
                reader.onload = (event) => {
                  if (event.target?.result) {
                    setCustomImageUri(event.target.result as string);
                  }
                };
                reader.readAsDataURL(file);
              }
            }}
          />
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            className={`px-2 py-1 rounded text-[11px] transition-colors border flex items-center space-x-1 ${
              customImageUri
                ? 'bg-blue-950/80 text-blue-300 border-blue-500/80'
                : 'bg-zinc-900 text-zinc-400 border-zinc-800 hover:text-zinc-200 hover:border-zinc-700'
            }`}
            title="Upload custom frame screenshot"
          >
            <Upload className="h-3 w-3" />
            <span>{customImageUri ? 'Custom Frame Active' : 'Custom Image'}</span>
          </button>
          {customImageUri && (
            <button
              type="button"
              onClick={() => setCustomImageUri(null)}
              className="px-1.5 py-0.5 rounded text-[11px] text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800"
              title="Revert to video sample frames"
            >
              ×
            </button>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-12 gap-4 items-start">
        {/* 16:9 Source Canvas */}
        <div className="md:col-span-8 flex flex-col space-y-1.5">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-medium text-zinc-400">
              Source 16:9 Frame (Drag to reposition & resize 9:16 window)
            </span>
            <div className="flex items-center space-x-2 text-[10px] text-zinc-500">
              <span className="inline-block w-2 h-2 rounded-full bg-red-500" />
              <span>9:16 Vertical Ratio (0.5625)</span>
            </div>
          </div>
          <canvas
            ref={sourceCanvasRef}
            width={640}
            height={360}
            onMouseDown={handleMouseDown}
            onMouseMove={updateCursor}
            onMouseUp={() => setActiveDrag(null)}
            className="w-full aspect-video rounded-lg border border-zinc-800 cursor-move bg-zinc-950 shadow-inner"
          />
        </div>

        {/* 9:16 Live Preview */}
        <div className="md:col-span-4 flex flex-col space-y-1.5">
          <span className="text-[11px] font-medium text-zinc-400">
            Live 9:16 Preview
          </span>
          <canvas
            ref={previewCanvasRef}
            width={180}
            height={320}
            className="w-36 h-64 mx-auto rounded-lg border border-zinc-800 bg-zinc-950 shadow-md"
          />
        </div>
      </div>
    </div>
  );
};

export default VerticalCropEditor;
