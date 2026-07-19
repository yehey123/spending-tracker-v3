'use client';
import { useState, useCallback } from 'react';
import { useDropzone } from 'react-dropzone';
import { useQueryClient } from '@tanstack/react-query';
import { useRouter } from 'next/navigation';
import { api } from '@/lib/api';
import type { Statement } from '@/lib/types';
import { Upload, FileText, CheckCircle, XCircle, Loader } from 'lucide-react';

export default function UploadPage() {
  const qc = useQueryClient();
  const router = useRouter();
  const [file, setFile] = useState<File | null>(null);
  const [status, setStatus] = useState<'idle' | 'uploading' | 'success' | 'error'>('idle');
  const [result, setResult] = useState<Statement | null>(null);
  const [error, setError] = useState('');
  const [newAccountId, setNewAccountId] = useState<number | null>(null);
  const [statementKind, setStatementKind] = useState<'bank_account' | 'credit_card'>('bank_account');

  const onDrop = useCallback((accepted: File[]) => {
    if (accepted[0]) { setFile(accepted[0]); setStatus('idle'); setResult(null); setError(''); }
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { 'image/png': [], 'image/jpeg': [], 'application/pdf': [] },
    maxFiles: 1,
  });

  const handleUpload = async () => {
    if (!file) return;
    setStatus('uploading');
    try {
      const form = new FormData();
      form.append('file', file);
      form.append('statement_kind', statementKind);
      const data = await api.upload<Statement>('/statements/upload', form);
      if (data.status === 'staged') {
        router.push(`/statements/${data.id}/review`);
        return;
      }
      setResult(data);
      setStatus('success');
      if (data.account_created && data.account_id != null) {
        setNewAccountId(data.account_id);
      }
      qc.invalidateQueries({ queryKey: ['statements'] });
      qc.invalidateQueries({ queryKey: ['transactions'] });
      qc.invalidateQueries({ queryKey: ['accounts'] });
    } catch (e: any) {
      setError(e.message || 'Upload failed');
      setStatus('error');
    }
  };

  return (
    <div className="space-y-6 max-w-xl mx-auto">
      <h1 className="text-2xl font-bold">Upload Statement</h1>

      <div
        {...getRootProps()}
        className={`border-2 border-dashed rounded-xl p-10 text-center cursor-pointer transition-colors ${
          isDragActive ? 'border-indigo-400 bg-indigo-50' : 'border-gray-300 hover:border-indigo-400'
        }`}
      >
        <input {...getInputProps()} />
        <Upload className="mx-auto mb-3 text-gray-400" size={36} />
        {file ? (
          <div className="flex items-center justify-center gap-2 text-sm text-gray-700">
            <FileText size={16} />
            <span>{file.name}</span>
          </div>
        ) : (
          <p className="text-gray-500 text-sm">
            {isDragActive ? 'Drop it here' : 'Drag a PNG, JPEG, or PDF · or click to browse'}
          </p>
        )}
      </div>

      {file && (
        <div className="flex rounded-xl overflow-hidden border border-gray-200 text-sm font-medium">
          <button
            onClick={() => setStatementKind('bank_account')}
            className={`flex-1 py-2.5 transition-colors ${statementKind === 'bank_account' ? 'bg-indigo-600 text-white' : 'bg-white text-gray-600 hover:bg-gray-50'}`}
          >
            Bank Account
          </button>
          <button
            onClick={() => setStatementKind('credit_card')}
            className={`flex-1 py-2.5 transition-colors ${statementKind === 'credit_card' ? 'bg-indigo-600 text-white' : 'bg-white text-gray-600 hover:bg-gray-50'}`}
          >
            Credit Card
          </button>
        </div>
      )}

      {file && status !== 'uploading' && (
        <button
          onClick={handleUpload}
          className="w-full bg-indigo-600 text-white py-3 rounded-xl font-semibold hover:bg-indigo-700 transition-colors"
        >
          Upload &amp; Process
        </button>
      )}

      {status === 'uploading' && (
        <div className="flex items-center justify-center gap-2 text-indigo-600 py-4">
          <Loader size={20} className="animate-spin" />
          <span>Processing statement…</span>
        </div>
      )}

      {status === 'success' && result && (
        <div className="space-y-3">
          <div className="bg-green-50 border border-green-200 rounded-xl p-4 flex items-start gap-3">
            <CheckCircle className="text-green-500 mt-0.5" size={20} />
            <div>
              <div className="font-semibold text-green-800">Processed successfully</div>
              <div className="text-sm text-green-700 mt-1">
                {result.transaction_count} transaction{result.transaction_count !== 1 ? 's' : ''} imported
              </div>
            </div>
          </div>
          {newAccountId !== null && (
            <div className="bg-blue-50 border border-blue-200 rounded-xl p-4 flex items-center justify-between">
              <span className="text-sm text-blue-800">
                New account detected — tap to set name and opening balance.
              </span>
              <div className="flex gap-2 ml-3 shrink-0">
                <a href="/accounts" className="text-xs font-medium text-blue-600 underline">
                  Go to Accounts
                </a>
                <button onClick={() => setNewAccountId(null)} className="text-xs text-gray-400">✕</button>
              </div>
            </div>
          )}
        </div>
      )}

      {status === 'error' && (
        <div className="bg-red-50 border border-red-200 rounded-xl p-4 flex items-start gap-3">
          <XCircle className="text-red-500 mt-0.5" size={20} />
          <div>
            <div className="font-semibold text-red-800">Upload failed</div>
            <div className="text-sm text-red-700 mt-1">{error}</div>
          </div>
        </div>
      )}
    </div>
  );
}
