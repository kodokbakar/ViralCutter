import React, { useState, useEffect, useCallback } from 'react';
import {
  FolderArchive,
  Folder,
  FileVideo,
  FileText,
  FileAudio,
  File,
  Download,
  Trash2,
  Edit2,
  RefreshCw,
  Play,
  AlertCircle,
  Loader2,
  PackageCheck,
  Calendar,
  Layers,
} from 'lucide-react';
import { libraryApi } from '../api/client';
import type {
  ProjectSummary,
  ProjectDetail,
  AssetItem,
  ExportResponse,
} from '../api/types';

interface MediaLibraryProps {
  onSelectVideo?: (videoPath: string, projectName: string) => void;
}

export const MediaLibrary: React.FC<MediaLibraryProps> = ({ onSelectVideo }) => {
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [selectedProject, setSelectedProject] = useState<string | null>(null);
  const [projectDetail, setProjectDetail] = useState<ProjectDetail | null>(null);
  const [assets, setAssets] = useState<AssetItem[]>([]);
  const [loadingProjects, setLoadingProjects] = useState(false);
  const [loadingDetail, setLoadingDetail] = useState(false);

  // Action states
  const [renaming, setRenaming] = useState(false);
  const [renameValue, setRenameValue] = useState('');
  const [exporting, setExporting] = useState(false);
  const [exportResult, setExportResult] = useState<ExportResponse | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [actionSuccessMsg, setActionSuccessMsg] = useState<string | null>(null);

  // Load projects list
  const fetchProjects = useCallback(async () => {
    setLoadingProjects(true);
    setErrorMsg(null);
    try {
      const list = await libraryApi.listProjects();
      setProjects(list);
      if (list.length > 0 && !selectedProject) {
        setSelectedProject(list[0].name);
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to load projects';
      setErrorMsg(msg);
    } finally {
      setLoadingProjects(false);
    }
  }, [selectedProject]);

  useEffect(() => {
    fetchProjects();
  }, [fetchProjects]);

  // Load selected project details & assets
  const fetchProjectDetails = useCallback(async (projectName: string) => {
    setLoadingDetail(true);
    setErrorMsg(null);
    setExportResult(null);
    try {
      const [detail, assetList] = await Promise.all([
        libraryApi.getProject(projectName),
        libraryApi.listAssets(projectName),
      ]);
      setProjectDetail(detail);
      setAssets(assetList);
      setRenameValue(projectName);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to load project details';
      setErrorMsg(msg);
    } finally {
      setLoadingDetail(false);
    }
  }, []);

  useEffect(() => {
    if (selectedProject) {
      fetchProjectDetails(selectedProject);
    } else {
      setProjectDetail(null);
      setAssets([]);
    }
  }, [selectedProject, fetchProjectDetails]);

  // Handle Project Rename
  const handleRename = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedProject || !renameValue.trim() || renameValue === selectedProject) {
      setRenaming(false);
      return;
    }

    try {
      const res = await libraryApi.renameProject(selectedProject, renameValue.trim());
      setActionSuccessMsg(`Project renamed to ${res.new_name}`);
      setSelectedProject(res.new_name);
      setRenaming(false);
      fetchProjects();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Rename failed';
      setErrorMsg(msg);
    }
  };

  // Handle Project Delete
  const handleDeleteProject = async (projectName: string) => {
    if (!window.confirm(`Are you sure you want to delete project '${projectName}'?`)) {
      return;
    }

    try {
      await libraryApi.deleteProject(projectName);
      setActionSuccessMsg(`Project '${projectName}' deleted`);
      setSelectedProject(null);
      fetchProjects();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Delete failed';
      setErrorMsg(msg);
    }
  };

  // Handle Asset Delete
  const handleDeleteAsset = async (assetPath: string, assetName: string) => {
    if (!selectedProject || !window.confirm(`Delete asset '${assetName}'?`)) {
      return;
    }

    try {
      await libraryApi.deleteAsset(assetPath);
      setActionSuccessMsg(`Asset '${assetName}' deleted`);
      fetchProjectDetails(selectedProject);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to delete asset';
      setErrorMsg(msg);
    }
  };

  // Handle Project ZIP Export
  const handleExport = async () => {
    if (!selectedProject) return;
    setExporting(true);
    setErrorMsg(null);
    try {
      const res = await libraryApi.exportProject(selectedProject);
      setExportResult(res);
      setActionSuccessMsg(`ZIP export ready: ${res.filename}`);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Export failed';
      setErrorMsg(msg);
    } finally {
      setExporting(false);
    }
  };

  const getAssetIcon = (assetType: string) => {
    switch (assetType) {
      case 'video':
        return <FileVideo className="h-4 w-4 text-red-400" />;
      case 'subtitle':
        return <FileText className="h-4 w-4 text-amber-400" />;
      case 'audio':
        return <FileAudio className="h-4 w-4 text-blue-400" />;
      default:
        return <File className="h-4 w-4 text-zinc-400" />;
    }
  };

  const formatSize = (bytes: number) => {
    if (!bytes) return '0 B';
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
      {/* Projects List Explorer */}
      <div className="lg:col-span-4 space-y-4">
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4 space-y-3">
          <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
            <div className="flex items-center space-x-2">
              <FolderArchive className="h-5 w-5 text-red-400" />
              <h2 className="text-base font-semibold text-white">Projects</h2>
            </div>
            <button
              onClick={fetchProjects}
              className="p-1 rounded text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800"
              title="Refresh projects"
            >
              <RefreshCw className={`h-4 w-4 ${loadingProjects ? 'animate-spin' : ''}`} />
            </button>
          </div>

          {projects.length === 0 && !loadingProjects && (
            <div className="text-center py-10 text-xs text-zinc-500">
              <Folder className="h-8 w-8 mx-auto mb-2 text-zinc-700" />
              <p>No projects found in VIRALS/ output directory.</p>
            </div>
          )}

          <div className="space-y-1.5 max-h-[500px] overflow-y-auto pr-1">
            {projects.map((proj) => {
              const isSelected = selectedProject === proj.name;
              return (
                <div
                  key={proj.name}
                  onClick={() => setSelectedProject(proj.name)}
                  className={`p-3 rounded-lg border cursor-pointer transition-all ${
                    isSelected
                      ? 'bg-zinc-800/90 border-red-500/50 shadow-sm'
                      : 'bg-zinc-950/60 border-zinc-800/80 hover:bg-zinc-800/50 hover:border-zinc-700'
                  }`}
                >
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-sm font-semibold text-zinc-200 truncate">
                      {proj.name}
                    </span>
                    <span className="text-xs text-zinc-500 font-mono">
                      {proj.video_count} vids
                    </span>
                  </div>
                  <div className="flex items-center space-x-3 text-xs text-zinc-500">
                    <span className="flex items-center space-x-1">
                      <Calendar className="h-3 w-3" />
                      <span>{new Date(proj.modified_at * 1000).toLocaleDateString()}</span>
                    </span>
                    {proj.segment_count > 0 && (
                      <span className="flex items-center space-x-1">
                        <Layers className="h-3 w-3" />
                        <span>{proj.segment_count} segs</span>
                      </span>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* Selected Project Details & Assets */}
      <div className="lg:col-span-8 space-y-4">
        {selectedProject ? (
          <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5 space-y-5">
            {/* Project Header & Top Actions */}
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-zinc-800 pb-4">
              <div>
                {renaming ? (
                  <form onSubmit={handleRename} className="flex items-center space-x-2">
                    <input
                      type="text"
                      value={renameValue}
                      onChange={(e) => setRenameValue(e.target.value)}
                      className="rounded bg-zinc-950 border border-zinc-700 px-2 py-1 text-sm text-zinc-100 focus:border-red-500 focus:outline-none"
                      autoFocus
                    />
                    <button
                      type="submit"
                      className="px-2.5 py-1 rounded bg-red-600 hover:bg-red-500 text-xs font-semibold text-white"
                    >
                      Save
                    </button>
                    <button
                      type="button"
                      onClick={() => setRenaming(false)}
                      className="px-2.5 py-1 rounded bg-zinc-800 hover:bg-zinc-700 text-xs text-zinc-300"
                    >
                      Cancel
                    </button>
                  </form>
                ) : (
                  <div className="flex items-center space-x-2">
                    <h3 className="text-lg font-bold text-white">{selectedProject}</h3>
                    <button
                      onClick={() => setRenaming(true)}
                      className="p-1 rounded text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800"
                      title="Rename Project"
                    >
                      <Edit2 className="h-3.5 w-3.5" />
                    </button>
                  </div>
                )}
                {projectDetail && (
                  <p className="text-xs text-zinc-500 font-mono mt-0.5">{projectDetail.path}</p>
                )}
              </div>

              {/* Action Buttons */}
              <div className="flex items-center space-x-2">
                <button
                  type="button"
                  onClick={handleExport}
                  disabled={exporting}
                  className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-zinc-800 hover:bg-zinc-700 border border-zinc-700 text-xs font-medium text-zinc-200 transition-colors disabled:opacity-50"
                >
                  {exporting ? (
                    <Loader2 className="h-3.5 w-3.5 animate-spin text-red-400" />
                  ) : (
                    <PackageCheck className="h-3.5 w-3.5 text-red-400" />
                  )}
                  <span>Export ZIP</span>
                </button>

                <button
                  type="button"
                  onClick={() => handleDeleteProject(selectedProject)}
                  className="p-1.5 rounded-lg bg-zinc-800/80 hover:bg-red-950 border border-zinc-700 hover:border-red-700 text-zinc-400 hover:text-red-300 transition-colors"
                  title="Delete Project"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
            </div>

            {/* Notifications */}
            {actionSuccessMsg && (
              <div className="text-xs text-emerald-400 bg-emerald-950/30 border border-emerald-800/40 p-2.5 rounded-lg">
                {actionSuccessMsg}
              </div>
            )}
            {errorMsg && (
              <div className="flex items-center space-x-2 text-xs text-red-400 bg-red-950/30 border border-red-800/40 p-2.5 rounded-lg">
                <AlertCircle className="h-4 w-4 shrink-0" />
                <span>{errorMsg}</span>
              </div>
            )}

            {/* ZIP Export Download Banner */}
            {exportResult && (
              <div className="flex items-center justify-between bg-zinc-950 border border-emerald-800/60 rounded-lg p-3 text-xs">
                <div className="flex items-center space-x-2 text-zinc-300">
                  <PackageCheck className="h-4 w-4 text-emerald-400" />
                  <span>
                    Archive ready: <strong className="text-white">{exportResult.filename}</strong> (
                    {formatSize(exportResult.size_bytes)})
                  </span>
                </div>
                <a
                  href={libraryApi.getDownloadUrl(exportResult.zip_path)}
                  download={exportResult.filename}
                  className="flex items-center space-x-1 px-3 py-1 rounded bg-emerald-600 hover:bg-emerald-500 text-white font-medium transition-colors"
                >
                  <Download className="h-3.5 w-3.5" />
                  <span>Download</span>
                </a>
              </div>
            )}

            {/* Assets Table */}
            <div className="space-y-2">
              <h4 className="text-xs font-medium uppercase tracking-wider text-zinc-400">
                Project Assets ({assets.length})
              </h4>

              {loadingDetail ? (
                <div className="py-12 flex justify-center">
                  <Loader2 className="h-6 w-6 animate-spin text-zinc-500" />
                </div>
              ) : assets.length === 0 ? (
                <div className="text-center py-10 text-xs text-zinc-500 bg-zinc-950/40 rounded-lg border border-zinc-800">
                  No assets discovered in this project directory.
                </div>
              ) : (
                <div className="border border-zinc-800 rounded-lg overflow-hidden">
                  <table className="min-w-full divide-y divide-zinc-800 text-xs">
                    <thead className="bg-zinc-950 text-zinc-400 font-medium">
                      <tr>
                        <th className="px-3 py-2 text-left">Asset</th>
                        <th className="px-3 py-2 text-left">Type</th>
                        <th className="px-3 py-2 text-right">Size</th>
                        <th className="px-3 py-2 text-right">Actions</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-zinc-800/60 bg-zinc-950/40 text-zinc-300">
                      {assets.map((asset) => (
                        <tr key={asset.name} className="hover:bg-zinc-800/40 transition-colors">
                          <td className="px-3 py-2.5 flex items-center space-x-2 font-mono">
                            {getAssetIcon(asset.asset_type)}
                            <span className="truncate max-w-[240px] text-zinc-200">
                              {asset.name}
                            </span>
                          </td>
                          <td className="px-3 py-2.5 capitalize text-zinc-400">
                            {asset.asset_type}
                          </td>
                          <td className="px-3 py-2.5 text-right font-mono text-zinc-400">
                            {formatSize(asset.size)}
                          </td>
                          <td className="px-3 py-2.5 text-right space-x-1">
                            {asset.asset_type === 'video' && onSelectVideo && (
                              <button
                                type="button"
                                onClick={() => onSelectVideo(asset.path, selectedProject)}
                                className="p-1 rounded text-zinc-400 hover:text-red-400 hover:bg-zinc-800"
                                title="Preview video"
                              >
                                <Play className="h-3.5 w-3.5" />
                              </button>
                            )}
                            <button
                              type="button"
                              onClick={() => handleDeleteAsset(asset.path, asset.name)}
                              className="p-1 rounded text-zinc-500 hover:text-red-400 hover:bg-zinc-800"
                              title="Delete asset"
                            >
                              <Trash2 className="h-3.5 w-3.5" />
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>
        ) : (
          <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-12 text-center text-zinc-500 text-xs">
            <FolderArchive className="h-10 w-10 mx-auto mb-2 text-zinc-700" />
            <p>Select a project from the left to inspect assets and exports.</p>
          </div>
        )}
      </div>
    </div>
  );
};
