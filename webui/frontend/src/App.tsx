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

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100 flex flex-col font-sans">
      <Navbar
        currentTab={currentTab}
        onTabChange={setCurrentTab}
        activeJob={activeJob}
        backendHealthy={backendHealthy}
      />

      <main className="flex-1 max-w-7xl w-full mx-auto p-4 sm:p-6 lg:p-8">
        {(currentTab === 'generator' || currentTab === 'jobs' || currentTab === 'upload') && (
          <GeneratorTab
            activeJob={activeJob}
            onRefreshActiveJob={checkStatus}
            defaultVideoPath={selectedVideoPath}
            defaultProjectName={selectedProjectName}
          />
        )}

        {currentTab === 'subtitles' && (
          <SubtitlesTab
            defaultVideoPath={selectedVideoPath}
            defaultProjectName={selectedProjectName}
          />
        )}

        {currentTab === 'watermark' && (
          <WatermarkTab
            defaultVideoPath={selectedVideoPath}
            defaultProjectName={selectedProjectName}
          />
        )}

        {currentTab === 'subtitle-editor' && (
          <SubtitleEditorTab currentProject={selectedProjectName} />
        )}

        {currentTab === 'library' && (
          <LibraryTab onSelectVideo={handleSelectVideoForJob} />
        )}

        {currentTab === 'gdrive' && (
          <GDriveTab
            onSelectVideo={handleSelectVideoForJob}
            defaultProjectName={selectedProjectName}
          />
        )}

        {(currentTab === 'diagnostics' || currentTab === 'system') && (
          <DiagnosticsTab onRefresh={checkStatus} />
        )}
      </main>

      <footer className="border-t border-zinc-800/80 py-4 px-6 text-center text-xs text-zinc-400">
        ViralCutter WebUI — Modern FastAPI &amp; React Pipeline
      </footer>
    </div>
  );
}

export default App;
