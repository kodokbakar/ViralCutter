import React from 'react';
import {
  Film,
  Terminal,
  Upload,
  Subtitles,
  FolderArchive,
  Activity,
  CheckCircle2,
  AlertCircle,
  Loader2,
} from 'lucide-react';
import type { ActiveJobResponse } from '../api/types';

export type TabType = 'jobs' | 'upload' | 'subtitles' | 'library' | 'system';

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
    { id: 'jobs', label: 'Job Console', icon: Terminal },
    { id: 'upload', label: 'Video & Player', icon: Upload },
    { id: 'subtitles', label: 'Subtitle Editor', icon: Subtitles },
    { id: 'library', label: 'Media Library', icon: FolderArchive },
    { id: 'system', label: 'System Status', icon: Activity },
  ] as const;

  return (
    <header className="sticky top-0 z-40 w-full border-b border-zinc-800 bg-zinc-950/90 backdrop-blur">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
        {/* Brand */}
        <div className="flex items-center space-x-3 cursor-pointer" onClick={() => onTabChange('jobs')}>
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-red-600/20 text-red-500 border border-red-500/30">
            <Film className="h-6 w-6" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <span className="font-bold text-lg tracking-tight text-white">ViralCutter</span>
              <span className="rounded bg-red-950/60 px-1.5 py-0.5 text-xs font-semibold text-red-400 border border-red-800/40">
                WebUI
              </span>
            </div>
            <p className="text-xs text-zinc-400">FastAPI & React Pipeline</p>
          </div>
        </div>

        {/* Navigation Tabs */}
        <nav className="flex space-x-1 sm:space-x-2">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            const isActive = currentTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => onTabChange(tab.id)}
                className={`flex items-center space-x-2 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
                  isActive
                    ? 'bg-zinc-800 text-white shadow-sm border border-zinc-700'
                    : 'text-zinc-400 hover:bg-zinc-900 hover:text-zinc-200'
                }`}
              >
                <Icon className={`h-4 w-4 ${isActive ? 'text-red-400' : 'text-zinc-400'}`} />
                <span className="hidden md:inline">{tab.label}</span>
              </button>
            );
          })}
        </nav>

        {/* Status Indicators */}
        <div className="flex items-center space-x-3 text-xs">
          {/* Active Job Chip */}
          {activeJob?.has_active_job ? (
            <button
              onClick={() => onTabChange('jobs')}
              className="flex items-center space-x-2 rounded-full bg-red-950/70 border border-red-700/60 px-3 py-1 text-red-300 animate-pulse hover:bg-red-900/50"
            >
              <Loader2 className="h-3.5 w-3.5 animate-spin text-red-400" />
              <span>Job Running</span>
            </button>
          ) : (
            <div className="hidden sm:flex items-center space-x-1.5 text-zinc-500">
              <span className="h-2 w-2 rounded-full bg-zinc-600" />
              <span>Idle</span>
            </div>
          )}

          {/* Backend Health Dot */}
          <div
            className="flex items-center space-x-1.5 rounded-md bg-zinc-900 px-2.5 py-1 text-zinc-400 border border-zinc-800"
            title={backendHealthy ? 'API Connected' : 'API Disconnected'}
          >
            {backendHealthy ? (
              <>
                <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" />
                <span className="text-zinc-300">API</span>
              </>
            ) : (
              <>
                <AlertCircle className="h-3.5 w-3.5 text-red-400" />
                <span className="text-red-300">Offline</span>
              </>
            )}
          </div>
        </div>
      </div>
    </header>
  );
};
