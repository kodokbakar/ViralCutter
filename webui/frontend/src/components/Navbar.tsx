import React from 'react';
import {
  Film,
  Subtitles,
  Image as ImageIcon,
  FolderArchive,
  Activity,
  CheckCircle2,
  AlertCircle,
  Loader2,
  Cloud,
  Sliders,
  FileCode,
} from 'lucide-react';
import type { ActiveJobResponse } from '../api/types';

export type TabType =
  | 'generator'
  | 'subtitles'
  | 'watermark'
  | 'subtitle-editor'
  | 'library'
  | 'gdrive'
  | 'diagnostics'
  | 'jobs'
  | 'upload'
  | 'system';

interface NavbarProps {
  currentTab: TabType;
  onTabChange: (tab: TabType) => void;
  activeJob: ActiveJobResponse | null;
  backendHealthy: boolean;
}

export const Navbar: React.FC<NavbarProps> = ({
  currentTab,
  onTabChange,
  activeJob,
  backendHealthy,
}) => {
  const tabs = [
    { id: 'generator' as TabType, label: 'Generator', icon: Sliders },
    { id: 'subtitles' as TabType, label: 'Subtitles', icon: Subtitles },
    { id: 'watermark' as TabType, label: 'Watermark', icon: ImageIcon },
    { id: 'subtitle-editor' as TabType, label: 'Subtitle Editor', icon: FileCode },
    { id: 'library' as TabType, label: 'Library', icon: FolderArchive },
    { id: 'gdrive' as TabType, label: 'Google Drive', icon: Cloud },
    { id: 'diagnostics' as TabType, label: 'Diagnostics', icon: Activity },
  ];

  const isTabActive = (tabId: TabType) => {
    if (currentTab === tabId) return true;
    if (tabId === 'generator' && (currentTab === 'jobs' || currentTab === 'upload')) return true;
    if (tabId === 'diagnostics' && currentTab === 'system') return true;
    return false;
  };

  return (
    <header className="sticky top-0 z-40 w-full border-b border-zinc-800 bg-zinc-950/90 backdrop-blur">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-3 sm:px-6 lg:px-8">
        {/* Brand */}
        <div
          className="flex items-center space-x-2.5 cursor-pointer shrink-0"
          onClick={() => onTabChange('generator')}
        >
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-red-600/20 text-red-500 border border-red-500/30">
            <Film className="h-5 w-5" />
          </div>
          <div className="hidden sm:block">
            <div className="flex items-center space-x-1.5">
              <span className="font-bold text-base tracking-tight text-white">ViralCutter</span>
              <span className="rounded bg-red-950/60 px-1 py-0.2 text-[10px] font-semibold text-red-400 border border-red-800/40">
                WebUI
              </span>
            </div>
            <p className="text-[10px] text-zinc-400">FastAPI & React Pipeline</p>
          </div>
        </div>

        {/* Navigation Tabs */}
        <nav className="flex space-x-1 overflow-x-auto py-1 px-1 max-w-[65%] sm:max-w-none no-scrollbar">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            const active = isTabActive(tab.id);
            return (
              <button
                key={tab.id}
                onClick={() => onTabChange(tab.id)}
                className={`flex items-center space-x-1.5 rounded-lg px-2.5 py-1.5 text-xs font-medium transition-colors shrink-0 ${
                  active
                    ? 'bg-zinc-800 text-white shadow-sm border border-zinc-700'
                    : 'text-zinc-400 hover:bg-zinc-900 hover:text-zinc-200'
                }`}
              >
                <Icon className={`h-3.5 w-3.5 ${active ? 'text-red-400' : 'text-zinc-400'}`} />
                <span className="hidden lg:inline">{tab.label}</span>
              </button>
            );
          })}
        </nav>

        {/* Status Indicators */}
        <div className="flex items-center space-x-2.5 text-xs shrink-0">
          {/* Active Job Chip */}
          {activeJob?.active ? (
            <button
              onClick={() => onTabChange('generator')}
              className="flex items-center space-x-1.5 rounded-full bg-red-950/70 border border-red-700/60 px-2.5 py-1 text-red-300 animate-pulse hover:bg-red-900/50"
            >
              <Loader2 className="h-3 w-3 animate-spin text-red-400" />
              <span className="hidden sm:inline">Job Running</span>
            </button>
          ) : (
            <div className="hidden md:flex items-center space-x-1.5 text-zinc-500">
              <span className="h-2 w-2 rounded-full bg-zinc-600" />
              <span>Idle</span>
            </div>
          )}

          {/* Backend Health Dot */}
          <div
            className="flex items-center space-x-1.5 rounded-md bg-zinc-900 px-2 py-1 text-zinc-400 border border-zinc-800"
            title={backendHealthy ? 'API Connected' : 'API Disconnected'}
          >
            {backendHealthy ? (
              <>
                <CheckCircle2 className="h-3 w-3 text-emerald-400" />
                <span className="text-[11px] text-zinc-300 hidden sm:inline">API</span>
              </>
            ) : (
              <>
                <AlertCircle className="h-3 w-3 text-red-400" />
                <span className="text-[11px] text-red-300 hidden sm:inline">Offline</span>
              </>
            )}
          </div>
        </div>
      </div>
    </header>
  );
};

export default Navbar;
