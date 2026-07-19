'use client';
import { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import type { AppSettings, SettingsPut, Category, CategoryCreate } from '@/lib/types';
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

  // OCR settings
  const { data: settings } = useQuery({
    queryKey: ['settings'],
    queryFn: () => api.get<AppSettings>('/settings'),
  });

  const [ocrProvider, setOcrProvider] = useState<AppSettings['ocr_provider']>('tesseract');
  const [anthropicKey, setAnthropicKey] = useState('');
  const [openaiKey, setOpenaiKey] = useState('');
  const [reviewBeforeCommit, setReviewBeforeCommit] = useState(true);
  const [homeCurrency, setHomeCurrency] = useState('');

  // AI categorization provider
  const [aiProvider, setAiProvider] = useState('anthropic');
  const [aiModel, setAiModel] = useState('');
  const [aiApiUrl, setAiApiUrl] = useState('');
  const [geminiKey, setGeminiKey] = useState('');
  const [googleProjectId, setGoogleProjectId] = useState('');
  const [googleLocation, setGoogleLocation] = useState('us-central1');

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
      if (settings.ai_provider) setAiProvider(settings.ai_provider);
      if (settings.ai_model) setAiModel(settings.ai_model);
      if (settings.ai_api_url) setAiApiUrl(settings.ai_api_url);
      if (settings.google_project_id) setGoogleProjectId(settings.google_project_id);
      if (settings.google_location) setGoogleLocation(settings.google_location);
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

  const addCategory = useMutation({
    mutationFn: (body: CategoryCreate) => api.post<Category>('/categories', body),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['categories'] }); setNewName(''); },
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
        </div>
      </section>

      {/* OCR provider */}
      <section className="bg-white rounded-xl p-5 shadow-sm space-y-3">
        <h2 className="font-semibold">OCR Provider</h2>
        <select value={ocrProvider} onChange={(e) => setOcrProvider(e.target.value as AppSettings['ocr_provider'])}
          className="border rounded-lg px-3 py-2 text-sm w-full">
          <option value="tesseract">Tesseract (local, private)</option>
          <option value="claude">Claude (Anthropic API)</option>
          <option value="openai">OpenAI Vision</option>
          <option value="gemini">Gemini (Google AI Studio)</option>
          <option value="vertex">Google Vertex AI</option>
        </select>
        {ocrProvider === 'claude' && (
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
        <button
          onClick={() => settingsMutation.mutate({
            ocr_provider: ocrProvider,
            ...(ocrProvider === 'claude' && anthropicKey ? { anthropic_api_key: anthropicKey } : {}),
            ...(ocrProvider === 'openai' && openaiKey ? { openai_api_key: openaiKey } : {}),
            ...(ocrProvider === 'gemini' && geminiKey ? { gemini_api_key: geminiKey } : {}),
            ...(ocrProvider === 'vertex' && googleProjectId ? { google_project_id: googleProjectId } : {}),
            ...(ocrProvider === 'vertex' && googleLocation ? { google_location: googleLocation } : {}),
          })}
          className="bg-indigo-600 text-white px-4 py-2 rounded-lg text-sm"
        >
          Save OCR Settings
        </button>
      </section>

      {/* AI Categorization */}
      <section className="bg-white rounded-xl p-5 shadow-sm space-y-3">
        <h2 className="font-semibold">AI Categorization Provider</h2>
        <select value={aiProvider} onChange={(e) => setAiProvider(e.target.value)}
          className="border rounded-lg px-3 py-2 text-sm w-full">
          <option value="anthropic">Claude (Anthropic)</option>
          <option value="openai">GPT-4o-mini (OpenAI)</option>
          <option value="gemini">Gemini (Google AI Studio)</option>
          <option value="vertex">Google Vertex AI</option>
          <option value="local">Local / Ollama</option>
        </select>
        {aiProvider === 'anthropic' && (
          <input value={anthropicKey} onChange={(e) => setAnthropicKey(e.target.value)}
            placeholder={settings?.anthropic_api_key_set ? '••••••••• (set)' : 'Anthropic API key (sk-ant-...)'}
            className="border rounded-lg px-3 py-2 text-sm w-full" type="password" />
        )}
        {aiProvider === 'openai' && (
          <input value={openaiKey} onChange={(e) => setOpenaiKey(e.target.value)}
            placeholder={settings?.openai_api_key_set ? '••••••••• (set)' : 'OpenAI API key (sk-...)'}
            className="border rounded-lg px-3 py-2 text-sm w-full" type="password" />
        )}
        {aiProvider === 'gemini' && (
          <input value={geminiKey} onChange={(e) => setGeminiKey(e.target.value)}
            placeholder={settings?.gemini_api_key_set ? '••••••••• (set)' : 'Gemini API key (AIza...)'}
            className="border rounded-lg px-3 py-2 text-sm w-full" type="password" />
        )}
        {aiProvider === 'vertex' && (
          <>
            <input value={googleProjectId} onChange={(e) => setGoogleProjectId(e.target.value)}
              placeholder="Google Cloud Project ID" className="border rounded-lg px-3 py-2 text-sm w-full" />
            <input value={googleLocation} onChange={(e) => setGoogleLocation(e.target.value)}
              placeholder="Region (e.g. us-central1)" className="border rounded-lg px-3 py-2 text-sm w-full" />
            <p className="text-xs text-gray-500">Uses Application Default Credentials (GOOGLE_APPLICATION_CREDENTIALS env var).</p>
          </>
        )}
        {aiProvider === 'local' && (
          <>
            <input value={aiApiUrl} onChange={(e) => setAiApiUrl(e.target.value)}
              placeholder="API URL (e.g. http://localhost:11434/v1)"
              className="border rounded-lg px-3 py-2 text-sm w-full" />
            <input value={aiModel} onChange={(e) => setAiModel(e.target.value)}
              placeholder="Model name (e.g. llama3, optional)"
              className="border rounded-lg px-3 py-2 text-sm w-full" />
          </>
        )}
        <button
          onClick={() => settingsMutation.mutate({
            ai_provider: aiProvider as SettingsPut['ai_provider'],
            ...(aiModel ? { ai_model: aiModel } : {}),
            ...(aiApiUrl ? { ai_api_url: aiApiUrl } : {}),
            ...(geminiKey ? { gemini_api_key: geminiKey } : {}),
            ...(googleProjectId ? { google_project_id: googleProjectId } : {}),
            ...(googleLocation ? { google_location: googleLocation } : {}),
            ...(aiProvider === 'anthropic' && anthropicKey ? { anthropic_api_key: anthropicKey } : {}),
            ...(aiProvider === 'openai' && openaiKey ? { openai_api_key: openaiKey } : {}),
          })}
          className="bg-indigo-600 text-white px-4 py-2 rounded-lg text-sm"
        >
          Save AI Settings
        </button>
      </section>

      {/* Categories */}
      <section className="bg-white rounded-xl p-5 shadow-sm space-y-3">
        <h2 className="font-semibold">Categories</h2>
        <ul className="divide-y divide-gray-100">
          {categories.map((c) => (
            <li key={c.id} className="flex items-center justify-between py-2">
              <div className="flex items-center gap-2">
                <span className="w-3 h-3 rounded-full inline-block" style={{ backgroundColor: c.color ?? undefined }} />
                <span className="text-sm">{c.name}</span>
              </div>
              <button onClick={() => { if (confirm(`Delete "${c.name}"?`)) deleteCategory.mutate(c.id); }}
                className="text-gray-400 hover:text-red-500">
                <Trash2 size={15} />
              </button>
            </li>
          ))}
        </ul>
        <div className="flex gap-2 pt-2">
          <input value={newName} onChange={(e) => setNewName(e.target.value)}
            placeholder="New category name" className="border rounded-lg px-3 py-2 text-sm flex-1" />
          <input type="color" value={newColor} onChange={(e) => setNewColor(e.target.value)}
            className="border rounded-lg px-2 py-1 w-12 cursor-pointer" />
          <button
            onClick={() => newName && addCategory.mutate({ name: newName, color: newColor })}
            className="bg-indigo-600 text-white px-3 py-2 rounded-lg text-sm flex items-center gap-1"
          >
            <Plus size={15} /> Add
          </button>
        </div>
      </section>
    </div>
  );
}
