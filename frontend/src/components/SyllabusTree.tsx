import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  getCourses,
  createCourse,
  deleteCourse,
  createModule,
  deleteModule,
  createTopic,
  deleteTopic,
  createResource,
  deleteResource,
  getMyProgress,
  updateTopicProgress,
} from '../lib/syllabus';
import { TopicMaterials } from './TopicMaterials';
import {
  ChevronDown,
  ChevronRight,
  Plus,
  Trash2,
  BookOpen,
  FolderPlus,
  FilePlus,
  Link as LinkIcon,
  FileText,
  Bookmark,
  Sparkles,
} from 'lucide-react';
import type { Course, Module, Topic, Resource, LearningState, ResourceType } from '../types/syllabus';

interface SyllabusTreeProps {
  classroomId: string | number;
  isTeacher: boolean;
}

const LEARNING_STATES: LearningState[] = [
  'NOT_STARTED',
  'LEARNING',
  'PRACTICING',
  'COMPLETED',
  'REVIEW_REQUIRED',
  'MASTERED',
];

const STATE_BADGE_STYLE: Record<LearningState, string> = {
  NOT_STARTED: 'bg-slate-800 text-slate-400 border-slate-700',
  LEARNING: 'bg-blue-500/20 text-blue-300 border-blue-500/40',
  PRACTICING: 'bg-purple-500/20 text-purple-300 border-purple-500/40',
  COMPLETED: 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40',
  REVIEW_REQUIRED: 'bg-amber-500/20 text-amber-300 border-amber-500/40',
  MASTERED: 'bg-indigo-500/20 text-indigo-300 border-indigo-500/40',
};

