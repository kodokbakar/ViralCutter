import React from 'react';
import { MediaLibrary } from './MediaLibrary';

export interface LibraryTabProps {
  onSelectVideo?: (videoPath: string, projectName: string) => void;
}

export const LibraryTab: React.FC<LibraryTabProps> = ({ onSelectVideo }) => {
  return <MediaLibrary onSelectVideo={onSelectVideo} />;
};

export default LibraryTab;
