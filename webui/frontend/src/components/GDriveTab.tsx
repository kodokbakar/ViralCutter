import React, { useState, useEffect, useCallback } from 'react';
import {
  Cloud,
  HardDrive,
  Download,
  Upload,
  RefreshCw,
  Search,
  CheckCircle2,
  AlertCircle,
  FileVideo,
  FolderArchive,
  Loader2,
  ArrowRight,
} from 'lucide-react';
import { gdriveApi } from '../api/client';
import type {
  GDriveStatusResponse,
  GDriveVideoItem,
  GDriveImportResponse,
  GDriveExportResponse,
} from '../api/types';

export interface GDriveTabProps {
  onSelectVideo?: (videoPath: string, projectName?: string) => void;
  defaultProjectName?: string;
}

export const GDriveTab: React.FC<GDriveTabProps> = ({
  onSelectVideo,
  defaultProjectName = '',
}) => {
  // Status State
  const [status, setStatus] = useState<GDriveStatusResponse | null>(null);
  const [statusLoading, setStatusLoading] = useState<boolean>(false);

  // Video Browser / Picker State
  const [videos, setVideos] = useState<GDriveVideoItem[]>([]);
  const [loadingVideos, setLoadingVideos] = useState<boolean>(false);
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [selectedVideo, setSelectedVideo] = useState<GDriveVideoItem | null>(null);

  // Import State
  const [importProjectName, setImportProjectName] = useState<string>('');
  const [isImporting, setIsImporting] = useState<boolean>(false);
  const [importResult, setImportResult] = useState<GDriveImportResponse | null>(null);
  const [importError, setImportError] = useState<string | null>(null);

  // Export / Backup State
  const [exportProjectName, setExportProjectName] = useState<string>(defaultProjectName);
  const [destinationFolder, setDestinationFolder] = useState<string>('ViralCutter_Backups');
  const [isExporting, setIsExporting] = useState<boolean>(false);
  const [exportResult, setExportResult] = useState<GDriveExportResponse | null>(null);
  const [exportError, setExportError] = useState<string | null>(null);

  // Load Status
  const fetchStatus = useCallback(async () => {
    setStatusLoading(true);
    try {
      const res = await gdriveApi.getStatus();
      setStatus(res);
    } catch {
      setStatus({
        available: false,
        mode: 'unconfigured',
        message: 'Could not connect to Google Drive service',
      });
    } finally {
      setStatusLoading(false);
    }
  }, []);

  // Load Videos List
  const fetchVideos = useCallback(async (query = '', forceRefresh = false) => {
    setLoadingVideos(true);
    try {
      const items = await gdriveApi.listVideos({
        query: query.trim() || undefined,
        force_refresh: forceRefresh,
      });
      setVideos(items);
    } catch {
      setVideos([]);
    } finally {
      setLoadingVideos(false);
    }
  }, []);

  useEffect(() => {
    fetchStatus();
    fetchVideos();
  }, [fetchStatus, fetchVideos]);

  // Handle Video Selection
  const handleSelectVideo = (item: GDriveVideoItem) => {
    setSelectedVideo(item);
    setImportError(null);
    setImportResult(null);
    if (!importProjectName) {
      setImportProjectName(item.name.replace(/\.[^/.]+$/, ''));
    }
  };

  // Trigger Video Import
  const handleImport = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedVideo) return;

    setIsImporting(true);
    setImportError(null);
    setImportResult(null);

    try {
      const res = await gdriveApi.importVideo({
        file_id: selectedVideo.id,
        file_path: selectedVideo.path || undefined,
        project_name: importProjectName.trim() || undefined,
      });
      setImportResult(res);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Import failed';
      setImportError(msg);
    } finally {
      setIsImporting(false);
    }
  };

  // Trigger Backup / Export to Drive
  const handleExport = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!exportProjectName.trim()) {
      setExportError('Please enter a project name to export');
      return;
    }

    setIsExporting(true);
    setExportError(null);
    setExportResult(null);

    try {
      const res = await gdriveApi.exportToDrive({
        project_name: exportProjectName.trim(),
        destination_folder: destinationFolder.trim() || undefined,
      });
      setExportResult(res);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Export failed';
      setExportError(msg);
    } finally {
      setIsExporting(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* 1. Status Banner */}
      <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="flex items-center space-x-3">
          <Cloud className="h-6 w-6 text-red-400" />
          <div>
            <div className="flex items-center space-x-2">
              <h2 className="text-base font-semibold text-white">Google Drive Integration</h2>
              {status?.available ? (
                <span className="flex items-center space-x-1 px-2 py-0.5 rounded-full text-xs font-medium bg-emerald-950/80 text-emerald-300 border border-emerald-800">
                  <CheckCircle2 className="h-3 w-3" />
                  <span>Available ({status.mode})</span>
                </span>
              ) : (
                <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-zinc-800 text-zinc-400 border border-zinc-700">
                  {status?.mode || 'Unconfigured'}
                </span>
              )}
            </div>
            <p className="text-xs text-zinc-400 mt-0.5">{status?.message || 'Checking status...'}</p>
          </div>
        </div>

        <button
          type="button"
          onClick={() => {
            fetchStatus();
            fetchVideos(searchQuery, true);
          }}
          disabled={statusLoading || loadingVideos}
          className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-xs font-medium text-zinc-200 transition-colors"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${statusLoading || loadingVideos ? 'animate-spin' : ''}`} />
          <span>Refresh</span>
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* 2. Google Drive Video Browser & Folder Picker */}
        <div className="lg:col-span-7 space-y-4">
          <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5 space-y-4">
            <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
              <div className="flex items-center space-x-2">
                <HardDrive className="h-5 w-5 text-red-400" />
                <h3 className="text-sm font-semibold text-white">Drive Video Picker</h3>
              </div>
              <span className="text-xs text-zinc-500 font-mono">{videos.length} videos found</span>
            </div>

            {/* Search Input */}
            <div className="flex space-x-2">
              <div className="relative flex-1">
                <Search className="absolute left-3 top-2.5 h-4 w-4 text-zinc-500" />
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && fetchVideos(searchQuery, false)}
                  placeholder="Filter videos in Google Drive..."
                  className="w-full bg-zinc-800 border border-zinc-700 rounded-lg pl-9 pr-3 py-2 text-xs text-zinc-200 focus:outline-none focus:border-red-500"
                />
              </div>
              <button
                type="button"
                onClick={() => fetchVideos(searchQuery, false)}
                disabled={loadingVideos}
                className="px-3 py-2 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-xs font-medium text-zinc-200"
              >
                Search
              </button>
            </div>

            {/* Videos List */}
            <div className="border border-zinc-800 rounded-lg max-h-[360px] overflow-y-auto divide-y divide-zinc-800/80 bg-zinc-950/40">
              {loadingVideos ? (
                <div className="flex items-center justify-center p-8 text-zinc-500 text-xs space-x-2">
                  <Loader2 className="h-4 w-4 animate-spin text-red-500" />
                  <span>Loading Google Drive videos...</span>
                </div>
              ) : videos.length === 0 ? (
                <div className="text-center p-8 text-xs text-zinc-500">
                  No videos found in Drive or search query returned empty.
                </div>
              ) : (
                videos.map((vid) => {
                  const isSelected = selectedVideo?.id === vid.id;
                  return (
                    <div
                      key={vid.id}
                      onClick={() => handleSelectVideo(vid)}
                      className={`p-3 cursor-pointer flex items-center justify-between transition-colors ${
                        isSelected ? 'bg-red-950/40 border-l-4 border-red-500' : 'hover:bg-zinc-800/50'
                      }`}
                    >
                      <div className="flex items-center space-x-3 min-w-0">
                        <FileVideo className={`h-5 w-5 shrink-0 ${isSelected ? 'text-red-400' : 'text-zinc-500'}`} />
                        <div className="min-w-0">
                          <p className="text-xs font-medium text-zinc-200 truncate">{vid.name}</p>
                          <p className="text-[11px] text-zinc-500 font-mono">
                            {vid.size_formatted} {vid.modified_time ? `• ${vid.modified_time}` : ''}
                          </p>
                        </div>
                      </div>

                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleSelectVideo(vid);
                        }}
                        className={`text-xs px-2.5 py-1 rounded font-medium ${
                          isSelected
                            ? 'bg-red-600 text-white'
                            : 'bg-zinc-800 text-zinc-300 hover:bg-zinc-700'
                        }`}
                      >
                        {isSelected ? 'Selected' : 'Select'}
                      </button>
                    </div>
                  );
                })
              )}
            </div>
          </div>
        </div>

        {/* 3. Import & Export Action Panels */}
        <div className="lg:col-span-5 space-y-6">
          {/* Import Panel */}
          <form onSubmit={handleImport} className="bg-zinc-900 border border-zinc-800 rounded-xl p-5 space-y-4">
            <div className="flex items-center space-x-2 border-b border-zinc-800 pb-3">
              <Download className="h-5 w-5 text-red-400" />
              <div>
                <h3 className="text-sm font-semibold text-white">Import from Google Drive</h3>
                <p className="text-xs text-zinc-400">Download video directly to local project</p>
              </div>
            </div>

            {importError && (
              <div className="flex items-center space-x-2 text-xs text-red-400 bg-red-950/40 border border-red-800/60 p-3 rounded-lg">
                <AlertCircle className="h-4 w-4 shrink-0" />
                <span>{importError}</span>
              </div>
            )}

            {importResult && (
              <div className="space-y-2 bg-emerald-950/40 border border-emerald-800/60 p-3 rounded-lg text-xs text-emerald-300">
                <div className="flex items-center space-x-1.5 font-medium">
                  <CheckCircle2 className="h-4 w-4" />
                  <span>Imported Successfully</span>
                </div>
                <p className="font-mono text-[11px] text-zinc-300 truncate">
                  Path: {importResult.video_path}
                </p>
                {onSelectVideo && (
                  <button
                    type="button"
                    onClick={() => onSelectVideo(importResult.video_path, importResult.project_folder)}
                    className="flex items-center space-x-1 text-xs text-emerald-400 hover:text-emerald-300 font-semibold underline mt-1"
                  >
                    <span>Use in Generator Tab</span>
                    <ArrowRight className="h-3 w-3" />
                  </button>
                )}
              </div>
            )}

            <div className="space-y-1.5">
              <label htmlFor="gdrive-selected-file" className="block text-xs font-medium text-zinc-300">Selected File</label>
              <input
                id="gdrive-selected-file"
                type="text"
                readOnly
                value={selectedVideo ? `${selectedVideo.name} (${selectedVideo.size_formatted})` : ''}
                placeholder="Select a video from the picker on the left"
                className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-xs text-zinc-400 focus:outline-none"
              />
            </div>

            <div className="space-y-1.5">
              <label htmlFor="gdrive-import-project-name" className="block text-xs font-medium text-zinc-300">Target Project Folder</label>
              <input
                id="gdrive-import-project-name"
                type="text"
                value={importProjectName}
                onChange={(e) => setImportProjectName(e.target.value)}
                placeholder="e.g. DriveImport_01"
                className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-xs text-zinc-100 focus:outline-none focus:border-red-500"
              />
            </div>

            <button
              type="submit"
              data-testid="import-gdrive-button"
              disabled={!selectedVideo || isImporting}
              className="w-full flex items-center justify-center space-x-2 rounded-lg bg-red-600 hover:bg-red-500 text-white px-4 py-2 text-xs font-semibold transition-colors disabled:opacity-50"
            >
              {isImporting ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  <span>Importing Video...</span>
                </>
              ) : (
                <>
                  <Download className="h-4 w-4" />
                  <span>Import to Workspace</span>
                </>
              )}
            </button>
          </form>

          {/* Backup / Export Panel */}
          <form onSubmit={handleExport} className="bg-zinc-900 border border-zinc-800 rounded-xl p-5 space-y-4">
            <div className="flex items-center space-x-2 border-b border-zinc-800 pb-3">
              <Upload className="h-5 w-5 text-red-400" />
              <div>
                <h3 className="text-sm font-semibold text-white">Backup Project to Google Drive</h3>
                <p className="text-xs text-zinc-400">Export viral clips and data to Drive folder</p>
              </div>
            </div>

            {exportError && (
              <div className="flex items-center space-x-2 text-xs text-red-400 bg-red-950/40 border border-red-800/60 p-3 rounded-lg">
                <AlertCircle className="h-4 w-4 shrink-0" />
                <span>{exportError}</span>
              </div>
            )}

            {exportResult && (
              <div className="space-y-1 bg-emerald-950/40 border border-emerald-800/60 p-3 rounded-lg text-xs text-emerald-300">
                <div className="flex items-center space-x-1.5 font-medium">
                  <CheckCircle2 className="h-4 w-4" />
                  <span>Backup Export Completed</span>
                </div>
                <p className="font-mono text-[11px] text-zinc-300 truncate">
                  Destination: {exportResult.destination}
                </p>
              </div>
            )}

            <div className="space-y-1.5">
              <label htmlFor="gdrive-export-project-name" className="block text-xs font-medium text-zinc-300">Local Project Name</label>
              <input
                id="gdrive-export-project-name"
                type="text"
                value={exportProjectName}
                onChange={(e) => setExportProjectName(e.target.value)}
                placeholder="e.g. MyShortsProject"
                className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-xs text-zinc-100 focus:outline-none focus:border-red-500"
              />
            </div>

            <div className="space-y-1.5">
              <label htmlFor="gdrive-destination-folder" className="block text-xs font-medium text-zinc-300">Destination Drive Folder</label>
              <input
                id="gdrive-destination-folder"
                type="text"
                value={destinationFolder}
                onChange={(e) => setDestinationFolder(e.target.value)}
                placeholder="ViralCutter_Backups"
                className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-xs text-zinc-100 focus:outline-none focus:border-red-500"
              />
            </div>

            <button
              type="submit"
              data-testid="export-gdrive-button"
              disabled={isExporting || !exportProjectName.trim()}
              className="w-full flex items-center justify-center space-x-2 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-200 border border-zinc-700 px-4 py-2 text-xs font-semibold transition-colors disabled:opacity-50"
            >
              {isExporting ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin text-red-400" />
                  <span>Uploading to Drive...</span>
                </>
              ) : (
                <>
                  <FolderArchive className="h-4 w-4" />
                  <span>Backup to Drive</span>
                </>
              )}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
};

export default GDriveTab;
