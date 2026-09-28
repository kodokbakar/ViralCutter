import { useState, useEffect, useCallback } from 'react';
import { Navbar, type TabType } from './components/Navbar';
import { JobConsole } from './components/JobConsole';
import { VideoUploadPlayer } from './components/VideoUploadPlayer';
import { SubtitleEditor } from './components/SubtitleEditor';
import { MediaLibrary } from './components/MediaLibrary';
import { SystemStatusPanel } from './components/SystemStatusPanel';
import { jobsApi, systemApi } from './api/client';
import type { ActiveJobResponse } from './api/types';

export function App() {
  const [currentTab, setCurrentTab] = useState<TabType>('jobs');
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

  // Handler when a video is selected in Upload / Player or Media Library
  const handleSelectVideoForJob = (videoPath: string, projectName?: string) => {
    setSelectedVideoPath(videoPath);
    if (projectName) {
      setSelectedProjectName(projectName);
    }
    setCurrentTab('jobs');
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
        {currentTab === 'jobs' && (
          <JobConsole
            activeJob={activeJob}
            onRefreshActiveJob={checkStatus}
            defaultVideoPath={selectedVideoPath}
            defaultProjectName={selectedProjectName}
          />
        )}

        {currentTab === 'upload' && (
          <VideoUploadPlayer onSelectVideoForJob={handleSelectVideoForJob} />
        )}

        {currentTab === 'subtitles' && (
          <SubtitleEditor currentProject={selectedProjectName} />
        )}

        {currentTab === 'library' && (
          <MediaLibrary onSelectVideo={handleSelectVideoForJob} />
        )}

        {currentTab === 'system' && <SystemStatusPanel />}
      </main>

      <footer className="border-t border-zinc-800/80 py-4 px-6 text-center text-xs text-zinc-400">
        ViralCutter WebUI — Modern FastAPI &amp; React Pipeline
      </footer>
    </div>
  );
}

export default App;
