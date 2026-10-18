import React, { useState, useEffect } from 'react';
import {
  Sparkles,
  Play,
  Loader2,
  Sliders,
  CheckCircle2,
  AlertCircle,
  Video,
  FileCode,
  Layers,
} from 'lucide-react';
import { brollApi } from '../api/client';
import type { BrollTemplate } from '../api/types';

const DEFAULT_TEMPLATES: BrollTemplate[] = [
  {
    id: 'sleek_stat_badge',
    name: 'Sleek Metric Island',
    description: 'Minimalist Dynamic Island glass capsule with glowing LED and metric counter (Upper-Third)',
    default_duration: 3.5,
    sample_data: {
      target_number: '87',
      prefix: '+',
      suffix: '%',
      label: 'Lonjakan Retensi Penonton',
      accent_color: '#00F0FF',
    },
  },
  {
    id: 'sleek_quote_card',
    name: 'Sleek Quote Island',
    description: 'Compact upper-third translucent glass card with glowing accent line and speaker attribution',
    default_duration: 4.0,
    sample_data: {
      quote: 'Bila pembukaan video tidak memikat dalam 2 detik, penonton pergi selamanya.',
      author: 'Dr. Sarah Adams',
      title: 'Media Psychologist',
    },
  },
  {
    id: 'sleek_keyword_pill',
    name: 'Sleek Keyword Pill',
    description: 'Dynamic Island horizontal capsule with blinking status LED and punchy keywords',
    default_duration: 3.5,
    sample_data: {
      tag: 'KEY INSIGHT',
      line_1: 'JANGAN PERNAH',
      line_2: 'BUANG 3 DETIK',
      line_3: 'PERTAMA ANDA',
      subtext: 'Algoritma TikTok dan Reels mengukur 70% retensi dari detik pembuka.',
    },
  },
  {
    id: 'sleek_step_list',
    name: 'Sleek Step List',
    description: 'Minimalist upper-third glass board with sleek numbered gradient step rows',
    default_duration: 4.5,
    sample_data: {
      headline: '3 KUNCI VIRAL',
      points: ['Hook 3 detik pertama', 'Pacing tanpa dead-air', 'Punchline memuaskan'],
    },
  },
  {
    id: 'stat_counter',
    name: 'Vox Metric Punch',
    description: 'Kinetic number counter capsule in upper-third safe-zone',
    default_duration: 3.5,
    sample_data: {
      target_number: '87',
      prefix: '+',
      suffix: '%',
      label: 'Lonjakan Retensi 3 Detik Pertama',
      accent_color: '#FF5A36',
    },
  },
  {
    id: 'quote_card',
    name: 'Vox Editorial Pull-Quote',
    description: 'Newsprint paper cutout card with speaker stamp',
    default_duration: 4.0,
    sample_data: {
      quote: 'Bila pembukaan video tidak memikat dalam 2 detik, penonton pergi selamanya.',
      author: 'Dr. Sarah Adams',
      title: 'Media Psychologist',
    },
  },
  {
    id: 'point_highlight',
    name: 'Vox Collage Sticky Steps',
    description: 'Numbered paper index cards with stop-motion timing',
    default_duration: 4.5,
    sample_data: {
      headline: '3 KUNCI VIRAL',
      points: ['Hook 3 detik pertama', 'Pacing tanpa dead-air', 'Punchline memuaskan'],
    },
  },
  {
    id: 'vox_versus_split',
    name: 'Vox Versus / Split Screen',
    description: 'Full-screen dual-tone split comparison (Navy vs Coral) with rotating VS stamp',
    default_duration: 4.0,
    sample_data: {
      tag_a: 'CARA LAMA',
      title_a: 'MANUAL EDIT',
      desc_a: 'Butuh 4 jam per video pendek, rawan lelah dan tidak konsisten.',
      tag_b: 'CARA BARU',
      title_b: 'VIRALCUTTER AI',
      desc_b: 'Selesai dalam 2 menit otomatis dengan 3-part storytelling retention.',
    },
  },
  {
    id: 'vox_headline_punch',
    name: 'Vox Kinetic Typographic Hook',
    description: 'Full-screen 9:16 kinetic text slam with yellow highlighter block and breaking badge',
    default_duration: 3.5,
    sample_data: {
      tag: 'BREAKING INSIGHT',
      line_1: 'JANGAN PERNAH',
      line_2: 'BUANG 3 DETIK',
      line_3: 'PERTAMA ANDA',
      subtext: 'Algoritma TikTok dan Reels mengukur 70% retensi dari detik pembuka.',
    },
  },
  {
    id: 'vox_explainer_def',
    name: 'Vox Glossary / Blueprint Def',
    description: 'Technical dictionary breakdown with phonetic guide and highlighter sweep',
    default_duration: 4.0,
    sample_data: {
      term: 'HOOK RETENTION',
      phonetic: '/hʊk rɪˈten.ʃən/',
      pos: 'noun',
      definition: 'Teknik psikologi visual untuk menghentikan jempol penonton dari scrolling.',
      context_note: 'Faktor nomor 1 penentu viralitas di YouTube Shorts dan Reels.',
    },
  },
  {
    id: 'vox_bar_chart',
    name: 'Vox Editorial Data Graph',
    description: 'Animated comparison bar graph with diagonal textures and counter ticker',
    default_duration: 4.0,
    sample_data: {
      chart_title: 'PERBANDINGAN RETENSI AUDIENS',
      source: 'DATA ANALYTICS 2026',
      bars: [
        { label: 'Standard', value: '24%', height: 32, accent: false },
        { label: 'Jump-Cut', value: '58%', height: 65, accent: false },
        { label: 'ViralCutter', value: '89%', height: 95, accent: true },
      ],
    },
  },
];

