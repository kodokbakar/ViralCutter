import React, { useRef, useEffect, useState, useCallback } from 'react';
import { Gamepad2, RotateCcw, Film, Upload, Loader2, Layers, Crosshair } from 'lucide-react';
import type { SampleFrameItem, GamingLayout } from '../api/types';

export interface GamingCropEditorProps {
  imageSrc?: string;
  videoSrc?: string;
  sampleFrames?: SampleFrameItem[];
  activeSampleIndex?: number;
  onSelectSampleFrame?: (index: number) => void;
  isLoadingSamples?: boolean;
  facecamCrop: string;
  gameplayCrop: string;
  layout?: GamingLayout;
  onLayoutChange?: (layout: GamingLayout) => void;
  killfeedCrop?: string;
  onKillfeedChange?: (killfeedCrop: string) => void;
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
export const AR_KILLFEED = 2.0;

export const GAMING_LAYOUT_AR: Record<GamingLayout, { arFacecam: number; arGameplay: number }> = {
  split_30_70: { arFacecam: 1080 / 576, arGameplay: 1080 / 1344 },
  split_40_60: { arFacecam: 1080 / 768, arGameplay: 1080 / 1152 },
  floating_pip: { arFacecam: 360 / 270, arGameplay: 1080 / 1920 },
  blurred_bg: { arFacecam: 1080 / 576, arGameplay: 1080 / 608 },
};

export const GAMING_LAYOUT_LABELS: Record<GamingLayout, string> = {
  split_30_70: '30/70 Split',
  split_40_60: '40/60 Split',
  floating_pip: 'Floating PiP',
  blurred_bg: 'Blurred BG',
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
    if (Math.abs(px - hx) <= hitRadius && Math.abs(py - hy) <= hitRadius) {
      return type;
    }
  }
  return null;
}

