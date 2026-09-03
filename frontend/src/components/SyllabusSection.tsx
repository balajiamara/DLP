import React from 'react';
import { ProgressSummaryCard } from './ProgressSummaryCard';
import { SyllabusTree } from './SyllabusTree';

interface SyllabusSectionProps {
  classroomId: string | number;
  isTeacher: boolean;
}

export const SyllabusSection: React.FC<SyllabusSectionProps> = ({ classroomId, isTeacher }) => {
  return (
    <div className="space-y-8">
      {/* Student Progress Summary Header (Hidden for Teacher view or rendered if student) */}
      {!isTeacher && <ProgressSummaryCard classroomId={classroomId} />}

      {/* Main Collapsible Syllabus Tree */}
      <SyllabusTree classroomId={classroomId} isTeacher={isTeacher} />
    </div>
  );
};
