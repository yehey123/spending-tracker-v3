import { Preferences } from '@capacitor/preferences';

const TOKEN_KEY = 'spending_tracker_jwt';

export async function getCapacitorToken(): Promise<string | null> {
  const { value } = await Preferences.get({ key: TOKEN_KEY });
  return value;
}

export async function setCapacitorToken(token: string): Promise<void> {
  await Preferences.set({ key: TOKEN_KEY, value: token });
}

export async function clearCapacitorToken(): Promise<void> {
  await Preferences.remove({ key: TOKEN_KEY });
}

export async function capacitorLogout(baseUrl: string): Promise<void> {
  await clearCapacitorToken();
  await fetch(`${baseUrl}/auth/logout`, {
    method: 'POST',
    credentials: 'include',
  }).catch(() => {});
}
