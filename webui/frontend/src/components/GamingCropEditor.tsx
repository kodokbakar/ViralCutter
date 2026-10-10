import React, { useRef, useEffect, useState, useCallback } from 'react';
import { Gamepad2, RotateCcw } from 'lucide-react';

export interface GamingCropEditorProps {
  imageSrc?: string;
  videoSrc?: string;
  facecamCrop: string;
  gameplayCrop: string;
  onChange: (facecamCrop: string, gameplayCrop: string) => void;
}

export interface BoxRect {
  x: number;
  y: number;
  w: number;
  h: number;
}

export const AR_FACECAM = 1080 / 576; // ~1.875
export const AR_GAMEPLAY = 1080 / 1344; // ~0.80357

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
    if (Math.abs(px - hx) <= hitRadius && Math.abs(py - hy) <= hitRadius) {
      return type;
    }
  }
  return null;
}

export const GamingCropEditor: React.FC<GamingCropEditorProps> = ({
  imageSrc,
  videoSrc,
  facecamCrop,
  gameplayCrop,
  onChange,
}) => {
  const sourceCanvasRef = useRef<HTMLCanvasElement>(null);
  const previewCanvasRef = useRef<HTMLCanvasElement>(null);
  const imageRef = useRef<HTMLImageElement | null>(null);

  const [facecam, setFacecam] = useState<BoxRect>(() =>
    parseBox(facecamCrop, { x: 0.68, y: 0.05, w: 0.28, h: 0.1493 })
  );
  const [gameplay, setGameplay] = useState<BoxRect>(() =>
    parseBox(gameplayCrop, { x: 0.25, y: 0.0, w: 0.5, h: 0.622 })
  );

  const [activeDrag, setActiveDrag] = useState<{
    target: 'facecam' | 'gameplay';
    type: 'move' | HandleType;
    startX: number;
    startY: number;
    startBox: BoxRect;
  } | null>(null);

  const lastEmittedRef = useRef<string>('');

  // Sync state to parent on change
  useEffect(() => {
    const fcStr = formatBox(facecam);
    const gpStr = formatBox(gameplay);
    const key = `${fcStr}|${gpStr}`;
    if (lastEmittedRef.current !== key) {
      lastEmittedRef.current = key;
      onChange(fcStr, gpStr);
    }
  }, [facecam, gameplay, onChange]);

  // Sync from parent props when changed externally
  useEffect(() => {
    const key = `${facecamCrop}|${gameplayCrop}`;
    if (key !== lastEmittedRef.current) {
      const parsedFc = parseBox(facecamCrop, { x: 0.68, y: 0.05, w: 0.28, h: 0.1493 });
      const parsedGp = parseBox(gameplayCrop, { x: 0.25, y: 0.0, w: 0.5, h: 0.622 });
      setFacecam(parsedFc);
      setGameplay(parsedGp);
      lastEmittedRef.current = `${formatBox(parsedFc)}|${formatBox(parsedGp)}`;
    }
  }, [facecamCrop, gameplayCrop]);

  // Draw 16:9 Source Canvas
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
      ctx.fillStyle = '#52525b';
      ctx.font = '12px sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText('Source Frame (16:9)', canvas.width / 2, canvas.height / 2);
      ctx.textAlign = 'start';
    }

    const renderBox = (b: BoxRect, color: string, label: string) => {
      const bx = b.x * canvas.width;
      const by = b.y * canvas.height;
      const bw = b.w * canvas.width;
      const bh = b.h * canvas.height;

      // Shaded overlay
      ctx.fillStyle = `${color}25`;
      ctx.fillRect(bx, by, bw, bh);

      // Box border
      ctx.lineWidth = 2;
      ctx.strokeStyle = color;
      ctx.strokeRect(bx, by, bw, bh);

      // Label banner
      const labelY = by >= 22 ? by - 20 : by + 2;
      ctx.fillStyle = color;
      ctx.fillRect(bx, labelY, Math.min(bw, 120), 18);
      ctx.fillStyle = '#ffffff';
      ctx.font = 'bold 11px sans-serif';
      ctx.fillText(label, bx + 6, labelY + 13);

      // 4 Corner handles
      const handleSize = 8;
      ctx.fillStyle = '#ffffff';
      [
        [bx, by],
        [bx + bw, by],
        [bx + bw, by + bh],
        [bx, by + bh],
      ].forEach(([hx, hy]) => {
        ctx.fillRect(hx - handleSize / 2, hy - handleSize / 2, handleSize, handleSize);
        ctx.strokeStyle = color;
        ctx.lineWidth = 1.5;
        ctx.strokeRect(hx - handleSize / 2, hy - handleSize / 2, handleSize, handleSize);
      });
    };

    renderBox(gameplay, '#10b981', 'Gameplay (70%)');
    renderBox(facecam, '#3b82f6', 'Facecam (30%)');
  }, [facecam, gameplay]);

  // Draw 9:16 Split Preview Canvas
  const drawPreview = useCallback(() => {
    const canvas = previewCanvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    ctx.clearRect(0, 0, canvas.width, canvas.height);

    const targetW = canvas.width;
    const targetH = canvas.height;
    const camH = targetH * 0.3;
    const gameH = targetH * 0.7;

    const img = imageRef.current;
    if (img && img.naturalWidth && img.naturalHeight) {
      // Top 30% from facecam
      const fx = facecam.x * img.naturalWidth;
      const fy = facecam.y * img.naturalHeight;
      const fw = facecam.w * img.naturalWidth;
      const fh = facecam.h * img.naturalHeight;
      ctx.drawImage(img, fx, fy, fw, fh, 0, 0, targetW, camH);

      // Bottom 70% from gameplay
      const gx = gameplay.x * img.naturalWidth;
      const gy = gameplay.y * img.naturalHeight;
      const gw = gameplay.w * img.naturalWidth;
      const gh = gameplay.h * img.naturalHeight;
      ctx.drawImage(img, gx, gy, gw, gh, 0, camH, targetW, gameH);
    } else {
      ctx.fillStyle = '#2563eb30';
      ctx.fillRect(0, 0, targetW, camH);
      ctx.fillStyle = '#05966930';
      ctx.fillRect(0, camH, targetW, gameH);

      ctx.fillStyle = '#93c5fd';
      ctx.font = '10px sans-serif';
      ctx.fillText('Facecam 30%', 10, camH / 2 + 3);

      ctx.fillStyle = '#6ee7b7';
      ctx.font = '10px sans-serif';
      ctx.fillText('Gameplay 70%', 10, camH + gameH / 2 + 3);
    }

    // Divider line
    ctx.lineWidth = 2;
    ctx.strokeStyle = '#09090b';
    ctx.beginPath();
    ctx.moveTo(0, camH);
    ctx.lineTo(targetW, camH);
    ctx.stroke();
  }, [facecam, gameplay]);

  // Load and cache image
  useEffect(() => {
    const src = imageSrc || videoSrc;
    if (!src) {
      imageRef.current = null;
      drawSource();
      drawPreview();
      return;
    }
    const img = new Image();
    img.crossOrigin = 'anonymous';
    img.src = src;
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
  }, [imageSrc, videoSrc, drawSource, drawPreview]);

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
        const updated: BoxRect = { ...b, x: nextX, y: nextY };
        if (activeDrag.target === 'facecam') {
          setFacecam(updated);
        } else {
          setGameplay(updated);
        }
        return;
      }

      // Corner resize with aspect ratio lock
      const ar = activeDrag.target === 'facecam' ? AR_FACECAM : AR_GAMEPLAY;
      const minW = 0.08;
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
        x = b.x;
        y = b.y;
        w = Math.max(minW, newW);
        h = w / ar;
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

      const updated: BoxRect = {
        x: Math.max(0, Math.min(1.0 - w, x)),
        y: Math.max(0, Math.min(1.0 - h, y)),
        w,
        h,
      };

      if (activeDrag.target === 'facecam') {
        setFacecam(updated);
      } else {
        setGameplay(updated);
      }
    },
    [activeDrag]
  );

  // Global mousemove/mouseup listener while dragging
  useEffect(() => {
    if (!activeDrag) return;

    const onWindowMouseMove = (e: MouseEvent) => {
      const canvas = sourceCanvasRef.current;
      if (!canvas) return;
      const rect = canvas.getBoundingClientRect();
      const mx = (e.clientX - rect.left) / rect.width;
      const my = (e.clientY - rect.top) / rect.height;
      handleDragMove(mx, my);
    };

    window.addEventListener('mousemove', onWindowMouseMove);
    const stopDrag = () => setActiveDrag(null);
    window.addEventListener('mouseup', stopDrag);
    return () => {
      window.removeEventListener('mousemove', onWindowMouseMove);
      window.removeEventListener('mouseup', stopDrag);
    };
  }, [activeDrag, handleDragMove]);

  // Cursor updates
  const updateCursor = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = sourceCanvasRef.current;
    if (!canvas) return;

    if (activeDrag) {
      if (activeDrag.type === 'move') {
        canvas.style.cursor = 'move';
      } else if (activeDrag.type === 'nw' || activeDrag.type === 'se') {
        canvas.style.cursor = 'nwse-resize';
      } else {
        canvas.style.cursor = 'nesw-resize';
      }
      return;
    }

    const rect = canvas.getBoundingClientRect();
    const mx = (e.clientX - rect.left) / rect.width;
    const my = (e.clientY - rect.top) / rect.height;

    const fcHandle = getHandleAt(mx, my, facecam, canvas.width, canvas.height);
    const gpHandle = getHandleAt(mx, my, gameplay, canvas.width, canvas.height);
    const handle = fcHandle || gpHandle;

    if (handle === 'nw' || handle === 'se') {
      canvas.style.cursor = 'nwse-resize';
    } else if (handle === 'ne' || handle === 'sw') {
      canvas.style.cursor = 'nesw-resize';
    } else if (
      (mx >= facecam.x && mx <= facecam.x + facecam.w && my >= facecam.y && my <= facecam.y + facecam.h) ||
      (mx >= gameplay.x && mx <= gameplay.x + gameplay.w && my >= gameplay.y && my <= gameplay.y + gameplay.h)
    ) {
      canvas.style.cursor = 'move';
    } else {
      canvas.style.cursor = 'default';
    }
  };

  const handleMouseDown = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = sourceCanvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const mx = (e.clientX - rect.left) / rect.width;
    const my = (e.clientY - rect.top) / rect.height;

    // Check Facecam handles first (Facecam is on top)
    const fcHandle = getHandleAt(mx, my, facecam, canvas.width, canvas.height);
    if (fcHandle) {
      setActiveDrag({
        target: 'facecam',
        type: fcHandle,
        startX: mx,
        startY: my,
        startBox: { ...facecam },
      });
      return;
    }

    // Check Gameplay handles
    const gpHandle = getHandleAt(mx, my, gameplay, canvas.width, canvas.height);
    if (gpHandle) {
      setActiveDrag({
        target: 'gameplay',
        type: gpHandle,
        startX: mx,
        startY: my,
        startBox: { ...gameplay },
      });
      return;
    }

    // Check inside Facecam box (move)
    if (mx >= facecam.x && mx <= facecam.x + facecam.w && my >= facecam.y && my <= facecam.y + facecam.h) {
      setActiveDrag({
        target: 'facecam',
        type: 'move',
        startX: mx,
        startY: my,
        startBox: { ...facecam },
      });
      return;
    }

    // Check inside Gameplay box (move)
    if (mx >= gameplay.x && mx <= gameplay.x + gameplay.w && my >= gameplay.y && my <= gameplay.y + gameplay.h) {
      setActiveDrag({
        target: 'gameplay',
        type: 'move',
        startX: mx,
        startY: my,
        startBox: { ...gameplay },
      });
      return;
    }
  };
  // Presets
  const applyPreset = (camPos: 'top-right' | 'top-left' | 'bottom-left') => {
    const w = 0.28;
    const h = Number((w / AR_FACECAM).toFixed(4));
    let x = 0.68;
    let y = 0.05;

    if (camPos === 'top-left') {
      x = 0.04;
      y = 0.05;
    } else if (camPos === 'bottom-left') {
      x = 0.04;
      y = Number((1.0 - h - 0.05).toFixed(4));
    }

    setFacecam({ x, y, w, h });
  };

  const resetDefaults = () => {
    setFacecam({ x: 0.68, y: 0.05, w: 0.28, h: 0.1493 });
    setGameplay({ x: 0.25, y: 0.0, w: 0.5, h: 0.622 });
  };

  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4 space-y-4">
      <div className="flex items-center justify-between border-b border-zinc-800 pb-2">
        <div className="flex items-center space-x-2">
          <Gamepad2 className="h-4 w-4 text-emerald-400" />
          <span className="text-xs font-semibold text-white">9:16 Gaming Split Framing</span>
        </div>
        <div className="flex items-center space-x-1.5">
          <button
            type="button"
            onClick={() => applyPreset('top-right')}
            className="px-2 py-1 rounded bg-zinc-800 hover:bg-zinc-700 text-[11px] text-zinc-300 transition-colors"
          >
            Cam Top-Right
          </button>
          <button
            type="button"
            onClick={() => applyPreset('top-left')}
            className="px-2 py-1 rounded bg-zinc-800 hover:bg-zinc-700 text-[11px] text-zinc-300 transition-colors"
          >
            Cam Top-Left
          </button>
          <button
            type="button"
            onClick={() => applyPreset('bottom-left')}
            className="px-2 py-1 rounded bg-zinc-800 hover:bg-zinc-700 text-[11px] text-zinc-300 transition-colors"
          >
            Cam Bottom-Left
          </button>
          <button
            type="button"
            title="Reset"
            aria-label="Reset framing"
            onClick={resetDefaults}
            className="px-2 py-1 rounded bg-zinc-800 hover:bg-zinc-700 text-[11px] text-zinc-400 hover:text-zinc-200 transition-colors flex items-center space-x-1"
          >
            <RotateCcw className="h-3 w-3" />
            <span>Reset</span>
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-12 gap-4 items-start">
        {/* 16:9 Source Canvas */}
        <div className="md:col-span-8 flex flex-col space-y-1.5">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-medium text-zinc-400">
              Source 16:9 Frame (Drag boxes to frame camera & game)
            </span>
            <div className="flex items-center space-x-3 text-[10px] text-zinc-500">
              <span className="flex items-center space-x-1">
                <span className="inline-block w-2 h-2 rounded-full bg-blue-500" />
                <span>Facecam (1.875)</span>
              </span>
              <span className="flex items-center space-x-1">
                <span className="inline-block w-2 h-2 rounded-full bg-emerald-500" />
                <span>Gameplay (0.804)</span>
              </span>
            </div>
          </div>
          <canvas
            ref={sourceCanvasRef}
            width={640}
            height={360}
            onMouseDown={handleMouseDown}
            onMouseMove={updateCursor}
            onMouseUp={() => setActiveDrag(null)}
            onMouseLeave={() => setActiveDrag(null)}
            className="w-full aspect-video rounded-lg border border-zinc-800 cursor-move bg-zinc-950 shadow-inner"
          />
        </div>

        {/* 9:16 Live Stacked Preview */}
        <div className="md:col-span-4 flex flex-col space-y-1.5">
          <span className="text-[11px] font-medium text-zinc-400">
            Live 9:16 Preview (30% Cam / 70% Game)
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

export default GamingCropEditor;