export const SyllabusTree: React.FC<SyllabusTreeProps> = ({ classroomId, isTeacher }) => {
  const queryClient = useQueryClient();

  // Collapsible state sets
  const [expandedCourses, setExpandedCourses] = useState<Record<number, boolean>>({});
  const [expandedModules, setExpandedModules] = useState<Record<number, boolean>>({});

  // Inline forms state
  const [showCourseForm, setShowCourseForm] = useState(false);
  const [courseTitle, setCourseTitle] = useState('');
  const [courseDesc, setCourseDesc] = useState('');

  const [addingModuleForCourse, setAddingModuleForCourse] = useState<number | null>(null);
  const [moduleTitle, setModuleTitle] = useState('');

  const [addingTopicForModule, setAddingTopicForModule] = useState<number | null>(null);
  const [topicTitle, setTopicTitle] = useState('');
  const [topicDesc, setTopicDesc] = useState('');

  const [addingResourceForTopic, setAddingResourceForTopic] = useState<number | null>(null);
  const [resTitle, setResTitle] = useState('');
  const [resType, setResType] = useState<ResourceType>('LINK');
  const [resUrlOrNote, setResUrlOrNote] = useState('');

  const normalizedClassroomId = Number(classroomId);

  const invalidateSyllabusQueries = () => {
    queryClient.invalidateQueries({ queryKey: ['courses'] });
    queryClient.invalidateQueries({ queryKey: ['courses', classroomId] });
    queryClient.invalidateQueries({ queryKey: ['courses', normalizedClassroomId] });
    queryClient.invalidateQueries({ queryKey: ['my-progress'] });
    queryClient.invalidateQueries({ queryKey: ['progress-summary'] });
  };

  // Queries
  const { data: courses = [], isLoading: isLoadingCourses } = useQuery({
    queryKey: ['courses', normalizedClassroomId],
    queryFn: () => getCourses(normalizedClassroomId),
  });

  const { data: myProgress } = useQuery({
    queryKey: ['my-progress', normalizedClassroomId],
    queryFn: () => getMyProgress(normalizedClassroomId),
    enabled: !isTeacher,
  });

  // Map of topicId -> learning_state for fast lookup
  const progressMap = React.useMemo(() => {
    const map: Record<number, LearningState> = {};
    if (myProgress && Array.isArray(myProgress.courses)) {
      myProgress.courses.forEach((c: any) => {
        c.modules?.forEach((m: any) => {
          m.topics?.forEach((t: any) => {
            map[t.id] = t.learning_state || 'NOT_STARTED';
          });
        });
      });
    }
    return map;
  }, [myProgress]);

  // Mutations
  const createCourseMut = useMutation({
    mutationFn: () => createCourse(normalizedClassroomId, { title: courseTitle, description: courseDesc }),
    onSuccess: () => {
      invalidateSyllabusQueries();
      setCourseTitle('');
      setCourseDesc('');
      setShowCourseForm(false);
    },
  });

  const deleteCourseMut = useMutation({
    mutationFn: (id: number) => deleteCourse(normalizedClassroomId, id),
    onSuccess: () => {
      invalidateSyllabusQueries();
    },
  });

  const createModuleMut = useMutation({
    mutationFn: (courseId: number) => createModule(normalizedClassroomId, courseId, { title: moduleTitle }),
    onSuccess: (_, courseId) => {
      invalidateSyllabusQueries();
      setModuleTitle('');
      setAddingModuleForCourse(null);
      setExpandedCourses((prev) => ({ ...prev, [courseId]: true }));
    },
  });

  const deleteModuleMut = useMutation({
    mutationFn: (id: number) => deleteModule(normalizedClassroomId, id),
    onSuccess: () => {
      invalidateSyllabusQueries();
    },
  });

  const createTopicMut = useMutation({
    mutationFn: (moduleId: number) => createTopic(normalizedClassroomId, moduleId, { title: topicTitle, description: topicDesc }),
    onSuccess: (_, moduleId) => {
      invalidateSyllabusQueries();
      setTopicTitle('');
      setTopicDesc('');
      setAddingTopicForModule(null);
      setExpandedModules((prev) => ({ ...prev, [moduleId]: true }));
    },
  });

  const deleteTopicMut = useMutation({
    mutationFn: (id: number) => deleteTopic(normalizedClassroomId, id),
    onSuccess: () => {
      invalidateSyllabusQueries();
    },
  });

  const createResourceMut = useMutation({
    mutationFn: (topicId: number) =>
      createResource(normalizedClassroomId, topicId, { title: resTitle, resource_type: resType, url_or_note: resUrlOrNote }),
    onSuccess: () => {
      invalidateSyllabusQueries();
      setResTitle('');
      setResUrlOrNote('');
      setAddingResourceForTopic(null);
    },
  });

  const deleteResourceMut = useMutation({
    mutationFn: (id: number) => deleteResource(normalizedClassroomId, id),
    onSuccess: () => {
      invalidateSyllabusQueries();
    },
  });

  const updateProgressMut = useMutation({
    mutationFn: ({ topicId, state }: { topicId: number; state: LearningState }) =>
      updateTopicProgress(topicId, state),
    onSuccess: () => {
      invalidateSyllabusQueries();
    },
  });

  const toggleCourse = (id: number) => {
    setExpandedCourses((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  const toggleModule = (id: number) => {
    setExpandedModules((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  if (isLoadingCourses) {
    return (
      <div className="p-8 text-center bg-slate-900 border border-slate-800 rounded-3xl space-y-3">
        <div className="w-8 h-8 border-3 border-indigo-500 border-t-transparent rounded-full animate-spin mx-auto"></div>
        <p className="text-sm text-slate-400">Loading syllabus structure...</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Syllabus Header Bar */}
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-2">
          <BookOpen className="w-5 h-5 text-indigo-400" />
          <h2 className="text-xl font-bold text-white tracking-tight">Course Syllabus</h2>
        </div>

        {isTeacher && (
          <button
            onClick={() => setShowCourseForm(!showCourseForm)}
            className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold rounded-xl shadow-lg transition flex items-center space-x-2"
          >
            <Plus className="w-4 h-4" />
            <span>Add Course</span>
          </button>
        )}
      </div>

      {/* Teacher Add Course Form */}
      {isTeacher && showCourseForm && (
        <div className="p-5 bg-slate-900 border border-indigo-500/30 rounded-2xl space-y-4 shadow-xl">
          <h3 className="text-sm font-semibold text-white">Create New Course</h3>
          <div className="space-y-3">
            <input
              type="text"
              placeholder="Course Title (e.g. Data Structures & Algorithms)"
              value={courseTitle}
              onChange={(e) => setCourseTitle(e.target.value)}
              className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2 text-xs text-white focus:outline-none focus:border-indigo-500"
            />
            <textarea
              placeholder="Course Description (Optional)"
              value={courseDesc}
              onChange={(e) => setCourseDesc(e.target.value)}
              rows={2}
              className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2 text-xs text-white focus:outline-none focus:border-indigo-500"
            />
          </div>
          <div className="flex justify-end space-x-2">
            <button
              onClick={() => setShowCourseForm(false)}
              className="px-3.5 py-1.5 bg-slate-800 text-slate-300 rounded-xl text-xs font-medium hover:bg-slate-700 transition"
            >
              Cancel
            </button>
            <button
              onClick={() => createCourseMut.mutate()}
              disabled={createCourseMut.isPending || !courseTitle.trim()}
              className="px-4 py-1.5 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white rounded-xl text-xs font-semibold transition"
            >
              {createCourseMut.isPending ? 'Saving...' : 'Save Course'}
            </button>
          </div>
        </div>
      )}

      {/* Empty State */}
      {courses.length === 0 ? (
        <div className="bg-slate-900/50 border border-slate-800/80 rounded-3xl p-12 text-center space-y-4">
          <BookOpen className="w-12 h-12 text-slate-600 mx-auto" />
          <div className="space-y-1">
            <h3 className="text-base font-bold text-white">No Courses Available</h3>
            <p className="text-xs text-slate-400 max-w-sm mx-auto">
              {isTeacher
                ? "You haven't added any courses to this classroom yet. Click 'Add Course' above to start building the syllabus."
                : 'No syllabus has been published for this classroom yet. Check back soon!'}
            </p>
          </div>
        </div>
      ) : (
        /* Courses Tree List */
        <div className="space-y-4">
          {courses.map((course: Course) => {
            const isCourseExpanded = expandedCourses[course.id] ?? true;

            return (
              <div
                key={course.id}
                className="bg-slate-900 border border-slate-800 rounded-3xl overflow-hidden shadow-xl"
              >
                {/* Course Header */}
                <div className="p-5 bg-slate-900 flex items-center justify-between gap-4 border-b border-slate-800/80">
                  <div
                    onClick={() => toggleCourse(course.id)}
                    className="flex items-center space-x-3 cursor-pointer group flex-1 min-w-0"
                  >
                    <button className="text-slate-400 group-hover:text-white transition">
                      {isCourseExpanded ? <ChevronDown className="w-5 h-5" /> : <ChevronRight className="w-5 h-5" />}
                    </button>
                    <div className="min-w-0">
                      <h3 className="text-base font-bold text-white group-hover:text-indigo-300 transition truncate">
                        {course.title}
                      </h3>
                      {course.description && (
                        <p className="text-xs text-slate-400 truncate mt-0.5">{course.description}</p>
                      )}
                    </div>
                  </div>

                  {isTeacher && (
                    <div className="flex items-center space-x-2">
                      <button
                        onClick={() => setAddingModuleForCourse(course.id)}
                        className="px-3 py-1.5 bg-indigo-600/20 hover:bg-indigo-600/30 text-indigo-300 border border-indigo-500/30 rounded-xl text-xs font-semibold transition flex items-center space-x-1"
                      >
                        <FolderPlus className="w-3.5 h-3.5" />
                        <span>Add Module</span>
                      </button>
                      <button
                        onClick={() => deleteCourseMut.mutate(course.id)}
                        disabled={deleteCourseMut.isPending}
                        className="p-1.5 text-slate-500 hover:text-rose-400 transition"
                        title="Delete Course"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  )}
                </div>

                {/* Course Content (Modules) */}
                {isCourseExpanded && (
                  <div className="p-5 space-y-4 bg-slate-950/40">
                    {/* Add Module Inline Form */}
                    {isTeacher && addingModuleForCourse === course.id && (
                      <div className="p-4 bg-slate-900 border border-slate-800 rounded-2xl space-y-3">
                        <input
                          type="text"
                          placeholder="Module Title (e.g. Module 1: Binary Trees)"
                          value={moduleTitle}
                          onChange={(e) => setModuleTitle(e.target.value)}
                          className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2 text-xs text-white focus:outline-none focus:border-indigo-500"
                        />
                        <div className="flex justify-end space-x-2">
                          <button
                            onClick={() => setAddingModuleForCourse(null)}
                            className="px-3 py-1 bg-slate-800 text-slate-300 rounded-lg text-xs"
                          >
                            Cancel
                          </button>
                          <button
                            onClick={() => createModuleMut.mutate(course.id)}
                            disabled={createModuleMut.isPending || !moduleTitle.trim()}
                            className="px-3 py-1 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-xs font-semibold"
                          >
                            Save Module
                          </button>
                        </div>
                      </div>
                    )}

                    {(!course.modules || course.modules.length === 0) ? (
                      <p className="text-xs text-slate-500 italic pl-4">No modules added to this course yet.</p>
                    ) : (
                      course.modules.map((module: Module) => {
                        const isModuleExpanded = expandedModules[module.id] ?? true;

                        return (
                          <div
                            key={module.id}
                            className="bg-slate-900/80 border border-slate-800/90 rounded-2xl overflow-hidden"
                          >
                            {/* Module Header */}
                            <div className="p-4 flex items-center justify-between gap-3 border-b border-slate-800/60 bg-slate-900/40">
                              <div
                                onClick={() => toggleModule(module.id)}
                                className="flex items-center space-x-2.5 cursor-pointer group flex-1 min-w-0"
                              >
                                <button className="text-slate-400 group-hover:text-white transition">
                                  {isModuleExpanded ? (
                                    <ChevronDown className="w-4 h-4" />
                                  ) : (
                                    <ChevronRight className="w-4 h-4" />
                                  )}
                                </button>
                                <h4 className="text-xs sm:text-sm font-semibold text-slate-200 group-hover:text-indigo-300 transition truncate">
                                  {module.title}
                                </h4>
                              </div>

                              {isTeacher && (
                                <div className="flex items-center space-x-2">
                                  <button
                                    onClick={() => setAddingTopicForModule(module.id)}
                                    className="px-2.5 py-1 bg-slate-800 hover:bg-slate-700 text-indigo-300 rounded-lg text-[11px] font-medium transition flex items-center space-x-1"
                                  >
                                    <FilePlus className="w-3 h-3" />
                                    <span>Add Topic</span>
                                  </button>
                                  <button
                                    onClick={() => deleteModuleMut.mutate(module.id)}
                                    disabled={deleteModuleMut.isPending}
                                    className="p-1 text-slate-500 hover:text-rose-400 transition"
                                  >
                                    <Trash2 className="w-3.5 h-3.5" />
                                  </button>
                                </div>
                              )}
                            </div>

                            {/* Module Content (Topics) */}
                            {isModuleExpanded && (
                              <div className="p-4 space-y-4 bg-slate-950/60">
                                {/* Add Topic Inline Form */}
                                {isTeacher && addingTopicForModule === module.id && (
                                  <div className="p-3.5 bg-slate-900 border border-slate-800 rounded-xl space-y-3">
                                    <input
                                      type="text"
                                      placeholder="Topic Title (e.g. Traversal Algorithms)"
                                      value={topicTitle}
                                      onChange={(e) => setTopicTitle(e.target.value)}
                                      className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-1.5 text-xs text-white focus:outline-none focus:border-indigo-500"
                                    />
                                    <textarea
                                      placeholder="Topic Description (Optional)"
                                      value={topicDesc}
                                      onChange={(e) => setTopicDesc(e.target.value)}
                                      rows={2}
                                      className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-1.5 text-xs text-white focus:outline-none focus:border-indigo-500"
                                    />
                                    <div className="flex justify-end space-x-2">
                                      <button
                                        onClick={() => setAddingTopicForModule(null)}
                                        className="px-3 py-1 bg-slate-800 text-slate-300 rounded-lg text-xs"
                                      >
                                        Cancel
                                      </button>
                                      <button
                                        onClick={() => createTopicMut.mutate(module.id)}
                                        disabled={createTopicMut.isPending || !topicTitle.trim()}
                                        className="px-3 py-1 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-xs font-semibold"
                                      >
                                        Save Topic
                                      </button>
                                    </div>
                                  </div>
                                )}

                                {(!module.topics || module.topics.length === 0) ? (
                                  <p className="text-xs text-slate-500 italic pl-2">No topics in this module yet.</p>
                                ) : (
                                  module.topics.map((topic: Topic) => {
                                    const currentLearningState = progressMap[topic.id] || 'NOT_STARTED';

                                    return (
                                      <div
                                        key={topic.id}
                                        className="p-4 bg-slate-900/90 border border-slate-800 rounded-2xl space-y-4 hover:border-slate-700/80 transition"
                                      >
                                        {/* Topic Header & Controls */}
                                        <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-3">
                                          <div className="space-y-1 min-w-0">
                                            <div className="flex items-center space-x-2">
                                              <Sparkles className="w-4 h-4 text-indigo-400 flex-shrink-0" />
                                              <h5 className="text-xs sm:text-sm font-bold text-white truncate">
                                                {topic.title}
                                              </h5>
                                            </div>
                                            {topic.description && (
                                              <p className="text-xs text-slate-400 pl-6 leading-relaxed">
                                                {topic.description}
                                              </p>
                                            )}
                                          </div>

                                          {/* Student Progress Selector / Teacher Controls */}
                                          <div className="flex items-center space-x-2 flex-shrink-0">
                                            {!isTeacher && (
                                              <select
                                                value={currentLearningState}
                                                onChange={(e) =>
                                                  updateProgressMut.mutate({
                                                    topicId: topic.id,
                                                    state: e.target.value as LearningState,
                                                  })
                                                }
                                                className={`text-xs font-semibold px-2.5 py-1 rounded-xl border focus:outline-none cursor-pointer ${
                                                  STATE_BADGE_STYLE[currentLearningState]
                                                }`}
                                              >
                                                {LEARNING_STATES.map((st) => (
                                                  <option key={st} value={st} className="bg-slate-900 text-slate-200">
                                                    {st.replace('_', ' ')}
                                                  </option>
                                                ))}
                                              </select>
                                            )}

                                            {isTeacher && (
                                              <>
                                                <button
                                                  onClick={() => setAddingResourceForTopic(topic.id)}
                                                  className="px-2 py-1 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg text-[11px] font-medium transition flex items-center space-x-1"
                                                >
                                                  <Plus className="w-3 h-3" />
                                                  <span>Resource</span>
                                                </button>
                                                <button
                                                  onClick={() => deleteTopicMut.mutate(topic.id)}
                                                  disabled={deleteTopicMut.isPending}
                                                  className="p-1 text-slate-500 hover:text-rose-400 transition"
                                                >
                                                  <Trash2 className="w-3.5 h-3.5" />
                                                </button>
                                              </>
                                            )}
                                          </div>
                                        </div>

                                        {/* Add Resource Inline Form */}
                                        {isTeacher && addingResourceForTopic === topic.id && (
                                          <div className="p-3 bg-slate-950 border border-slate-800 rounded-xl space-y-3">
                                            <input
                                              type="text"
                                              placeholder="Resource Title (e.g. Video Lecture Link)"
                                              value={resTitle}
                                              onChange={(e) => setResTitle(e.target.value)}
                                              className="w-full bg-slate-900 border border-slate-800 rounded-lg px-3 py-1 text-xs text-white focus:outline-none focus:border-indigo-500"
                                            />
                                            <div className="flex gap-2">
                                              <select
                                                value={resType}
                                                onChange={(e) => setResType(e.target.value as ResourceType)}
                                                className="bg-slate-900 border border-slate-800 rounded-lg px-2.5 py-1 text-xs text-slate-300"
                                              >
                                                <option value="LINK">LINK</option>
                                                <option value="DOCUMENT">DOCUMENT</option>
                                                <option value="NOTE">NOTE</option>
                                              </select>
                                              <input
                                                type="text"
                                                placeholder={resType === 'NOTE' ? 'Plain text note content' : 'https://...'}
                                                value={resUrlOrNote}
                                                onChange={(e) => setResUrlOrNote(e.target.value)}
                                                className="flex-1 bg-slate-900 border border-slate-800 rounded-lg px-3 py-1 text-xs text-white focus:outline-none focus:border-indigo-500"
                                              />
                                            </div>
                                            <div className="flex justify-end space-x-2">
                                              <button
                                                onClick={() => setAddingResourceForTopic(null)}
                                                className="px-3 py-1 bg-slate-800 text-slate-300 rounded-lg text-xs"
                                              >
                                                Cancel
                                              </button>
                                              <button
                                                onClick={() => createResourceMut.mutate(topic.id)}
                                                disabled={createResourceMut.isPending || !resTitle.trim()}
                                                className="px-3 py-1 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-xs font-semibold"
                                              >
                                                Save Resource
                                              </button>
                                            </div>
                                          </div>
                                        )}

                                        {/* Resources List */}
                                        {topic.resources && topic.resources.length > 0 && (
                                          <div className="space-y-1.5 pt-2 border-t border-slate-800/40">
                                            <span className="text-[11px] font-semibold text-slate-400 block mb-1">
                                              Resources ({topic.resources.length})
                                            </span>
                                            {topic.resources.map((res: Resource) => (
                                              <div
                                                key={res.id}
                                                className="flex items-center justify-between p-2 bg-slate-950/40 border border-slate-800/60 rounded-xl text-xs"
                                              >
                                                <div className="flex items-center space-x-2 min-w-0 pr-2">
                                                  {res.resource_type === 'LINK' ? (
                                                    <LinkIcon className="w-3.5 h-3.5 text-blue-400 flex-shrink-0" />
                                                  ) : res.resource_type === 'DOCUMENT' ? (
                                                    <FileText className="w-3.5 h-3.5 text-purple-400 flex-shrink-0" />
                                                  ) : (
                                                    <Bookmark className="w-3.5 h-3.5 text-amber-400 flex-shrink-0" />
                                                  )}
                                                  <span className="font-medium text-slate-300 truncate">{res.title}</span>
                                                </div>

                                                <div className="flex items-center space-x-2">
                                                  {res.resource_type === 'LINK' ? (
                                                    <a
                                                      href={res.url_or_note}
                                                      target="_blank"
                                                      rel="noreferrer"
                                                      className="text-xs text-indigo-400 hover:underline"
                                                    >
                                                      Open Link
                                                    </a>
                                                  ) : (
                                                    <span className="text-xs text-slate-400 truncate max-w-xs">
                                                      {res.url_or_note}
                                                    </span>
                                                  )}

                                                  {isTeacher && (
                                                    <button
                                                      onClick={() => deleteResourceMut.mutate(res.id)}
                                                      className="text-slate-500 hover:text-rose-400 p-0.5"
                                                    >
                                                      <Trash2 className="w-3 h-3" />
                                                    </button>
                                                  )}
                                                </div>
                                              </div>
                                            ))}
                                          </div>
                                        )}

                                        {/* Embedded Topic Materials Component */}
                                        <TopicMaterials topicId={topic.id} isTeacher={isTeacher} />
                                      </div>
                                    );
                                  })
                                )}
                              </div>
                            )}
                          </div>
                        );
                      })
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