export const BrollTab: React.FC = () => {
  const [templates, setTemplates] = useState<BrollTemplate[]>(DEFAULT_TEMPLATES);
  const [selectedTemplateId, setSelectedTemplateId] = useState<string>('stat_counter');
  const [templateData, setTemplateData] = useState<Record<string, unknown>>(
    DEFAULT_TEMPLATES[0].sample_data || {}
  );
  const [duration, setDuration] = useState<number>(3.5);
  const [isLoadingTemplates, setIsLoadingTemplates] = useState<boolean>(false);
  const [isRendering, setIsRendering] = useState<boolean>(false);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [statusMessage, setStatusMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  // Fetch templates from API
  useEffect(() => {
    let active = true;
    const fetchTemplates = async () => {
      setIsLoadingTemplates(true);
      try {
        const fetched = await brollApi.getTemplates();
        if (active && fetched && fetched.length > 0) {
          setTemplates(fetched);
          const current = fetched.find((t) => t.id === selectedTemplateId) || fetched[0];
          setSelectedTemplateId(current.id);
          setDuration(current.default_duration || 3.5);
          setTemplateData(current.sample_data || {});
        }
      } catch {
        // Keep default templates on error
      } finally {
        if (active) setIsLoadingTemplates(false);
      }
    };

    fetchTemplates();
    return () => {
      active = false;
    };
  }, []);

  const selectedTemplate =
    templates.find((t) => t.id === selectedTemplateId) || templates[0];

  const handleSelectTemplate = (t: BrollTemplate) => {
    setSelectedTemplateId(t.id);
    setDuration(t.default_duration || 3.5);
    setTemplateData(t.sample_data ? JSON.parse(JSON.stringify(t.sample_data)) : {});
    setStatusMessage(null);
  };

  const handleDataChange = (key: string, value: unknown) => {
    setTemplateData((prev) => ({
      ...prev,
      [key]: value,
    }));
  };

  const handleTestRender = async () => {
    if (!selectedTemplate) return;
    setIsRendering(true);
    setStatusMessage(null);

    try {
      const dataPayload = { ...templateData };
      if (Array.isArray(dataPayload.points)) {
        dataPayload.points = (dataPayload.points as unknown[])
          .map((p) => String(p).trim())
          .filter((p) => p.length > 0);
      } else if (typeof dataPayload.points === 'string') {
        dataPayload.points = dataPayload.points
          .split('\n')
          .map((p) => p.trim())
          .filter((p) => p.length > 0);
      }

      const res = await brollApi.preview({
        template_id: selectedTemplate.id,
        duration,
        data: dataPayload,
      });
      setPreviewUrl(res.preview_url);
      setStatusMessage({
        type: 'success',
        text: `Render complete (${duration}s)`,
      });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Render preview failed';
      setStatusMessage({
        type: 'error',
        text: msg,
      });
    } finally {
      setIsRendering(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-zinc-800 pb-4">
        <div>
          <div className="flex items-center space-x-2">
            <Sparkles className="h-6 w-6 text-red-500" />
            <h1 className="text-xl font-bold text-white tracking-tight">
              Automated Motion B-Roll
            </h1>
          </div>
          <p className="text-xs text-zinc-400 mt-1">
            Dynamic HTML motion graphics rendered transparently over speech pauses, metrics, and hooks.
          </p>
        </div>
      </div>

      {/* Grid: Left Editor & Right 9:16 Video Preview */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Left Column: Template Catalog & Form Controls (7 cols) */}
        <div className="lg:col-span-7 space-y-6">
          {/* Template Catalog */}
          <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5 space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-2">
                <Layers className="h-4 w-4 text-red-400" />
                <h2 className="text-sm font-semibold text-zinc-200">Template Catalog</h2>
              </div>
              {isLoadingTemplates && (
                <div className="flex items-center space-x-1.5 text-zinc-400 text-xs">
                  <Loader2 className="h-3 w-3 animate-spin text-red-400" />
                  <span>Loading...</span>
                </div>
              )}
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              {templates.map((tpl) => {
                const isSelected = tpl.id === selectedTemplateId;
                return (
                  <button
                    key={tpl.id}
                    type="button"
                    onClick={() => handleSelectTemplate(tpl)}
                    className={`flex flex-col text-left p-3.5 rounded-lg border transition-all ${
                      isSelected
                        ? 'border-red-500/80 bg-red-950/20 text-white shadow-sm'
                        : 'border-zinc-800 bg-zinc-950/60 text-zinc-400 hover:border-zinc-700 hover:text-zinc-200'
                    }`}
                  >
                    <div className="flex items-center justify-between w-full">
                      <span className="font-semibold text-xs text-zinc-100">{tpl.name}</span>
                      {isSelected && (
                        <span className="h-2 w-2 rounded-full bg-red-500 shadow-sm shadow-red-500/50" />
                      )}
                    </div>
                    {tpl.description && (
                      <p className="text-[11px] text-zinc-400 mt-1.5 line-clamp-2 leading-relaxed">
                        {tpl.description}
                      </p>
                    )}
                    <span className="text-[10px] text-zinc-500 mt-2 font-mono">
                      ~{tpl.default_duration || 3.5}s
                    </span>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Template Parameter Editor */}
          <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5 space-y-4">
            <div className="flex items-center space-x-2">
              <FileCode className="h-4 w-4 text-red-400" />
              <h2 className="text-sm font-semibold text-zinc-200">
                Parameters: {selectedTemplate?.name}
              </h2>
            </div>

            <div className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-zinc-300 mb-1">
                  Trigger Phrase (Spoken anchor in speech)
                </label>
                <input
                  type="text"
                  value={String(templateData.trigger_phrase ?? '')}
                  onChange={(e) => handleDataChange('trigger_phrase', e.target.value)}
                  className="w-full rounded bg-zinc-950 border border-zinc-800 px-3 py-1.5 text-xs text-zinc-200 focus:border-red-500 focus:outline-none placeholder-zinc-600"
                  placeholder="e.g. naik 85 persen"
                />
                <span className="text-[10px] text-zinc-500 block mt-0.5">
                  Exact 2-4 spoken words from transcript for millisecond-accurate audio sync
                </span>
              </div>

              {/* Dynamic inputs based on template */}
              {['stat_counter', 'sleek_stat_badge', 'vox_stat_counter'].includes(selectedTemplateId) && (
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                  <div>
                    <label className="block text-xs font-medium text-zinc-300 mb-1">Prefix</label>
                    <input
                      type="text"
                      value={String(templateData.prefix ?? '')}
                      onChange={(e) => handleDataChange('prefix', e.target.value)}
                      className="w-full rounded bg-zinc-950 border border-zinc-800 px-3 py-1.5 text-xs text-zinc-200 focus:border-red-500 focus:outline-none"
                      placeholder="+"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-zinc-300 mb-1">
                      Target Number
                    </label>
                    <input
                      type="text"
                      value={String(templateData.target_number ?? '')}
                      onChange={(e) => handleDataChange('target_number', e.target.value)}
                      className="w-full rounded bg-zinc-950 border border-zinc-800 px-3 py-1.5 text-xs text-zinc-200 focus:border-red-500 focus:outline-none"
                      placeholder="87"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-zinc-300 mb-1">Suffix</label>
                    <input
                      type="text"
                      value={String(templateData.suffix ?? '')}
                      onChange={(e) => handleDataChange('suffix', e.target.value)}
                      className="w-full rounded bg-zinc-950 border border-zinc-800 px-3 py-1.5 text-xs text-zinc-200 focus:border-red-500 focus:outline-none"
                      placeholder="%"
                    />
                  </div>
                  <div className="sm:col-span-2">
                    <label className="block text-xs font-medium text-zinc-300 mb-1">Label</label>
                    <input
                      type="text"
                      value={String(templateData.label ?? '')}
                      onChange={(e) => handleDataChange('label', e.target.value)}
                      className="w-full rounded bg-zinc-950 border border-zinc-800 px-3 py-1.5 text-xs text-zinc-200 focus:border-red-500 focus:outline-none"
                      placeholder="Tingkat Retensi..."
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-zinc-300 mb-1">Accent Color</label>
                    <div className="flex items-center space-x-2">
                      <input
                        type="color"
                        value={String(templateData.accent_color ?? '#FF3B30')}
                        onChange={(e) => handleDataChange('accent_color', e.target.value)}
                        className="h-8 w-10 rounded border border-zinc-800 bg-zinc-950 cursor-pointer"
                      />
                      <input
                        type="text"
                        value={String(templateData.accent_color ?? '#FF3B30')}
                        onChange={(e) => handleDataChange('accent_color', e.target.value)}
                        className="w-full rounded bg-zinc-950 border border-zinc-800 px-2 py-1.5 text-xs text-zinc-200 focus:border-red-500 focus:outline-none font-mono"
                      />
                    </div>
                  </div>
                </div>
              )}

              {['quote_card', 'sleek_quote_card', 'vox_quote_card'].includes(selectedTemplateId) && (
                <div className="space-y-3">
                  <div>
                    <label className="block text-xs font-medium text-zinc-300 mb-1">Quote</label>
                    <textarea
                      rows={3}
                      value={String(templateData.quote ?? '')}
                      onChange={(e) => handleDataChange('quote', e.target.value)}
                      className="w-full rounded bg-zinc-950 border border-zinc-800 px-3 py-1.5 text-xs text-zinc-200 focus:border-red-500 focus:outline-none"
                      placeholder="Quote statement..."
                    />
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    <div>
                      <label className="block text-xs font-medium text-zinc-300 mb-1">Author</label>
                      <input
                        type="text"
                        value={String(templateData.author ?? '')}
                        onChange={(e) => handleDataChange('author', e.target.value)}
                        className="w-full rounded bg-zinc-950 border border-zinc-800 px-3 py-1.5 text-xs text-zinc-200 focus:border-red-500 focus:outline-none"
                        placeholder="Dr. Sarah Adams"
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-medium text-zinc-300 mb-1">Title</label>
                      <input
                        type="text"
                        value={String(templateData.title ?? '')}
                        onChange={(e) => handleDataChange('title', e.target.value)}
                        className="w-full rounded bg-zinc-950 border border-zinc-800 px-3 py-1.5 text-xs text-zinc-200 focus:border-red-500 focus:outline-none"
                        placeholder="Media Psychologist"
                      />
                    </div>
                  </div>
                </div>
              )}

              {['point_highlight', 'sleek_step_list', 'vox_point_list'].includes(selectedTemplateId) && (
                <div className="space-y-3">
                  <div>
                    <label className="block text-xs font-medium text-zinc-300 mb-1">Headline</label>
                    <input
                      type="text"
                      value={String(templateData.headline ?? '')}
                      onChange={(e) => handleDataChange('headline', e.target.value)}
                      className="w-full rounded bg-zinc-950 border border-zinc-800 px-3 py-1.5 text-xs text-zinc-200 focus:border-red-500 focus:outline-none"
                      placeholder="3 Kunci Viral"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-zinc-300 mb-1">
                      Bullet Points (one per line)
                    </label>
                    <textarea
                      rows={4}
                      value={
                        Array.isArray(templateData.points)
                          ? (templateData.points as string[]).join('\n')
                          : String(templateData.points ?? '')
                      }
                      onChange={(e) =>
                        handleDataChange('points', e.target.value.split('\n'))
                      }
                      className="w-full rounded bg-zinc-950 border border-zinc-800 px-3 py-1.5 text-xs text-zinc-200 focus:border-red-500 focus:outline-none font-mono"
                      placeholder="Hook 3 detik pertama&#10;Pacing tanpa dead-air&#10;Punchline memuaskan"
                    />
                  </div>
                </div>
              )}
              {selectedTemplateId === 'vox_versus_split' && (
                <div className="space-y-4">
                  <div className="p-3 rounded-lg bg-zinc-950/80 border border-zinc-800 space-y-3">
                    <span className="text-[11px] font-mono font-bold text-amber-400 uppercase tracking-wider block">Side A (Top - Navy)</span>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                      <div>
                        <label className="block text-[11px] font-medium text-zinc-400 mb-1">Tag A</label>
                        <input
                          type="text"
                          value={String(templateData.tag_a ?? '')}
                          onChange={(e) => handleDataChange('tag_a', e.target.value)}
                          className="w-full rounded bg-zinc-900 border border-zinc-700 px-2.5 py-1.5 text-xs text-zinc-100 focus:border-red-500 focus:outline-none"
                        />
                      </div>
                      <div>
                        <label className="block text-[11px] font-medium text-zinc-400 mb-1">Title A</label>
                        <input
                          type="text"
                          value={String(templateData.title_a ?? '')}
                          onChange={(e) => handleDataChange('title_a', e.target.value)}
                          className="w-full rounded bg-zinc-900 border border-zinc-700 px-2.5 py-1.5 text-xs text-zinc-100 focus:border-red-500 focus:outline-none"
                        />
                      </div>
                    </div>
                    <div>
                      <label className="block text-[11px] font-medium text-zinc-400 mb-1">Description A</label>
                      <input
                        type="text"
                        value={String(templateData.desc_a ?? '')}
                        onChange={(e) => handleDataChange('desc_a', e.target.value)}
                        className="w-full rounded bg-zinc-900 border border-zinc-700 px-2.5 py-1.5 text-xs text-zinc-100 focus:border-red-500 focus:outline-none"
                      />
                    </div>
                  </div>

                  <div className="p-3 rounded-lg bg-zinc-950/80 border border-zinc-800 space-y-3">
                    <span className="text-[11px] font-mono font-bold text-red-400 uppercase tracking-wider block">Side B (Bottom - Coral)</span>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                      <div>
                        <label className="block text-[11px] font-medium text-zinc-400 mb-1">Tag B</label>
                        <input
                          type="text"
                          value={String(templateData.tag_b ?? '')}
                          onChange={(e) => handleDataChange('tag_b', e.target.value)}
                          className="w-full rounded bg-zinc-900 border border-zinc-700 px-2.5 py-1.5 text-xs text-zinc-100 focus:border-red-500 focus:outline-none"
                        />
                      </div>
                      <div>
                        <label className="block text-[11px] font-medium text-zinc-400 mb-1">Title B</label>
                        <input
                          type="text"
                          value={String(templateData.title_b ?? '')}
                          onChange={(e) => handleDataChange('title_b', e.target.value)}
                          className="w-full rounded bg-zinc-900 border border-zinc-700 px-2.5 py-1.5 text-xs text-zinc-100 focus:border-red-500 focus:outline-none"
                        />
                      </div>
                    </div>
                    <div>
                      <label className="block text-[11px] font-medium text-zinc-400 mb-1">Description B</label>
                      <input
                        type="text"
                        value={String(templateData.desc_b ?? '')}
                        onChange={(e) => handleDataChange('desc_b', e.target.value)}
                        className="w-full rounded bg-zinc-900 border border-zinc-700 px-2.5 py-1.5 text-xs text-zinc-100 focus:border-red-500 focus:outline-none"
                      />
                    </div>
                  </div>
                </div>
              )}

              {['vox_headline_punch', 'sleek_keyword_pill'].includes(selectedTemplateId) && (
                <div className="space-y-3">
                  <div>
                    <label className="block text-xs font-medium text-zinc-300 mb-1">Tag</label>
                    <input
                      type="text"
                      value={String(templateData.tag ?? '')}
                      onChange={(e) => handleDataChange('tag', e.target.value)}
                      className="w-full rounded bg-zinc-950 border border-zinc-800 px-3 py-1.5 text-xs text-zinc-200 focus:border-red-500 focus:outline-none"
                    />
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                    <div>
                      <label className="block text-xs font-medium text-zinc-300 mb-1">Line 1 (White)</label>
                      <input
                        type="text"
                        value={String(templateData.line_1 ?? '')}
                        onChange={(e) => handleDataChange('line_1', e.target.value)}
                        className="w-full rounded bg-zinc-950 border border-zinc-800 px-3 py-1.5 text-xs text-zinc-200 focus:border-red-500 focus:outline-none"
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-medium text-zinc-300 mb-1">Line 2 (Highlight Block)</label>
                      <input
                        type="text"
                        value={String(templateData.line_2 ?? '')}
                        onChange={(e) => handleDataChange('line_2', e.target.value)}
                        className="w-full rounded bg-zinc-950 border border-zinc-800 px-3 py-1.5 text-xs text-zinc-200 focus:border-red-500 focus:outline-none font-bold text-yellow-400"
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-medium text-zinc-300 mb-1">Line 3 (Accent)</label>
                      <input
                        type="text"
                        value={String(templateData.line_3 ?? '')}
                        onChange={(e) => handleDataChange('line_3', e.target.value)}
                        className="w-full rounded bg-zinc-950 border border-zinc-800 px-3 py-1.5 text-xs text-zinc-200 focus:border-red-500 focus:outline-none text-red-400"
                      />
                    </div>
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-zinc-300 mb-1">Subtext</label>
                    <input
                      type="text"
                      value={String(templateData.subtext ?? '')}
                      onChange={(e) => handleDataChange('subtext', e.target.value)}
                      className="w-full rounded bg-zinc-950 border border-zinc-800 px-3 py-1.5 text-xs text-zinc-200 focus:border-red-500 focus:outline-none"
                    />
                  </div>
                </div>
              )}

              {selectedTemplateId === 'vox_explainer_def' && (
                <div className="space-y-3">
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                    <div>
                      <label className="block text-xs font-medium text-zinc-300 mb-1">Term</label>
                      <input
                        type="text"
                        value={String(templateData.term ?? '')}
                        onChange={(e) => handleDataChange('term', e.target.value)}
                        className="w-full rounded bg-zinc-950 border border-zinc-800 px-3 py-1.5 text-xs text-zinc-200 focus:border-red-500 focus:outline-none"
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-medium text-zinc-300 mb-1">Phonetic</label>
                      <input
                        type="text"
                        value={String(templateData.phonetic ?? '')}
                        onChange={(e) => handleDataChange('phonetic', e.target.value)}
                        className="w-full rounded bg-zinc-950 border border-zinc-800 px-3 py-1.5 text-xs text-zinc-200 focus:border-red-500 focus:outline-none font-serif"
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-medium text-zinc-300 mb-1">Part of Speech</label>
                      <input
                        type="text"
                        value={String(templateData.pos ?? '')}
                        onChange={(e) => handleDataChange('pos', e.target.value)}
                        className="w-full rounded bg-zinc-950 border border-zinc-800 px-3 py-1.5 text-xs text-zinc-200 focus:border-red-500 focus:outline-none"
                      />
                    </div>
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-zinc-300 mb-1">Definition (with Marker Highlight)</label>
                    <textarea
                      rows={2}
                      value={String(templateData.definition ?? '')}
                      onChange={(e) => handleDataChange('definition', e.target.value)}
                      className="w-full rounded bg-zinc-950 border border-zinc-800 px-3 py-1.5 text-xs text-zinc-200 focus:border-red-500 focus:outline-none"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-zinc-300 mb-1">Context Note</label>
                    <input
                      type="text"
                      value={String(templateData.context_note ?? '')}
                      onChange={(e) => handleDataChange('context_note', e.target.value)}
                      className="w-full rounded bg-zinc-950 border border-zinc-800 px-3 py-1.5 text-xs text-zinc-200 focus:border-red-500 focus:outline-none"
                    />
                  </div>
                </div>
              )}

              {selectedTemplateId === 'vox_bar_chart' && (
                <div className="space-y-3">
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    <div>
                      <label className="block text-xs font-medium text-zinc-300 mb-1">Chart Title</label>
                      <input
                        type="text"
                        value={String(templateData.chart_title ?? '')}
                        onChange={(e) => handleDataChange('chart_title', e.target.value)}
                        className="w-full rounded bg-zinc-950 border border-zinc-800 px-3 py-1.5 text-xs text-zinc-200 focus:border-red-500 focus:outline-none"
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-medium text-zinc-300 mb-1">Source Footnote</label>
                      <input
                        type="text"
                        value={String(templateData.source ?? '')}
                        onChange={(e) => handleDataChange('source', e.target.value)}
                        className="w-full rounded bg-zinc-950 border border-zinc-800 px-3 py-1.5 text-xs text-zinc-200 focus:border-red-500 focus:outline-none"
                      />
                    </div>
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-zinc-300 mb-1">Bars Data (JSON)</label>
                    <textarea
                      rows={5}
                      value={
                        typeof templateData.bars === 'string'
                          ? templateData.bars
                          : JSON.stringify(templateData.bars ?? [], null, 2)
                      }
                      onChange={(e) => {
                        try {
                          const parsed = JSON.parse(e.target.value);
                          handleDataChange('bars', parsed);
                        } catch {
                          handleDataChange('bars', e.target.value);
                        }
                      }}
                      className="w-full rounded bg-zinc-950 border border-zinc-800 px-3 py-1.5 text-xs text-zinc-200 focus:border-red-500 focus:outline-none font-mono"
                    />
                  </div>
                </div>
              )}

              {/* Fallback JSON Editor for unknown or custom templates */}
              {![
                'stat_counter', 'quote_card', 'point_highlight',
                'vox_versus_split', 'vox_headline_punch', 'vox_explainer_def', 'vox_bar_chart'
              ].includes(selectedTemplateId) && (
                <div>
                  <label className="block text-xs font-medium text-zinc-300 mb-1">Custom Template Data (JSON)</label>
                  <textarea
                    rows={6}
                    value={JSON.stringify(templateData, null, 2)}
                    onChange={(e) => {
                      try {
                        setTemplateData(JSON.parse(e.target.value));
                      } catch {
                        // allow raw typing
                      }
                    }}
                    className="w-full rounded bg-zinc-950 border border-zinc-800 px-3 py-1.5 text-xs text-zinc-200 focus:border-red-500 focus:outline-none font-mono"
                  />
                </div>
              )}

              {/* Duration Slider */}
              <div className="space-y-2 border-t border-zinc-800 pt-4">
                <div className="flex items-center justify-between">
                  <label
                    htmlFor="broll-duration-slider"
                    className="flex items-center space-x-1.5 text-xs font-medium text-zinc-300"
                  >
                    <Sliders className="h-3.5 w-3.5 text-zinc-400" />
                    <span>Duration</span>
                  </label>
                  <span className="text-xs font-mono text-zinc-400">{duration.toFixed(1)}s</span>
                </div>
                <input
                  id="broll-duration-slider"
                  type="range"
                  min="1.5"
                  max="6.0"
                  step="0.5"
                  value={duration}
                  onChange={(e) => setDuration(parseFloat(e.target.value))}
                  className="w-full accent-red-600 bg-zinc-800 h-1.5 rounded-lg appearance-none cursor-pointer"
                />
                <div className="flex justify-between text-[10px] text-zinc-500">
                  <span>1.5s (Fast)</span>
                  <span>3.5s (Default)</span>
                  <span>6.0s (Long)</span>
                </div>
              </div>

              {/* Render Button & Status */}
              <div className="pt-2">
                <button
                  type="button"
                  data-testid="test-render-broll-button"
                  onClick={handleTestRender}
                  disabled={isRendering}
                  className="w-full flex items-center justify-center space-x-2 py-2.5 px-4 rounded-lg bg-red-600 hover:bg-red-500 text-white font-medium text-xs shadow-sm disabled:opacity-50 transition-colors"
                >
                  {isRendering ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin text-white" />
                      <span>Rendering WebM Preview...</span>
                    </>
                  ) : (
                    <>
                      <Play className="h-4 w-4 fill-white" />
                      <span>Test Render Motion B-Roll</span>
                    </>
                  )}
                </button>

                {statusMessage && (
                  <div
                    className={`mt-3 flex items-center space-x-2 text-xs p-2.5 rounded-lg border ${
                      statusMessage.type === 'success'
                        ? 'bg-emerald-950/40 text-emerald-300 border-emerald-800/60'
                        : 'bg-red-950/40 text-red-300 border-red-800/60'
                    }`}
                  >
                    {statusMessage.type === 'success' ? (
                      <CheckCircle2 className="h-4 w-4 text-emerald-400 shrink-0" />
                    ) : (
                      <AlertCircle className="h-4 w-4 text-red-400 shrink-0" />
                    )}
                    <span>{statusMessage.text}</span>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* Right Column: 9:16 Video Player Preview (5 cols) */}
        <div className="lg:col-span-5 space-y-3">
          <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5 space-y-4">
            <div className="flex items-center space-x-2">
              <Video className="h-4 w-4 text-red-400" />
              <h2 className="text-sm font-semibold text-zinc-200">
                9:16 Transparent Preview
              </h2>
            </div>

            {/* Vertical Video Viewport with Transparent Grid Background */}
            <div
              className="relative w-full max-w-[280px] sm:max-w-[300px] aspect-[9/16] mx-auto rounded-xl overflow-hidden border border-zinc-800 shadow-2xl flex items-center justify-center"
              style={{
                backgroundColor: '#0a0a0c',
                backgroundImage: `
                  linear-gradient(45deg, #18181b 25%, transparent 25%),
                  linear-gradient(-45deg, #18181b 25%, transparent 25%),
                  linear-gradient(45deg, transparent 75%, #18181b 75%),
                  linear-gradient(-45deg, transparent 75%, #18181b 75%)
                `,
                backgroundSize: '20px 20px',
                backgroundPosition: '0 0, 0 10px, 10px -10px, -10px 0px',
              }}
            >
              {previewUrl ? (
                <video
                  key={previewUrl}
                  src={previewUrl}
                  controls
                  autoPlay
                  loop
                  muted
                  playsInline
                  className="w-full h-full object-contain"
                />
              ) : (
                <div className="p-6 text-center text-zinc-500 space-y-2">
                  <div className="h-10 w-10 mx-auto rounded-full bg-zinc-900/80 border border-zinc-700/60 flex items-center justify-center text-zinc-400">
                    <Sparkles className="h-5 w-5" />
                  </div>
                  <p className="text-xs font-medium text-zinc-300">No Preview Rendered</p>
                  <p className="text-[11px] text-zinc-500 leading-relaxed">
                    Select a template, customize parameters, and click &ldquo;Test Render Motion B-Roll&rdquo; to preview.
                  </p>
                </div>
              )}
            </div>

            <div className="text-center text-[11px] text-zinc-500">
              Renders as VP9 / WebM with alpha transparency overlay for 1080x1920 shorts.
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default BrollTab;
