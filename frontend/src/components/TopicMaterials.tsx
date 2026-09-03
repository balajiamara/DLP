import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getTopicMaterials, uploadTopicMaterial, getMaterialDownloadUrl, deleteMaterial } from '../lib/materials';
import { FileText, Download, Upload, Trash2, Loader2, Paperclip } from 'lucide-react';
import type { Material } from '../types/materials';

interface TopicMaterialsProps {
  topicId: number;
  isTeacher: boolean;
}

export const TopicMaterials: React.FC<TopicMaterialsProps> = ({ topicId, isTeacher }) => {
  const queryClient = useQueryClient();
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState('');
  const [showUploadForm, setShowUploadForm] = useState(false);
  const [downloadingId, setDownloadingId] = useState<number | null>(null);

  const { data: materials = [], isLoading } = useQuery({
    queryKey: ['materials', topicId],
    queryFn: () => getTopicMaterials(topicId),
  });

  const uploadMutation = useMutation({
    mutationFn: async () => {
      if (!file) throw new Error('Please select a file to upload.');
      return uploadTopicMaterial(topicId, file, title || file.name);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['materials', topicId] });
      setFile(null);
      setTitle('');
      setShowUploadForm(false);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (materialId: number) => deleteMaterial(materialId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['materials', topicId] });
    },
  });

  const handleDownload = async (materialId: number) => {
    try {
      setDownloadingId(materialId);
      const signedUrl = await getMaterialDownloadUrl(materialId);
      window.open(signedUrl, '_blank');
    } catch (err) {
      console.error('Failed to get download URL:', err);
    } finally {
      setDownloadingId(null);
    }
  };

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  return (
    <div className="mt-3 space-y-3 pt-3 border-t border-slate-800/60">
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold text-slate-400 flex items-center space-x-1.5">
          <Paperclip className="w-3.5 h-3.5 text-indigo-400" />
          <span>File Materials ({materials.length})</span>
        </span>

        {isTeacher && (
          <button
            onClick={() => setShowUploadForm(!showUploadForm)}
            className="text-xs text-indigo-400 hover:text-indigo-300 font-medium transition flex items-center space-x-1"
          >
            <Upload className="w-3.5 h-3.5" />
            <span>{showUploadForm ? 'Cancel' : 'Upload Material'}</span>
          </button>
        )}
      </div>

      {/* Upload Form for Teachers */}
      {isTeacher && showUploadForm && (
        <div className="p-3 bg-slate-950/80 border border-slate-800 rounded-xl space-y-3">
          <div className="space-y-2">
            <input
              type="text"
              placeholder="Material Title (Optional)"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              className="w-full bg-slate-900 border border-slate-800 rounded-lg px-3 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-indigo-500"
            />
            <input
              type="file"
              onChange={(e) => setFile(e.target.files?.[0] || null)}
              className="w-full text-xs text-slate-400 file:mr-3 file:py-1 file:px-3 file:rounded-lg file:border-0 file:text-xs file:font-semibold file:bg-indigo-600/20 file:text-indigo-300 hover:file:bg-indigo-600/30"
            />
          </div>

          {uploadMutation.isError && (
            <p className="text-xs text-rose-400">
              {(uploadMutation.error as Error)?.message || 'Failed to upload material.'}
            </p>
          )}

          <button
            onClick={() => uploadMutation.mutate()}
            disabled={uploadMutation.isPending || !file}
            className="w-full py-1.5 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed text-white text-xs font-semibold rounded-lg shadow transition flex items-center justify-center space-x-2"
          >
            {uploadMutation.isPending ? (
              <>
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                <span>Uploading...</span>
              </>
            ) : (
              <>
                <Upload className="w-3.5 h-3.5" />
                <span>Upload File</span>
              </>
            )}
          </button>
        </div>
      )}

      {/* Materials List */}
      {isLoading ? (
        <p className="text-xs text-slate-500 italic">Loading materials...</p>
      ) : materials.length === 0 ? (
        <p className="text-xs text-slate-500 italic">No file materials attached yet.</p>
      ) : (
        <div className="space-y-1.5">
          {materials.map((mat: Material) => (
            <div
              key={mat.id}
              className="flex items-center justify-between p-2.5 bg-slate-950/60 border border-slate-800/80 rounded-xl hover:border-slate-700 transition group"
            >
              <div className="flex items-center space-x-2.5 min-w-0 pr-2">
                <FileText className="w-4 h-4 text-indigo-400 flex-shrink-0" />
                <div className="min-w-0">
                  <p className="text-xs font-medium text-slate-200 truncate">{mat.title}</p>
                  <p className="text-[10px] text-slate-500 truncate">
                    {mat.file_name} • {formatFileSize(mat.file_size_bytes)} • Uppercase: {mat.file_type.toUpperCase()}
                  </p>
                </div>
              </div>

              <div className="flex items-center space-x-2">
                <button
                  onClick={() => handleDownload(mat.id)}
                  disabled={downloadingId === mat.id}
                  className="px-2.5 py-1 bg-slate-800 hover:bg-indigo-600/30 text-indigo-300 border border-slate-700 hover:border-indigo-500/40 rounded-lg text-xs font-medium transition flex items-center space-x-1"
                >
                  {downloadingId === mat.id ? (
                    <Loader2 className="w-3 h-3 animate-spin" />
                  ) : (
                    <Download className="w-3 h-3" />
                  )}
                  <span>Download</span>
                </button>

                {isTeacher && (
                  <button
                    onClick={() => deleteMutation.mutate(mat.id)}
                    disabled={deleteMutation.isPending}
                    className="p-1 text-slate-500 hover:text-rose-400 transition"
                    title="Delete Material"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