export const GamingCropEditor: React.FC<GamingCropEditorProps> = ({
  imageSrc,
  videoSrc,
  sampleFrames,
  activeSampleIndex,
  onSelectSampleFrame,
  isLoadingSamples,
  facecamCrop,
  gameplayCrop,
  layout = 'split_30_70',
  onLayoutChange,
  killfeedCrop,
  onKillfeedChange,
  onChange,
}) => {
  const currentLayout: GamingLayout = layout || 'split_30_70';
  const arConfig = GAMING_LAYOUT_AR[currentLayout] || GAMING_LAYOUT_AR.split_30_70;

  const sourceCanvasRef = useRef<HTMLCanvasElement>(null);
  const previewCanvasRef = useRef<HTMLCanvasElement>(null);
  const imageRef = useRef<HTMLImageElement | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [selectedFrameIdx, setSelectedFrameIdx] = useState<number>(() => activeSampleIndex ?? 0);
  const [customImageUri, setCustomImageUri] = useState<string | null>(null);

  useEffect(() => {
    if (activeSampleIndex !== undefined && activeSampleIndex >= 0) {
      setSelectedFrameIdx(activeSampleIndex);
    }
  }, [activeSampleIndex]);

  const [facecam, setFacecam] = useState<BoxRect>(() =>
    parseBox(facecamCrop, { x: 0.68, y: 0.05, w: 0.28, h: 0.1493 })
  );
  const [gameplay, setGameplay] = useState<BoxRect>(() =>
    parseBox(gameplayCrop, { x: 0.25, y: 0.0, w: 0.5, h: 0.622 })
  );
  const [killfeed, setKillfeed] = useState<BoxRect>(() =>
    parseBox(killfeedCrop || '', { x: 0.70, y: 0.05, w: 0.26, h: 0.13 })
  );
  const [killfeedEnabled, setKillfeedEnabled] = useState<boolean>(() =>
    Boolean(killfeedCrop && killfeedCrop.trim() && killfeedCrop.trim().toLowerCase() !== 'none')
  );

  const [activeDrag, setActiveDrag] = useState<{
    target: 'facecam' | 'gameplay' | 'killfeed';
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

  useEffect(() => {
    if (killfeedCrop !== undefined) {
      const enabled = Boolean(killfeedCrop && killfeedCrop.trim() && killfeedCrop.trim().toLowerCase() !== 'none');
      setKillfeedEnabled(enabled);
      if (enabled) {
        setKillfeed(parseBox(killfeedCrop, { x: 0.70, y: 0.05, w: 0.26, h: 0.13 }));
      }
    }
  }, [killfeedCrop]);

  const handleToggleKillfeed = (enabled: boolean) => {
    setKillfeedEnabled(enabled);
    if (enabled) {
      onKillfeedChange?.(formatBox(killfeed));
    } else {
      onKillfeedChange?.('');
    }
  };

  const handleSelectLayout = (newLayout: GamingLayout) => {
    onLayoutChange?.(newLayout);
    const newAr = GAMING_LAYOUT_AR[newLayout] || GAMING_LAYOUT_AR.split_30_70;
    setFacecam((prev) => {
      const newH = Math.min(1 - prev.y, Number((prev.w / newAr.arFacecam).toFixed(4)));
      return { ...prev, h: newH };
    });
    setGameplay((prev) => {
      const newH = Math.min(1 - prev.y, Number((prev.w / newAr.arGameplay).toFixed(4)));
      return { ...prev, h: newH };
    });
  };

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
      ctx.fillRect(bx, labelY, Math.min(bw, 130), 18);
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

    const gameLabel =
      currentLayout === 'split_40_60'
        ? 'Gameplay (60%)'
        : currentLayout === 'floating_pip'
        ? 'Gameplay (Full)'
        : currentLayout === 'blurred_bg'
        ? 'Gameplay (Center)'
        : 'Gameplay (70%)';
    const camLabel =
      currentLayout === 'split_40_60'
        ? 'Facecam (40%)'
        : currentLayout === 'floating_pip'
        ? 'Facecam (PiP)'
        : 'Facecam (30%)';

    renderBox(gameplay, '#10b981', gameLabel);
    renderBox(facecam, '#3b82f6', camLabel);
    if (killfeedEnabled) {
      renderBox(killfeed, '#f59e0b', 'Killfeed Overlay');
    }
  }, [facecam, gameplay, killfeed, killfeedEnabled, currentLayout]);

  // Draw 9:16 Split Preview Canvas
  const drawPreview = useCallback(() => {
    const canvas = previewCanvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    ctx.clearRect(0, 0, canvas.width, canvas.height);

    const targetW = canvas.width;
    const targetH = canvas.height;
    let camH = targetH * 0.3;
    let gameH = targetH * 0.7;
    if (currentLayout === 'split_40_60') {
      camH = targetH * 0.4;
      gameH = targetH * 0.6;
    }

    const img = imageRef.current;
    if (img && img.naturalWidth && img.naturalHeight) {
      const fx = facecam.x * img.naturalWidth;
      const fy = facecam.y * img.naturalHeight;
      const fw = facecam.w * img.naturalWidth;
      const fh = facecam.h * img.naturalHeight;

      const gx = gameplay.x * img.naturalWidth;
      const gy = gameplay.y * img.naturalHeight;
      const gw = gameplay.w * img.naturalWidth;
      const gh = gameplay.h * img.naturalHeight;

      if (currentLayout === 'floating_pip') {
        // Full gameplay background
        ctx.drawImage(img, gx, gy, gw, gh, 0, 0, targetW, targetH);
        // Floating facecam PiP top-left
        const pipW = targetW * 0.36;
        const pipH = pipW / (360 / 270);
        ctx.lineWidth = 2;
        ctx.strokeStyle = '#ffffff';
        ctx.strokeRect(10, 12, pipW, pipH);
        ctx.drawImage(img, fx, fy, fw, fh, 10, 12, pipW, pipH);
      } else if (currentLayout === 'blurred_bg') {
        // Blurred background simulated with gameplay frame
        ctx.save();
        ctx.filter = 'blur(4px)';
        ctx.drawImage(img, gx, gy, gw, gh, 0, 0, targetW, targetH);
        ctx.restore();
        // Facecam top (30%)
        ctx.drawImage(img, fx, fy, fw, fh, 0, 0, targetW, targetH * 0.3);
        // Gameplay middle (32%)
        const midY = targetH * 0.33;
        const midH = targetH * 0.32;
        ctx.drawImage(img, gx, gy, gw, gh, 0, midY, targetW, midH);
      } else {
        // split_30_70 or split_40_60
        ctx.drawImage(img, fx, fy, fw, fh, 0, 0, targetW, camH);
        ctx.drawImage(img, gx, gy, gw, gh, 0, camH, targetW, gameH);

        // Divider line
        ctx.lineWidth = 2;
        ctx.strokeStyle = '#09090b';
        ctx.beginPath();
        ctx.moveTo(0, camH);
        ctx.lineTo(targetW, camH);
        ctx.stroke();
      }

      // Draw killfeed overlay if enabled
      if (killfeedEnabled) {
        const kx = killfeed.x * img.naturalWidth;
        const ky = killfeed.y * img.naturalHeight;
        const kw = killfeed.w * img.naturalWidth;
        const kh = killfeed.h * img.naturalHeight;
        const kfW = targetW * 0.34;
        const kfH = Math.max(16, kfW * (killfeed.h / Math.max(0.01, killfeed.w)));
        const kfX = targetW - kfW - 6;
        const kfY = 6;
        ctx.drawImage(img, kx, ky, kw, kh, kfX, kfY, kfW, kfH);
        ctx.lineWidth = 1.5;
        ctx.strokeStyle = '#ffffff';
        ctx.strokeRect(kfX, kfY, kfW, kfH);
      }
    } else {
      ctx.fillStyle = '#2563eb30';
      ctx.fillRect(0, 0, targetW, camH);
      ctx.fillStyle = '#05966930';
      ctx.fillRect(0, camH, targetW, gameH);

      ctx.fillStyle = '#93c5fd';
      ctx.font = '10px sans-serif';
      ctx.fillText(`Facecam (${GAMING_LAYOUT_LABELS[currentLayout]})`, 10, camH / 2 + 3);

      ctx.fillStyle = '#6ee7b7';
      ctx.font = '10px sans-serif';
      ctx.fillText('Gameplay', 10, camH + gameH / 2 + 3);

      if (killfeedEnabled) {
        ctx.fillStyle = '#f59e0b40';
        ctx.fillRect(targetW - 60, 6, 54, 20);
        ctx.strokeStyle = '#f59e0b';
        ctx.strokeRect(targetW - 60, 6, 54, 20);
        ctx.fillStyle = '#fef3c7';
        ctx.font = '8px sans-serif';
        ctx.fillText('Killfeed', targetW - 55, 18);
      }
    }
  }, [facecam, gameplay, killfeed, killfeedEnabled, currentLayout]);

  // Determine active frame source
  const activeSampleFrame =
    sampleFrames && sampleFrames.length > 0
      ? sampleFrames[selectedFrameIdx] || sampleFrames[0]
      : null;

  const activeSrc =
    customImageUri ||
    (activeSampleFrame ? activeSampleFrame.data_uri || activeSampleFrame.path : imageSrc || videoSrc);

  // Load and cache image
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
        const updated: BoxRect = { ...b, x: nextX, y: nextY };
        if (activeDrag.target === 'facecam') {
          setFacecam(updated);
        } else if (activeDrag.target === 'gameplay') {
          setGameplay(updated);
        } else if (activeDrag.target === 'killfeed') {
          setKillfeed(updated);
          onKillfeedChange?.(formatBox(updated));
        }
        return;
      }

      // Corner resize with aspect ratio lock
      const ar =
        activeDrag.target === 'facecam'
          ? arConfig.arFacecam
          : activeDrag.target === 'gameplay'
          ? arConfig.arGameplay
          : AR_KILLFEED;
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
      } else if (activeDrag.target === 'gameplay') {
        setGameplay(updated);
      } else if (activeDrag.target === 'killfeed') {
        setKillfeed(updated);
        onKillfeedChange?.(formatBox(updated));
      }
    },
    [activeDrag, arConfig, onKillfeedChange]
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

    const kfHandle = killfeedEnabled ? getHandleAt(mx, my, killfeed, canvas.width, canvas.height) : null;
    const fcHandle = getHandleAt(mx, my, facecam, canvas.width, canvas.height);
    const gpHandle = getHandleAt(mx, my, gameplay, canvas.width, canvas.height);
    const handle = kfHandle || fcHandle || gpHandle;

    if (handle === 'nw' || handle === 'se') {
      canvas.style.cursor = 'nwse-resize';
    } else if (handle === 'ne' || handle === 'sw') {
      canvas.style.cursor = 'nesw-resize';
    } else if (
      (killfeedEnabled && mx >= killfeed.x && mx <= killfeed.x + killfeed.w && my >= killfeed.y && my <= killfeed.y + killfeed.h) ||
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

    // Check Killfeed handles first if enabled
    if (killfeedEnabled) {
      const kfHandle = getHandleAt(mx, my, killfeed, canvas.width, canvas.height);
      if (kfHandle) {
        setActiveDrag({
          target: 'killfeed',
          type: kfHandle,
          startX: mx,
          startY: my,
          startBox: { ...killfeed },
        });
        return;
      }
    }

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

    // Check inside Killfeed box (move)
    if (killfeedEnabled && mx >= killfeed.x && mx <= killfeed.x + killfeed.w && my >= killfeed.y && my <= killfeed.y + killfeed.h) {
      setActiveDrag({
        target: 'killfeed',
        type: 'move',
        startX: mx,
        startY: my,
        startBox: { ...killfeed },
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
    const h = Number((w / arConfig.arFacecam).toFixed(4));
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
    const defaultCamAr = arConfig.arFacecam;
    const defaultGameAr = arConfig.arGameplay;
    const fcW = 0.28;
    const fcH = Number((fcW / defaultCamAr).toFixed(4));
    const gpW = 0.50;
    const gpH = Number((gpW / defaultGameAr).toFixed(4));
    setFacecam({ x: 0.68, y: 0.05, w: fcW, h: Math.min(1.0 - 0.05, fcH) });
    setGameplay({ x: 0.25, y: 0.0, w: gpW, h: Math.min(1.0, gpH) });
    setKillfeed({ x: 0.70, y: 0.05, w: 0.26, h: 0.13 });
    if (killfeedEnabled) {
      onKillfeedChange?.('0.7000,0.0500,0.2600,0.1300');
    }
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
            onClick={() => setGameplay((prev) => ({ ...prev, x: (1.0 - prev.w) / 2 }))}
            className="px-2 py-1 rounded bg-zinc-800 hover:bg-zinc-700 text-[11px] text-zinc-300 transition-colors"
          >
            Center Action
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

      {/* Gaming Layout & Killfeed Selector Toolbar */}
      <div className="flex flex-wrap items-center justify-between gap-2 p-2 bg-zinc-950/60 rounded-lg border border-zinc-800/80">
        <div className="flex items-center space-x-1.5 overflow-x-auto">
          <Layers className="h-3.5 w-3.5 text-zinc-400 shrink-0" />
          <span className="text-[11px] font-medium text-zinc-400">Layout:</span>
          {(['split_30_70', 'split_40_60', 'floating_pip', 'blurred_bg'] as GamingLayout[]).map((lay) => (
            <button
              key={lay}
              type="button"
              onClick={() => handleSelectLayout(lay)}
              className={`px-2 py-1 rounded text-[11px] font-medium transition-all ${
                currentLayout === lay
                  ? 'bg-emerald-600 text-white shadow-sm'
                  : 'bg-zinc-800 text-zinc-300 hover:bg-zinc-700'
              }`}
            >
              {GAMING_LAYOUT_LABELS[lay]}
            </button>
          ))}
        </div>

        <div className="flex items-center space-x-2">
          <label className="flex items-center space-x-1.5 cursor-pointer text-[11px] text-zinc-300 select-none">
            <input
              type="checkbox"
              checked={killfeedEnabled}
              onChange={(e) => handleToggleKillfeed(e.target.checked)}
              className="rounded bg-zinc-800 border-zinc-700 text-amber-500 focus:ring-0 focus:ring-offset-0"
            />
            <Crosshair className="h-3.5 w-3.5 text-amber-400" />
            <span>Killfeed Box</span>
          </label>
        </div>
      </div>
      {/* 3 Source Sample Frames Selector Toolbar */}
      <div className="flex flex-wrap items-center justify-between gap-2 p-2.5 bg-zinc-950/80 rounded-lg border border-zinc-800/80">
        <div className="flex items-center space-x-2">
          <span className="text-[11px] font-medium text-zinc-300 flex items-center space-x-1.5 shrink-0">
            <Film className="h-3.5 w-3.5 text-emerald-400" />
            <span>Source Frames:</span>
          </span>

          {isLoadingSamples ? (
            <span className="text-[11px] text-zinc-400 flex items-center space-x-1.5 font-mono">
              <Loader2 className="h-3 w-3 animate-spin text-emerald-400" />
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
                      ? 'bg-emerald-950/80 text-emerald-300 border-emerald-500/80 ring-1 ring-emerald-500/30 font-semibold'
                      : 'bg-zinc-900 text-zinc-400 border-zinc-800 hover:text-zinc-200 hover:border-zinc-700'
                  }`}
                >
                  <span
                    className={`w-1.5 h-1.5 rounded-full ${
                      customImageUri === null && selectedFrameIdx === idx
                        ? 'bg-emerald-400 animate-pulse'
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
              Source 16:9 Frame (Drag boxes to frame camera & game)
            </span>
            <div className="flex items-center space-x-3 text-[10px] text-zinc-500">
              <span className="flex items-center space-x-1">
                <span className="inline-block w-2 h-2 rounded-full bg-blue-500" />
                <span>Facecam ({arConfig.arFacecam.toFixed(2)})</span>
              </span>
              <span className="flex items-center space-x-1">
                <span className="inline-block w-2 h-2 rounded-full bg-emerald-500" />
                <span>Gameplay ({arConfig.arGameplay.toFixed(2)})</span>
              </span>
              {killfeedEnabled && (
                <span className="flex items-center space-x-1">
                  <span className="inline-block w-2 h-2 rounded-full bg-amber-500" />
                  <span>Killfeed</span>
                </span>
              )}
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

        {/* 9:16 Live Stacked Preview */}
        <div className="md:col-span-4 flex flex-col space-y-1.5">
          <span className="text-[11px] font-medium text-zinc-400">
            Live 9:16 Preview ({GAMING_LAYOUT_LABELS[currentLayout] || currentLayout})
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
