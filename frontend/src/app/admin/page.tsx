'use client';
import { useEffect, useState } from 'react';

interface AdminUser {
  id: string;
  email: string;
  display_name: string | null;
  is_admin: boolean;
  is_active: boolean;
  created_at: string;
}

export default function AdminPage() {
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchUsers = async () => {
    try {
      const res = await fetch('/api/admin/users', { credentials: 'include' });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setUsers(data.users);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchUsers(); }, []);

  const toggleActive = async (userId: string, isActive: boolean) => {
    const action = isActive ? 'deactivate' : 'reactivate';
    await fetch(`/api/admin/users/${userId}/${action}`, {
      method: 'POST',
      credentials: 'include',
    });
    fetchUsers();
  };

  if (loading) return <p>Loading users…</p>;
  if (error) return <p style={{ color: 'red' }}>Error: {error}</p>;

  return (
    <div style={{ padding: '2rem' }}>
      <h1>User Administration</h1>
      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <thead>
          <tr>
            {['Email', 'Display Name', 'Admin', 'Active', 'Joined', 'Actions'].map(h => (
              <th key={h} style={{ textAlign: 'left', padding: '0.5rem', borderBottom: '1px solid #ccc' }}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {users.map(u => (
            <tr key={u.id}>
              <td style={{ padding: '0.5rem' }}>{u.email}</td>
              <td style={{ padding: '0.5rem' }}>{u.display_name ?? '—'}</td>
              <td style={{ padding: '0.5rem' }}>{u.is_admin ? '✓' : ''}</td>
              <td style={{ padding: '0.5rem' }}>{u.is_active ? 'Active' : 'Deactivated'}</td>
              <td style={{ padding: '0.5rem' }}>{new Date(u.created_at).toLocaleDateString()}</td>
              <td style={{ padding: '0.5rem' }}>
                <button
                  onClick={() => toggleActive(u.id, u.is_active)}
                  style={{
                    padding: '0.25rem 0.75rem',
                    background: u.is_active ? '#dc2626' : '#16a34a',
                    color: 'white',
                    border: 'none',
                    borderRadius: '4px',
                    cursor: 'pointer',
                  }}
                >
                  {u.is_active ? 'Deactivate' : 'Reactivate'}
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
