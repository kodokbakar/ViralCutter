import { useState, useEffect, useCallback } from 'react';
import { Navbar, type TabType } from './components/Navbar';
import { GeneratorTab } from './components/GeneratorTab';
import { SubtitlesTab } from './components/SubtitlesTab';
import { WatermarkTab } from './components/WatermarkTab';
import { SubtitleEditorTab } from './components/SubtitleEditorTab';
import { LibraryTab } from './components/LibraryTab';
import { GDriveTab } from './components/GDriveTab';
import { DiagnosticsTab } from './components/DiagnosticsTab';
import { jobsApi, systemApi } from './api/client';
import type { ActiveJobResponse } from './api/types';

export function App() {
  const [currentTab, setCurrentTab] = useState<TabType>('generator');
  const [activeJob, setActiveJob] = useState<ActiveJobResponse | null>(null);
  const [backendHealthy, setBackendHealthy] = useState(false);

  // Cross-panel pre-fills
  const [selectedVideoPath, setSelectedVideoPath] = useState('');
  const [selectedProjectName, setSelectedProjectName] = useState('');

  // Check backend health & active job
  const checkStatus = useCallback(async () => {
    try {
      await systemApi.getHealth();
      setBackendHealthy(true);
    } catch {
      setBackendHealthy(false);
    }

    try {
      const active = await jobsApi.getActive();
      setActiveJob(active);
    } catch {
      setActiveJob(null);
    }
  }, []);

  useEffect(() => {
    checkStatus();
    const interval = setInterval(checkStatus, 4000);
    return () => clearInterval(interval);
  }, [checkStatus]);

  // Handler when a video is selected in Media Library or GDrive
  const handleSelectVideoForJob = (videoPath: string, projectName?: string) => {
    setSelectedVideoPath(videoPath);
    if (projectName) {
      setSelectedProjectName(projectName);
    }
    setCurrentTab('generator');
  };

  const handleNavigateTab = (tab: string, projectName?: string) => {
    if (projectName) {
      setSelectedProjectName(projectName);
    }
    setCurrentTab(tab as TabType);
  };

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100 flex flex-col font-sans">
      <Navbar
        currentTab={currentTab}
        onTabChange={setCurrentTab}
        activeJob={activeJob}
        backendHealthy={backendHealthy}
      />

      <main className="flex-1 max-w-7xl w-full mx-auto p-4 sm:p-6 lg:p-8">
        <div className={(currentTab === 'generator' || currentTab === 'jobs' || currentTab === 'upload') ? 'block' : 'hidden'}>
          <GeneratorTab
            activeJob={activeJob}
            onRefreshActiveJob={checkStatus}
            defaultVideoPath={selectedVideoPath}
            defaultProjectName={selectedProjectName}
            onNavigateTab={handleNavigateTab}
          />
        </div>

        <div className={currentTab === 'subtitles' ? 'block' : 'hidden'}>
          <SubtitlesTab
            defaultVideoPath={selectedVideoPath}
            defaultProjectName={selectedProjectName}
          />
        </div>

        <div className={currentTab === 'watermark' ? 'block' : 'hidden'}>
          <WatermarkTab
            defaultVideoPath={selectedVideoPath}
            defaultProjectName={selectedProjectName}
          />
        </div>

        <div className={currentTab === 'subtitle-editor' ? 'block' : 'hidden'}>
          <SubtitleEditorTab currentProject={selectedProjectName} />
        </div>

        <div className={currentTab === 'library' ? 'block' : 'hidden'}>
          <LibraryTab onSelectVideo={handleSelectVideoForJob} />
        </div>

        <div className={currentTab === 'gdrive' ? 'block' : 'hidden'}>
          <GDriveTab
            onSelectVideo={handleSelectVideoForJob}
            defaultProjectName={selectedProjectName}
          />
        </div>

        <div className={(currentTab === 'diagnostics' || currentTab === 'system') ? 'block' : 'hidden'}>
          <DiagnosticsTab onRefresh={checkStatus} />
        </div>
      </main>

      <footer className="border-t border-zinc-800/80 py-4 px-6 text-center text-xs text-zinc-400">
        ViralCutter WebUI — Modern FastAPI &amp; React Pipeline
      </footer>
    </div>
  );
}

export default App;
