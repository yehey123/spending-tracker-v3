'use client';
import { useEffect, useState } from 'react';
import { api } from '@/lib/api';

interface Session {
  session_id: string;
  device_name: string | null;
  created_at: string;
  expires_at: string;
  absolute_expires_at: string;
  is_current: boolean;
}

export default function DevicesPage() {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchSessions = async () => {
    setLoading(true);
    try {
      const data = await api.get<Session[]>('/auth/sessions');
      setSessions(data);
    } catch {
      setSessions([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchSessions(); }, []);

  const revoke = async (sessionId: string) => {
    try {
      await api.delete(`/auth/sessions/${sessionId}`);
    } catch {
      // 404 = already gone; ignore
    }
    fetchSessions();
  };

  if (loading) return <p style={{ padding: '2rem' }}>Loading sessions…</p>;

  return (
    <div style={{ padding: '2rem', maxWidth: '720px' }}>
      <h1 style={{ marginBottom: '0.5rem' }}>Active Sessions</h1>
      <p style={{ color: '#6b7280', marginBottom: '1.5rem' }}>
        These are all devices where you are currently logged in. Revoking a session
        logs out that device on its next request.
      </p>
      {sessions.length === 0 && <p>No active sessions found.</p>}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
        {sessions.map(s => (
          <div
            key={s.session_id}
            style={{
              border: `1px solid ${s.is_current ? '#2563eb' : '#e5e7eb'}`,
              borderRadius: '8px',
              padding: '1rem',
              background: s.is_current ? '#eff6ff' : 'white',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
              <div>
                <strong>{s.device_name ?? 'Unknown device'}</strong>
                {s.is_current && (
                  <span style={{
                    marginLeft: '0.5rem', fontSize: '0.75rem',
                    background: '#2563eb', color: 'white',
                    borderRadius: '4px', padding: '2px 6px',
                  }}>Current</span>
                )}
                <div style={{ fontSize: '0.85rem', color: '#6b7280', marginTop: '0.25rem' }}>
                  Expires: {new Date(s.expires_at).toLocaleString()}
                  {' · '}Session cap: {new Date(s.absolute_expires_at).toLocaleDateString()}
                </div>
              </div>
              <button
                onClick={() => revoke(s.session_id)}
                style={{
                  padding: '0.375rem 0.75rem',
                  background: s.is_current ? '#dc2626' : '#6b7280',
                  color: 'white',
                  border: 'none',
                  borderRadius: '4px',
                  cursor: 'pointer',
                  fontSize: '0.875rem',
                  flexShrink: 0,
                  marginLeft: '1rem',
                }}
              >
                {s.is_current ? 'Log out' : 'Revoke'}
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
