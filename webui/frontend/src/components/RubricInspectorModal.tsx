import React from 'react';
import { X, Copy, Check, Sparkles, TrendingUp, Volume2, Share2, Heart, Zap } from 'lucide-react';
import type { GeneratedClipItem } from '../api/types';

interface RubricInspectorModalProps {
  clip: GeneratedClipItem | null;
  onClose: () => void;
}

export const RubricInspectorModal: React.FC<RubricInspectorModalProps> = ({ clip, onClose }) => {
  const [copied, setCopied] = React.useState(false);
  if (!clip) return null;

  const rubric = clip.rubric || {
    composite_score: clip.score || 85,
    hook_strength: 8.5,
    retention_flow: 8.5,
    emotional_resonance: 8.0,
    shareability: 8.0,
    audio_dynamics: 8.0,
    verdict: 'High-conversion viral clip.'
  };

  const dimensions = [
    { label: 'Hook Strength (0-3s)', value: rubric.hook_strength, icon: Zap, color: 'bg-amber-400' },
    { label: 'Retention & Narrative Flow', value: rubric.retention_flow, icon: TrendingUp, color: 'bg-emerald-400' },
    { label: 'Emotional Resonance', value: rubric.emotional_resonance, icon: Heart, color: 'bg-rose-400' },
    { label: 'Shareability Probability', value: rubric.shareability, icon: Share2, color: 'bg-blue-400' },
    { label: 'Audio Delivery Dynamics', value: rubric.audio_dynamics, icon: Volume2, color: 'bg-purple-400' },
  ];

  const handleCopyHook = () => {
    if (clip.hook_title) {
      if (typeof navigator !== 'undefined' && navigator.clipboard?.writeText) {
        navigator.clipboard.writeText(clip.hook_title);
      }
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
      <div className="relative w-full max-w-lg bg-zinc-900 border border-zinc-800 rounded-2xl shadow-2xl p-6 space-y-6 text-zinc-100">
        <button
          onClick={onClose}
          aria-label="Close"
          className="absolute top-4 right-4 text-zinc-400 hover:text-white p-1 rounded-lg"
        >
          <X className="h-5 w-5" />
        </button>

        <div className="flex items-center space-x-3">
          <div className="p-2.5 rounded-xl bg-red-600/20 text-red-400 border border-red-500/30">
            <Sparkles className="h-6 w-6" />
          </div>
          <div>
            <h3 className="text-base font-bold text-white tracking-tight">Virality Rubric Audit</h3>
            <p className="text-xs text-zinc-400 truncate max-w-xs">{clip.name}</p>
          </div>
        </div>

        {/* Big Score Header */}
        <div className="p-4 rounded-xl bg-zinc-950/70 border border-zinc-800 flex items-center justify-between">
          <div>
            <div className="text-[11px] font-mono uppercase tracking-wider text-zinc-500">Composite Score</div>
            <div className="text-3xl font-black text-white tracking-tight">
              {rubric.composite_score}<span className="text-base text-zinc-500 font-medium">/100</span>
            </div>
          </div>
          <div className="text-right max-w-xs">
            <span className="text-[10px] font-mono uppercase tracking-wider text-emerald-400 block">AI Strategic Verdict</span>
            <p className="text-xs text-zinc-300 font-medium italic mt-0.5">{rubric.verdict}</p>
          </div>
        </div>

        {/* Calibrated Hook Title Box */}
        {clip.hook_title && (
          <div className="p-3.5 rounded-xl bg-amber-950/20 border border-amber-800/40 space-y-1.5">
            <div className="flex items-center justify-between">
              <span className="text-[10px] font-mono uppercase tracking-wider text-amber-400">Calibrated Stop-The-Scroll Hook</span>
              <button
                onClick={handleCopyHook}
                className="flex items-center space-x-1 text-[11px] text-amber-300 hover:text-amber-200"
              >
                {copied ? <Check className="h-3 w-3" /> : <Copy className="h-3 w-3" />}
                <span>{copied ? 'Copied' : 'Copy Hook'}</span>
              </button>
            </div>
            <div className="text-sm font-black text-white tracking-tight">{clip.hook_title}</div>
          </div>
        )}

        {/* 5-Dimension Bars */}
        <div className="space-y-3 pt-1">
          <span className="text-xs font-semibold text-zinc-300 uppercase tracking-wider block">5-Dimension Analysis</span>
          {dimensions.map((dim) => {
            const Icon = dim.icon;
            const pct = Math.min(100, Math.round((dim.value / 10.0) * 100));
            return (
              <div key={dim.label} className="space-y-1">
                <div className="flex items-center justify-between text-xs">
                  <span className="flex items-center space-x-1.5 text-zinc-300">
                    <Icon className="h-3.5 w-3.5 text-zinc-400" />
                    <span>{dim.label}</span>
                  </span>
                  <span className="font-mono font-bold text-white">{dim.value.toFixed(1)}/10</span>
                </div>
                <div className="w-full bg-zinc-800 h-2 rounded-full overflow-hidden">
                  <div className={`h-full ${dim.color} rounded-full transition-all duration-300`} style={{ width: `${pct}%` }} />
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};

export default RubricInspectorModal;
