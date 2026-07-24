'use client';
import React, { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import type { AppSettings, SettingsPut, ModelsResponse, Category, CategoryCreate } from '@/lib/types';
import { CheckCircle, XCircle, Loader, Plus, Trash2 } from 'lucide-react';

export default function SettingsPage() {
  const qc = useQueryClient();

  // Backend URL
  const [backendUrl, setBackendUrl] = useState('');
  const [urlStatus, setUrlStatus] = useState<'idle' | 'checking' | 'connected' | 'error'>('idle');

  useEffect(() => {
    setBackendUrl(localStorage.getItem('spending_tracker_backend_url') ?? 'http://localhost:8000');
  }, []);

  const checkUrl = async () => {
    setUrlStatus('checking');
    try {
      const res = await fetch(`${backendUrl}/health`);
      if (res.ok) { localStorage.setItem('spending_tracker_backend_url', backendUrl); setUrlStatus('connected'); }
      else setUrlStatus('error');
    } catch { setUrlStatus('error'); }
  };

  // Settings
  const { data: settings } = useQuery({
    queryKey: ['settings'],
    queryFn: () => api.get<AppSettings>('/settings'),
  });

  const [ocrProvider, setOcrProvider] = useState<AppSettings['ocr_provider']>('tesseract');
  const [anthropicKey, setAnthropicKey] = useState('');
  const [openaiKey, setOpenaiKey] = useState('');
  const [reviewBeforeCommit, setReviewBeforeCommit] = useState(true);
  const [homeCurrency, setHomeCurrency] = useState('');
  const [maxOutputTokens, setMaxOutputTokens] = useState<string>('');
  const [devMode, setDevMode] = useState(false);
  const [aiModel, setAiModel] = useState('');
  const [geminiKey, setGeminiKey] = useState('');
  const [googleProjectId, setGoogleProjectId] = useState('');
  const [googleLocation, setGoogleLocation] = useState('us-central1');

  const { data: ocrModels } = useQuery({
    queryKey: ['models', ocrProvider],
    queryFn: () => api.get<ModelsResponse>(`/settings/models?provider=${ocrProvider}`),
    enabled: ocrProvider !== 'tesseract',
  });

  const { data: currenciesData } = useQuery({
    queryKey: ['currencies'],
    queryFn: () => api.get<{ currencies: Record<string, string> }>('/exchange-rates/supported'),
  });
  const supportedCurrencies = Object.entries(currenciesData?.currencies ?? {});

  useEffect(() => {
    if (settings) {
      setOcrProvider(settings.ocr_provider);
      if (settings.review_before_commit !== undefined) setReviewBeforeCommit(!!settings.review_before_commit);
      if (settings.home_currency) setHomeCurrency(settings.home_currency);
      if (settings.ai_model) setAiModel(settings.ai_model);
      if (settings.google_project_id) setGoogleProjectId(settings.google_project_id);
      if (settings.google_location) setGoogleLocation(settings.google_location);
      if (settings.max_output_tokens) setMaxOutputTokens(String(settings.max_output_tokens));
      if (settings.dev_mode !== undefined) setDevMode(!!settings.dev_mode);
    }
  }, [settings]);

  const settingsMutation = useMutation({
    mutationFn: (body: SettingsPut) => api.put<AppSettings>('/settings', body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['settings'] }),
  });

  const handleReviewToggle = (v: boolean) => {
    setReviewBeforeCommit(v);
    settingsMutation.mutate({ ocr_provider: ocrProvider, review_before_commit: v });
  };

  const handleCurrencyChange = (v: string) => {
    setHomeCurrency(v);
    settingsMutation.mutate({ ocr_provider: ocrProvider, home_currency: v || null });
  };

  // Categories
  const { data: categories = [] } = useQuery({
    queryKey: ['categories'],
    queryFn: () => api.get<Category[]>('/categories'),
  });

  const [newName, setNewName] = useState('');
  const [newColor, setNewColor] = useState('#6366F1');
  const [newParentId, setNewParentId] = useState<string>('');

  const addCategory = useMutation({
    mutationFn: (body: CategoryCreate) => api.post<Category>('/categories', body),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['categories'] }); setNewName(''); setNewParentId(''); },
  });

  const deleteCategory = useMutation({
    mutationFn: (id: number) => api.delete(`/categories/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['categories'] }),
  });

  return (
    <div className="space-y-8 max-w-xl mx-auto">
      <h1 className="text-2xl font-bold">Settings</h1>

      {/* Backend URL */}
      <section className="bg-white rounded-xl p-5 shadow-sm space-y-3">
        <h2 className="font-semibold">Backend URL</h2>
        <div className="flex gap-2">
          <input
            value={backendUrl}
            onChange={(e) => { setBackendUrl(e.target.value); setUrlStatus('idle'); }}
            className="border rounded-lg px-3 py-2 text-sm flex-1"
            placeholder="http://localhost:8000"
          />
          <button onClick={checkUrl} className="bg-indigo-600 text-white px-4 py-2 rounded-lg text-sm">
            {urlStatus === 'checking' ? <Loader size={16} className="animate-spin" /> : 'Check'}
          </button>
        </div>
        {urlStatus === 'connected' && <p className="text-green-600 text-xs flex items-center gap-1"><CheckCircle size={13} /> Connected</p>}
        {urlStatus === 'error' && <p className="text-red-600 text-xs flex items-center gap-1"><XCircle size={13} /> Could not connect</p>}
      </section>

      {/* Import Settings */}
      <section className="bg-white rounded-xl p-5 shadow-sm space-y-3">
        <h2 className="font-semibold">Import Settings</h2>
        {settings?.dev_mode_available !== false && (
          <div className="flex items-center justify-between">
            <div>
              <label className="text-sm font-medium">Development mode</label>
              <p className="text-xs text-gray-400 mt-0.5">Skips AI categorisation to save tokens while testing</p>
            </div>
            <input
              type="checkbox"
              checked={devMode}
              onChange={(e) => {
                setDevMode(e.target.checked);
                settingsMutation.mutate({ dev_mode: e.target.checked });
              }}
              className="w-4 h-4 accent-indigo-600"
            />
          </div>
        )}
        <div className="flex items-center justify-between">
          <label className="text-sm">Review before committing</label>
          <input
            type="checkbox"
            checked={reviewBeforeCommit}
            onChange={(e) => handleReviewToggle(e.target.checked)}
            className="w-4 h-4 accent-indigo-600"
          />
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-xs text-gray-500">Home currency</label>
          {supportedCurrencies.length > 0 ? (
            <select
              value={homeCurrency}
              onChange={(e) => handleCurrencyChange(e.target.value)}
              className="border rounded-lg px-3 py-2 text-sm w-full"
            >
              <option value="">No preference</option>
              {supportedCurrencies.map(([code, name]) => (
                <option key={code} value={code}>{code} — {name}</option>
              ))}
            </select>
          ) : (
            <input
              value={homeCurrency}
              onChange={(e) => setHomeCurrency(e.target.value.toUpperCase().slice(0, 3))}
              onBlur={(e) => handleCurrencyChange(e.target.value)}
              placeholder="e.g. PHP, USD, EUR"
              className="border rounded-lg px-3 py-2 text-sm w-full"
              maxLength={3}
            />
          )}
        </div>
      </section>

      {/* OCR / AI Provider */}
      <section className="bg-white rounded-xl p-5 shadow-sm space-y-3">
        <h2 className="font-semibold">OCR Provider</h2>
        <p className="text-xs text-gray-500">
          AI providers handle both OCR and transaction categorisation in a single call.
        </p>
        <select value={ocrProvider} onChange={(e) => setOcrProvider(e.target.value as AppSettings['ocr_provider'])}
          className="border rounded-lg px-3 py-2 text-sm w-full">
          <option value="tesseract">Tesseract (local, no AI categorisation)</option>
          <option value="anthropic">Claude (Anthropic)</option>
          <option value="openai">OpenAI Vision</option>
          <option value="gemini">Gemini (Google AI Studio)</option>
          <option value="vertex">Google Vertex AI</option>
        </select>
        {ocrProvider === 'anthropic' && (
          <input value={anthropicKey} onChange={(e) => setAnthropicKey(e.target.value)}
            placeholder={settings?.anthropic_api_key_set ? '••••••••• (set)' : 'Anthropic API key'}
            className="border rounded-lg px-3 py-2 text-sm w-full" type="password" />
        )}
        {ocrProvider === 'openai' && (
          <input value={openaiKey} onChange={(e) => setOpenaiKey(e.target.value)}
            placeholder={settings?.openai_api_key_set ? '••••••••• (set)' : 'OpenAI API key'}
            className="border rounded-lg px-3 py-2 text-sm w-full" type="password" />
        )}
        {ocrProvider === 'gemini' && (
          <input value={geminiKey} onChange={(e) => setGeminiKey(e.target.value)}
            placeholder={settings?.gemini_api_key_set ? '••••••••• (set)' : 'Gemini API key (AIza...)'}
            className="border rounded-lg px-3 py-2 text-sm w-full" type="password" />
        )}
        {ocrProvider === 'vertex' && (
          <>
            <input value={googleProjectId} onChange={(e) => setGoogleProjectId(e.target.value)}
              placeholder="Google Cloud Project ID" className="border rounded-lg px-3 py-2 text-sm w-full" />
            <input value={googleLocation} onChange={(e) => setGoogleLocation(e.target.value)}
              placeholder="Region (e.g. us-central1)" className="border rounded-lg px-3 py-2 text-sm w-full" />
            <p className="text-xs text-gray-500">Uses Application Default Credentials (GOOGLE_APPLICATION_CREDENTIALS env var).</p>
          </>
        )}
        {ocrProvider !== 'tesseract' && (
          <>
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium text-gray-700">Model</span>
              <button
                onClick={() => api.post('/settings/models/refresh', {}).then(() => qc.invalidateQueries({ queryKey: ['models'] }))}
                className="text-xs text-indigo-500 hover:underline"
                type="button"
              >
                ↻ Refresh list
              </button>
            </div>
            <select
              value={aiModel}
              onChange={(e) => {
                setAiModel(e.target.value);
                const found = ocrModels?.models?.find(m => m.model_id === e.target.value);
                if (found?.max_output_tokens) setMaxOutputTokens(String(found.max_output_tokens));
              }}
              className="border rounded-lg px-3 py-2 text-sm w-full"
            >
              <option value="">— select a model —</option>
              {ocrModels?.models?.map(m => (
                <option key={m.model_id} value={m.model_id}>
                  {m.display_name ?? m.model_id}
                  {m.max_output_tokens ? ` — ${m.max_output_tokens.toLocaleString()} tokens` : ' — limit unknown'}
                </option>
              ))}
            </select>
            <input
              type="number"
              min={256}
              value={maxOutputTokens}
              onChange={(e) => setMaxOutputTokens(e.target.value)}
              placeholder="Max output tokens (e.g. 8192)"
              className="border rounded-lg px-3 py-2 text-sm w-full"
            />
          </>
        )}
        <button
          onClick={() => settingsMutation.mutate({
            ocr_provider: ocrProvider,
            ...(ocrProvider === 'anthropic' && anthropicKey ? { anthropic_api_key: anthropicKey } : {}),
            ...(ocrProvider === 'openai' && openaiKey ? { openai_api_key: openaiKey } : {}),
            ...(ocrProvider === 'gemini' && geminiKey ? { gemini_api_key: geminiKey } : {}),
            ...(ocrProvider === 'vertex' && googleProjectId ? { google_project_id: googleProjectId } : {}),
            ...(ocrProvider === 'vertex' && googleLocation ? { google_location: googleLocation } : {}),
            ...(aiModel ? { ai_model: aiModel } : {}),
            ...(maxOutputTokens ? { max_output_tokens: Number(maxOutputTokens) } : {}),
          })}
          className="bg-indigo-600 text-white px-4 py-2 rounded-lg text-sm"
        >
          Save
        </button>
      </section>

      {/* Categories */}
      <section className="bg-white rounded-xl p-5 shadow-sm space-y-3">
        <h2 className="font-semibold">Categories</h2>
        <ul className="divide-y divide-gray-100">
          {categories.map((c) => (
            <React.Fragment key={c.id}>
              <li className="flex items-center justify-between py-2">
                <div className="flex items-center gap-2">
                  <span className="w-3 h-3 rounded-full inline-block" style={{ backgroundColor: c.color ?? undefined }} />
                  <span className="text-sm font-medium">{c.name}</span>
                </div>
                <button onClick={() => { if (confirm(`Delete "${c.name}"?`)) deleteCategory.mutate(c.id); }}
                  className="text-gray-400 hover:text-red-500">
                  <Trash2 size={15} />
                </button>
              </li>
              {(c.children ?? []).map((child) => (
                <li key={child.id} className="flex items-center justify-between py-1.5 pl-6">
                  <div className="flex items-center gap-2">
                    <span className="w-2.5 h-2.5 rounded-full inline-block" style={{ backgroundColor: child.color ?? undefined }} />
                    <span className="text-sm text-gray-600">{child.name}</span>
                  </div>
                  <button onClick={() => { if (confirm(`Delete "${child.name}"?`)) deleteCategory.mutate(child.id); }}
                    className="text-gray-400 hover:text-red-500">
                    <Trash2 size={14} />
                  </button>
                </li>
              ))}
            </React.Fragment>
          ))}
        </ul>
        <div className="flex flex-wrap gap-2 pt-2">
          <input value={newName} onChange={(e) => setNewName(e.target.value)}
            placeholder="New category name" className="border rounded-lg px-3 py-2 text-sm flex-1 min-w-32" />
          <select
            value={newParentId}
            onChange={(e) => setNewParentId(e.target.value)}
            className="border rounded-lg px-3 py-2 text-sm"
          >
            <option value="">Top-level</option>
            {categories.map((c) => (
              <option key={c.id} value={String(c.id)}>{c.name}</option>
            ))}
          </select>
          <input type="color" value={newColor} onChange={(e) => setNewColor(e.target.value)}
            className="border rounded-lg px-2 py-1 w-12 cursor-pointer" />
          <button
            onClick={() => newName && addCategory.mutate({ name: newName, color: newColor, parent_id: newParentId ? Number(newParentId) : null })}
            className="bg-indigo-600 text-white px-3 py-2 rounded-lg text-sm flex items-center gap-1"
          >
            <Plus size={15} /> Add
          </button>
        </div>
      </section>
    </div>
  );
}
