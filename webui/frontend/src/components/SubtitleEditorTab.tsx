import React from 'react';
import { SubtitleEditor } from './SubtitleEditor';

export interface SubtitleEditorTabProps {
  currentProject?: string;
}

export const SubtitleEditorTab: React.FC<SubtitleEditorTabProps> = ({ currentProject }) => {
  return <SubtitleEditor currentProject={currentProject} />;
};

export default SubtitleEditorTab;
