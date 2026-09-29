import React, { useState, useEffect, useCallback } from 'react';
import DOMPurify from 'dompurify';
import {
  Subtitles,
  Palette,
  Eye,
  Plus,
  Trash2,
  Save,
  FileCode,
  CheckCircle2,
  AlertCircle,
  Loader2,
  Video,
} from 'lucide-react';
import { subtitlesApi, previewApi } from '../api/client';
import type {
  SubtitleItem,
  SubtitleStylePreviewRequest,
} from '../api/types';

interface SubtitleEditorProps {
  currentProject?: string;
}

export const SubtitleEditor: React.FC<SubtitleEditorProps> = ({ currentProject }) => {
  // Input & Parse State
  const [rawContent, setRawContent] = useState('');
  const [projectName, setProjectName] = useState(currentProject || '');
  const [entries, setEntries] = useState<SubtitleItem[]>([
    { index: 1, start: 0.0, end: 2.5, text: 'Welcome to ViralCutter AI' },
    { index: 2, start: 2.6, end: 5.2, text: 'Generate high retention shorts automatically' },
  ]);
  const [detectedFormat, setDetectedFormat] = useState('srt');
  const [isParsing, setIsParsing] = useState(false);
  const [parseError, setParseError] = useState<string | null>(null);

  // Style State
  const [presets, setPresets] = useState<Record<string, Record<string, unknown>>>({});
  const [selectedPreset, setSelectedPreset] = useState<string>('Beast');
  const [font, setFont] = useState('Montserrat-ExtraBold');
  const [fontSize, setFontSize] = useState(32);
  const [color, setColor] = useState('#FFFFFF');
  const [highlightColor, setHighlightColor] = useState('#FFD700');
  const [outlineColor, setOutlineColor] = useState('#000000');
  const [outlineThickness, setOutlineThickness] = useState(3);
  const [shadowColor, setShadowColor] = useState('#000000');
  const [shadowSize, setShadowSize] = useState(2);
  const [bold, setBold] = useState(true);
  const [uppercase, setUppercase] = useState(true);
  const [mode, setMode] = useState<'highlight' | 'word_by_word' | 'no_highlight'>('highlight');

  // Preview & Save State
  const [previewHtml, setPreviewHtml] = useState<string>('');
  const [loadingPreview, setLoadingPreview] = useState(false);
  const [videoPreviewUrl, setVideoPreviewUrl] = useState<string | null>(null);
  const [loadingVideoPreview, setLoadingVideoPreview] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [isConverting, setIsConverting] = useState(false);
  const [saveSuccessMsg, setSaveSuccessMsg] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [convertedOutput, setConvertedOutput] = useState<string | null>(null);

  // Load Presets on Mount
  useEffect(() => {
    subtitlesApi
      .getPresets()
      .then((res) => {
        if (res?.presets) {
          setPresets(res.presets);
        }
      })
      .catch(() => {
        // Fallback default presets if backend call fails
        setPresets({
          Hormozi: { font: 'Montserrat-ExtraBold', size: 36, color: '#FFFFFF', highlight_color: '#00FF66' },
          Beast: { font: 'Montserrat-ExtraBold', size: 38, color: '#FFFFFF', highlight_color: '#FFD700' },
          Minimalist: { font: 'Roboto-Bold', size: 28, color: '#FFFFFF', highlight_color: '#38BDF8' },
        });
      });
  }, []);

  // Update Style Preview when styling changes
  const updatePreview = useCallback(async () => {
    setLoadingPreview(true);
    const req: SubtitleStylePreviewRequest = {
      font,
      size: fontSize,
      color,
      highlight_color: highlightColor,
      outline_color: outlineColor,
      outline_thickness: outlineThickness,
      shadow_color: shadowColor,
      shadow_size: shadowSize,
      bold,
      uppercase,
      mode,
    };

    try {
      const res = await subtitlesApi.previewStyle(req);
      setPreviewHtml(res.html);
    } catch {
      // Fallback simple preview
      setPreviewHtml(
        `<div style="display:flex;align-items:center;justify-content:center;height:120px;background:#18181b;color:${color};font-weight:${bold ? 'bold' : 'normal'};text-transform:${uppercase ? 'uppercase' : 'none'};"><span>PREVIEW</span></div>`
      );
    } finally {
      setLoadingPreview(false);
    }
  }, [
    font,
    fontSize,
    color,
    highlightColor,
    outlineColor,
    outlineThickness,
    shadowColor,
    shadowSize,
    bold,
    uppercase,
    mode,
  ]);

  useEffect(() => {
    const timer = setTimeout(() => {
      updatePreview();
    }, 200);
    return () => clearTimeout(timer);
  }, [updatePreview]);

  // Apply Selected Preset
  const handleApplyPreset = (presetName: string) => {
    setSelectedPreset(presetName);
    const p = presets[presetName];
    if (!p) return;
    if (typeof p.font === 'string') setFont(p.font);
    if (typeof p.size === 'number') setFontSize(p.size);
    if (typeof p.color === 'string') setColor(p.color);
    if (typeof p.highlight_color === 'string') setHighlightColor(p.highlight_color);
    if (typeof p.outline_color === 'string') setOutlineColor(p.outline_color);
    if (typeof p.outline_thickness === 'number') setOutlineThickness(p.outline_thickness);
    if (typeof p.shadow_color === 'string') setShadowColor(p.shadow_color);
    if (typeof p.shadow_size === 'number') setShadowSize(p.shadow_size);
    if (typeof p.bold === 'boolean') setBold(p.bold);
    if (typeof p.uppercase === 'boolean') setUppercase(p.uppercase);
    if (typeof p.mode === 'string') setMode(p.mode as any);
  };

  const handlePreviewOnVideo = async () => {
    setLoadingVideoPreview(true);
    try {
      const sampleText = entries[0]?.text || 'The quick brown fox jumps over the lazy dog';
      const res = await previewApi.previewSubtitleVideo({
        sample_text: sampleText,
        subtitle_config: {
          font,
          fontSize,
          color,
          highlightColor,
          outlineColor,
          outlineThickness,
          shadowColor,
          shadowSize,
          bold,
          uppercase,
          mode,
        },
        duration: 3.0,
      });
      setVideoPreviewUrl(res.preview_url);
    } catch {
      // Fallback
    } finally {
      setLoadingVideoPreview(false);
    }
  };

  // Parse Raw Subtitles
  const handleParse = async () => {
    if (!rawContent.trim()) return;
    setIsParsing(true);
    setParseError(null);
    try {
      const res = await subtitlesApi.parse({ content: rawContent });
      setEntries(res.entries);
      setDetectedFormat(res.format);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to parse subtitles';
      setParseError(msg);
    } finally {
      setIsParsing(false);
    }
  };

  // Cue Operations
  const handleCueChange = (index: number, field: keyof SubtitleItem, value: string | number) => {
    setEntries((prev) =>
      prev.map((cue, i) => {
        if (i === index) {
          return { ...cue, [field]: value };
        }
        return cue;
      })
    );
  };

  const handleAddCue = () => {
    const lastCue = entries[entries.length - 1];
    const newStart = lastCue ? Number((lastCue.end + 0.1).toFixed(2)) : 0.0;
    const newEnd = Number((newStart + 2.5).toFixed(2));
    setEntries((prev) => [
      ...prev,
      {
        index: prev.length + 1,
        start: newStart,
        end: newEnd,
        text: 'New subtitle cue text',
      },
    ]);
  };

  const handleDeleteCue = (index: number) => {
    setEntries((prev) => prev.filter((_, i) => i !== index));
  };

  // Persist Subtitles to Server
  const handleSave = async (format: 'srt' | 'vtt' | 'ass') => {
    setIsSaving(true);
    setSaveError(null);
    setSaveSuccessMsg(null);
    try {
      const res = await subtitlesApi.save({
        project_name: projectName.trim() || undefined,
        entries,
        format,
        filename: `subtitles.${format}`,
      });
      setSaveSuccessMsg(`Saved ${res.count} cues to ${res.file_path}`);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Save failed';
      setSaveError(msg);
    } finally {
      setIsSaving(false);
    }
  };

  // Format Conversion
  const handleConvert = async (targetFormat: 'srt' | 'vtt' | 'ass') => {
    setIsConverting(true);
    setSaveError(null);
    setConvertedOutput(null);
    try {
      const content = rawContent.trim()
        ? rawContent
        : entries.map((e) => `${e.index}\n${e.start} --> ${e.end}\n${e.text}\n`).join('\n');
      const res = await subtitlesApi.convert({
        content,
        target_format: targetFormat,
      });
      setConvertedOutput(res.content);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Conversion failed';
      setSaveError(msg);
    } finally {
      setIsConverting(false);
    }
  };

  // XSS-Safe Sanitization of HTML Preview
  const sanitizedHtml = DOMPurify.sanitize(previewHtml, {
    ALLOWED_TAGS: ['div', 'span', 'b', 'i', 'u', 's', 'p'],
    ALLOWED_ATTR: ['style', 'class'],
  });

  return (
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
      {/* Subtitle Cue List / Editor Panel */}
      <div className="lg:col-span-7 space-y-6">
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5 space-y-5">
          <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
            <div className="flex items-center space-x-2">
              <Subtitles className="h-5 w-5 text-red-400" />
              <h2 className="text-base font-semibold text-white">Subtitle Cue Editor</h2>
            </div>
            <span className="text-xs font-mono text-zinc-400 bg-zinc-800 px-2 py-0.5 rounded">
              {entries.length} cues ({detectedFormat.toUpperCase()})
            </span>
          </div>

          {/* Quick Import / Paste */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <label className="text-xs font-medium text-zinc-400">
                Paste Raw Subtitle Content (SRT / VTT / JSON):
              </label>
              <button
                type="button"
                onClick={handleParse}
                disabled={isParsing || !rawContent.trim()}
                className="flex items-center space-x-1 px-2.5 py-1 rounded bg-zinc-800 hover:bg-zinc-700 text-xs font-medium text-zinc-200 transition-colors disabled:opacity-50"
              >
                {isParsing ? <Loader2 className="h-3 w-3 animate-spin" /> : <FileCode className="h-3 w-3" />}
                <span>Parse</span>
              </button>
            </div>
            <textarea
              rows={3}
              placeholder="1&#10;00:00:01,000 --> 00:00:03,500&#10;Hello world"
              value={rawContent}
              onChange={(e) => setRawContent(e.target.value)}
              className="w-full rounded-lg bg-zinc-950 border border-zinc-800 p-2 text-xs font-mono text-zinc-100 placeholder-zinc-600 focus:border-red-500 focus:outline-none"
            />
            {parseError && <p className="text-xs text-red-400">{parseError}</p>}
          </div>

          {/* Cues Table */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium uppercase tracking-wider text-zinc-400">
                Cue Sequence
              </span>
              <button
                type="button"
                onClick={handleAddCue}
                className="flex items-center space-x-1 px-2.5 py-1 rounded bg-red-950/60 hover:bg-red-900/60 text-xs font-medium text-red-300 border border-red-800/60 transition-colors"
              >
                <Plus className="h-3.5 w-3.5" />
                <span>Add Cue</span>
              </button>
            </div>

            <div className="max-h-[360px] overflow-y-auto space-y-2 pr-1">
              {entries.map((cue, idx) => (
                <div
                  key={idx}
                  className="flex items-center space-x-2 bg-zinc-950/80 border border-zinc-800/80 rounded-lg p-2.5 hover:border-zinc-700 transition-colors"
                >
                  <span className="text-xs font-mono text-zinc-500 w-6 text-center">#{idx + 1}</span>

                  <div className="flex items-center space-x-1">
                    <input
                      type="number"
                      step="0.1"
                      min="0"
                      value={cue.start}
                      onChange={(e) =>
                        handleCueChange(idx, 'start', parseFloat(e.target.value) || 0)
                      }
                      className="w-16 rounded bg-zinc-900 border border-zinc-800 px-1.5 py-1 text-xs font-mono text-zinc-200"
                    />
                    <span className="text-zinc-600 text-xs">→</span>
                    <input
                      type="number"
                      step="0.1"
                      min="0"
                      value={cue.end}
                      onChange={(e) =>
                        handleCueChange(idx, 'end', parseFloat(e.target.value) || 0)
                      }
                      className="w-16 rounded bg-zinc-900 border border-zinc-800 px-1.5 py-1 text-xs font-mono text-zinc-200"
                    />
                  </div>

                  <input
                    type="text"
                    value={cue.text}
                    onChange={(e) => handleCueChange(idx, 'text', e.target.value)}
                    className="flex-1 rounded bg-zinc-900 border border-zinc-800 px-2 py-1 text-xs text-zinc-100 focus:border-red-500 focus:outline-none"
                  />

                  <button
                    type="button"
                    onClick={() => handleDeleteCue(idx)}
                    className="p-1 rounded text-zinc-500 hover:text-red-400 hover:bg-zinc-900 transition-colors"
                    title="Delete cue"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </div>
              ))}
            </div>
          </div>

          {/* Persist & Export Actions */}
          <div className="pt-3 border-t border-zinc-800 space-y-3">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              <input
                type="text"
                placeholder="Project name to save into"
                value={projectName}
                onChange={(e) => setProjectName(e.target.value)}
                className="rounded-lg bg-zinc-950 border border-zinc-800 px-3 py-1.5 text-xs text-zinc-100 placeholder-zinc-500 focus:border-red-500 focus:outline-none"
              />
              <div className="flex space-x-2">
                <button
                  type="button"
                  onClick={() => handleSave('srt')}
                  disabled={isSaving}
                  className="flex-1 flex items-center justify-center space-x-1.5 rounded-lg bg-zinc-800 hover:bg-zinc-700 px-3 py-1.5 text-xs font-medium text-zinc-200 transition-colors"
                >
                  <Save className="h-3.5 w-3.5 text-red-400" />
                  <span>Save SRT</span>
                </button>
                <button
                  type="button"
                  onClick={() => handleSave('vtt')}
                  disabled={isSaving}
                  className="flex-1 flex items-center justify-center space-x-1.5 rounded-lg bg-zinc-800 hover:bg-zinc-700 px-3 py-1.5 text-xs font-medium text-zinc-200 transition-colors"
                >
                  <Save className="h-3.5 w-3.5 text-blue-400" />
                  <span>Save VTT</span>
                </button>
              </div>
            </div>

            {saveSuccessMsg && (
              <div className="flex items-center space-x-2 text-xs text-emerald-400 bg-emerald-950/30 border border-emerald-800/40 p-2 rounded-lg">
                <CheckCircle2 className="h-4 w-4 shrink-0" />
                <span>{saveSuccessMsg}</span>
              </div>
            )}

            {saveError && (
              <div className="flex items-center space-x-2 text-xs text-red-400 bg-red-950/30 border border-red-800/40 p-2 rounded-lg">
                <AlertCircle className="h-4 w-4 shrink-0" />
                <span>{saveError}</span>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Style Presets & Safe HTML Preview Panel */}
      <div className="lg:col-span-5 space-y-6">
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5 space-y-5">
          <div className="flex items-center space-x-2 border-b border-zinc-800 pb-3">
            <Palette className="h-5 w-5 text-red-400" />
            <h2 className="text-base font-semibold text-white">Style Presets & Preview</h2>
          </div>

          {/* Preset Selector */}
          <div className="space-y-2">
            <label className="text-xs font-medium uppercase tracking-wider text-zinc-400">
              Style Preset
            </label>
            <div className="grid grid-cols-3 gap-2">
              {Object.keys(presets).map((name) => (
                <button
                  type="button"
                  key={name}
                  onClick={() => handleApplyPreset(name)}
                  className={`rounded-lg py-1.5 px-2 text-xs font-medium border text-center transition-colors truncate ${
                    selectedPreset === name
                      ? 'bg-red-950/60 border-red-600/70 text-red-200'
                      : 'bg-zinc-800/60 border-zinc-700/60 text-zinc-400 hover:bg-zinc-800 hover:text-zinc-200'
                  }`}
                >
                  {name}
                </button>
              ))}
            </div>
          </div>

          {/* Custom Controls */}
          <div className="space-y-3 pt-2 border-t border-zinc-800">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs text-zinc-400 block mb-1">Font Family</label>
                <select
                  value={font}
                  onChange={(e) => setFont(e.target.value)}
                  className="w-full rounded bg-zinc-950 border border-zinc-800 px-2 py-1.5 text-xs text-zinc-200"
                >
                  <option value="Montserrat-ExtraBold">Montserrat-ExtraBold</option>
                  <option value="Roboto-Bold">Roboto-Bold</option>
                  <option value="Poppins-ExtraBold">Poppins-ExtraBold</option>
                  <option value="Barlow-SemiBold">Barlow-SemiBold</option>
                  <option value="Anton-Regular">Anton-Regular</option>
                </select>
              </div>

              <div>
                <label className="text-xs text-zinc-400 block mb-1">Font Size: {fontSize}px</label>
                <input
                  type="range"
                  min="20"
                  max="64"
                  value={fontSize}
                  onChange={(e) => setFontSize(parseInt(e.target.value))}
                  className="w-full"
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs text-zinc-400 block mb-1">Primary Color</label>
                <div className="flex items-center space-x-2">
                  <input
                    type="color"
                    value={color}
                    onChange={(e) => setColor(e.target.value)}
                    className="h-7 w-7 rounded bg-transparent cursor-pointer border border-zinc-700"
                  />
                  <span className="text-xs font-mono text-zinc-300">{color}</span>
                </div>
              </div>

              <div>
                <label className="text-xs text-zinc-400 block mb-1">Highlight Word</label>
                <div className="flex items-center space-x-2">
                  <input
                    type="color"
                    value={highlightColor}
                    onChange={(e) => setHighlightColor(e.target.value)}
                    className="h-7 w-7 rounded bg-transparent cursor-pointer border border-zinc-700"
                  />
                  <span className="text-xs font-mono text-zinc-300">{highlightColor}</span>
                </div>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs text-zinc-400 block mb-1">Outline Color</label>
                <div className="flex items-center space-x-2">
                  <input
                    type="color"
                    value={outlineColor}
                    onChange={(e) => setOutlineColor(e.target.value)}
                    className="h-7 w-7 rounded bg-transparent cursor-pointer border border-zinc-700"
                  />
                  <input
                    type="number"
                    min="0"
                    max="10"
                    value={outlineThickness}
                    onChange={(e) => setOutlineThickness(parseInt(e.target.value) || 0)}
                    className="w-12 rounded bg-zinc-950 border border-zinc-800 px-1.5 py-1 text-xs font-mono text-zinc-200"
                  />
                </div>
              </div>

              <div>
                <label className="text-xs text-zinc-400 block mb-1">Shadow Offset</label>
                <div className="flex items-center space-x-2">
                  <input
                    type="color"
                    value={shadowColor}
                    onChange={(e) => setShadowColor(e.target.value)}
                    className="h-7 w-7 rounded bg-transparent cursor-pointer border border-zinc-700"
                  />
                  <input
                    type="number"
                    min="0"
                    max="10"
                    value={shadowSize}
                    onChange={(e) => setShadowSize(parseInt(e.target.value) || 0)}
                    className="w-12 rounded bg-zinc-950 border border-zinc-800 px-1.5 py-1 text-xs font-mono text-zinc-200"
                  />
                </div>
              </div>
            </div>

            <div className="flex items-center space-x-4 pt-1">
              <label className="flex items-center space-x-1.5 text-xs text-zinc-300 cursor-pointer">
                <input
                  type="checkbox"
                  checked={bold}
                  onChange={(e) => setBold(e.target.checked)}
                  className="rounded border-zinc-700 bg-zinc-950 text-red-600"
                />
                <span>Bold</span>
              </label>

              <label className="flex items-center space-x-1.5 text-xs text-zinc-300 cursor-pointer">
                <input
                  type="checkbox"
                  checked={uppercase}
                  onChange={(e) => setUppercase(e.target.checked)}
                  className="rounded border-zinc-700 bg-zinc-950 text-red-600"
                />
                <span>Uppercase</span>
              </label>

              <div className="flex-1 text-right">
                <select
                  value={mode}
                  onChange={(e) => setMode(e.target.value as any)}
                  className="rounded bg-zinc-950 border border-zinc-800 px-2 py-1 text-xs text-zinc-200"
                >
                  <option value="highlight">Highlight Mode</option>
                  <option value="word_by_word">Word by Word</option>
                  <option value="no_highlight">Plain</option>
                </select>
              </div>
            </div>
          </div>

          {/* HTML Preview (XSS Sanitize Protected) & Video Preview */}
          <div className="space-y-2 pt-2 border-t border-zinc-800">
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-1.5 text-xs font-medium uppercase tracking-wider text-zinc-400">
                <Eye className="h-3.5 w-3.5 text-red-400" />
                <span>Live Rendering Preview</span>
              </div>
              <div className="flex items-center space-x-2">
                <button
                  type="button"
                  onClick={handlePreviewOnVideo}
                  disabled={loadingVideoPreview}
                  className="flex items-center space-x-1 px-2 py-0.5 rounded bg-zinc-800 hover:bg-zinc-700 text-zinc-300 text-[11px] border border-zinc-700 disabled:opacity-50 transition-colors"
                >
                  {loadingVideoPreview ? (
                    <Loader2 className="h-3 w-3 animate-spin" />
                  ) : (
                    <Video className="h-3 w-3 text-red-400" />
                  )}
                  <span>Preview on Video</span>
                </button>
                {loadingPreview && <Loader2 className="h-3.5 w-3.5 animate-spin text-zinc-500" />}
              </div>
            </div>

            {/* Video Preview Player if generated */}
            {videoPreviewUrl && (
              <div className="bg-zinc-950 p-3 rounded-xl border border-zinc-800 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-[11px] font-semibold text-zinc-300">Video Sample (3s Loop)</span>
                  <button
                    type="button"
                    onClick={() => setVideoPreviewUrl(null)}
                    className="text-[11px] text-zinc-500 hover:text-zinc-300"
                  >
                    Hide Video
                  </button>
                </div>
                <div className="w-full max-w-[180px] mx-auto aspect-[9/16] bg-black rounded-lg overflow-hidden shadow-lg border border-zinc-800 flex items-center justify-center">
                  <video
                    src={videoPreviewUrl}
                    autoPlay
                    loop
                    muted
                    playsInline
                    controls
                    className="w-full h-full object-contain"
                  />
                </div>
              </div>
            )}

            {/* Security: sanitizedHtml is strictly sanitized via DOMPurify with whitelisted tags and attributes to prevent XSS */}
            <div
              className="rounded-xl border border-zinc-800 overflow-hidden shadow-inner p-1 bg-zinc-950 flex items-center justify-center min-h-[140px]"
              dangerouslySetInnerHTML={{ __html: sanitizedHtml }}
            />
          </div>

          {/* Quick Format Conversion */}
          <div className="pt-2 border-t border-zinc-800 space-y-2">
            <span className="text-xs font-medium uppercase tracking-wider text-zinc-400 block">
              Format Converter
            </span>
            <div className="flex space-x-2">
              <button
                type="button"
                onClick={() => handleConvert('vtt')}
                disabled={isConverting}
                className="flex-1 py-1.5 rounded bg-zinc-800 hover:bg-zinc-700 text-xs font-medium text-zinc-300 transition-colors"
              >
                Convert to VTT
              </button>
              <button
                type="button"
                onClick={() => handleConvert('ass')}
                disabled={isConverting}
                className="flex-1 py-1.5 rounded bg-zinc-800 hover:bg-zinc-700 text-xs font-medium text-zinc-300 transition-colors"
              >
                Convert to ASS
              </button>
              <button
                type="button"
                onClick={() => handleConvert('srt')}
                disabled={isConverting}
                className="flex-1 py-1.5 rounded bg-zinc-800 hover:bg-zinc-700 text-xs font-medium text-zinc-300 transition-colors"
              >
                Convert to SRT
              </button>
            </div>

            {convertedOutput && (
              <div className="space-y-1">
                <textarea
                  readOnly
                  rows={4}
                  value={convertedOutput}
                  className="w-full rounded bg-zinc-950 border border-zinc-800 p-2 text-xs font-mono text-zinc-400"
                />
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
