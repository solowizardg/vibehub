import type { CreateSessionResponse, SessionDetail, SessionInfo } from '@/types/api';

const BASE_URL = '';

async function request<T>(path: string, options?: RequestInit): Promise<T> {
	const res = await fetch(`${BASE_URL}${path}`, {
		headers: { 'Content-Type': 'application/json' },
		...options,
	});
	if (!res.ok) {
		throw new Error(`API error: ${res.status} ${res.statusText}`);
	}
	return res.json();
}

export const apiClient = {
	createSession(query: string, template = 'react-vite'): Promise<CreateSessionResponse> {
		return request('/api/sessions', {
			method: 'POST',
			body: JSON.stringify({ query, template }),
		});
	},

	getSessions(): Promise<SessionInfo[]> {
		return request('/api/sessions');
	},

	getSession(sessionId: string): Promise<SessionDetail> {
		return request(`/api/sessions/${sessionId}`);
	},
};
