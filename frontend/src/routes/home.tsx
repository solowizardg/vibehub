import { type KeyboardEvent, useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router';
import { ArrowRight, Clock3, Sparkles } from 'lucide-react';
import { apiClient } from '@/lib/api-client';
import { cn } from '@/lib/cn';
import type { SessionInfo } from '@/types/api';

const TEMPLATES = [
	{ id: 'react-vite', label: 'React + Vite' },
	{ id: 'nextjs', label: 'Next.js' },
	{ id: 'vue-vite', label: 'Vue + Vite' },
];

export function HomePage() {
	const navigate = useNavigate();
	const [query, setQuery] = useState('');
	const [template, setTemplate] = useState('react-vite');
	const [loading, setLoading] = useState(false);
	const [sessions, setSessions] = useState<SessionInfo[]>([]);
	const [loadingSessions, setLoadingSessions] = useState(true);

	const loadSessions = useCallback(async () => {
		setLoadingSessions(true);
		try {
			const list = await apiClient.getSessions();
			setSessions(list);
		} catch (err) {
			console.error('Failed to load sessions:', err);
		} finally {
			setLoadingSessions(false);
		}
	}, []);

	useEffect(() => {
		void loadSessions();
	}, [loadSessions]);

	const handleSubmit = async () => {
		const trimmed = query.trim();
		if (!trimmed || loading) return;
		setLoading(true);
		try {
			const res = await apiClient.createSession(trimmed, template);
			navigate(`/chat/${res.session_id}`, { state: { query: trimmed, template } });
		} catch (err) {
			console.error('Failed to create session:', err);
			setLoading(false);
		}
	};

	const openHistorySession = (sessionId: string) => {
		navigate(`/chat/${sessionId}`, { state: { rebuildSandbox: true } });
	};

	const handleKeyDown = (e: KeyboardEvent) => {
		if (e.key === 'Enter' && !e.shiftKey) {
			e.preventDefault();
			handleSubmit();
		}
	};

	return (
		<div className="flex flex-1 flex-col items-center overflow-y-auto px-4 py-10">
			<div className="mb-8 flex flex-col items-center gap-3">
				<div className="flex size-14 items-center justify-center rounded-2xl bg-brand/10">
					<Sparkles size={28} className="text-brand" />
				</div>
				<h1 className="text-3xl font-bold text-text-primary">What do you want to build?</h1>
				<p className="text-sm text-text-secondary">Describe your app and VibeHub will generate it for you.</p>
			</div>

			<div className="mb-4 flex gap-2">
				{TEMPLATES.map((t) => (
					<button
						key={t.id}
						onClick={() => setTemplate(t.id)}
						className={cn(
							'rounded-lg border px-3 py-1.5 text-xs transition-colors',
							template === t.id
								? 'border-brand bg-brand/10 text-brand'
								: 'border-border text-text-secondary hover:border-text-muted hover:text-text-primary',
						)}
					>
						{t.label}
					</button>
				))}
			</div>

			<div className="w-full max-w-2xl">
				<div className="flex items-end gap-2 rounded-xl border border-border bg-surface-secondary p-3 shadow-lg shadow-black/20 focus-within:border-brand/50">
					<textarea
						value={query}
						onChange={(e) => setQuery(e.target.value)}
						onKeyDown={handleKeyDown}
						placeholder="Build a todo app with dark mode, user authentication, and local storage..."
						rows={3}
						className="flex-1 resize-none bg-transparent text-sm text-text-primary outline-none placeholder:text-text-muted"
					/>
					<button
						onClick={handleSubmit}
						disabled={!query.trim() || loading}
						className={cn(
							'flex size-9 shrink-0 items-center justify-center rounded-lg bg-brand text-white transition-colors hover:bg-brand-dark',
							(!query.trim() || loading) && 'cursor-not-allowed opacity-40',
						)}
					>
						{loading ? <div className="size-4 animate-spin rounded-full border-2 border-white/30 border-t-white" /> : <ArrowRight size={18} />}
					</button>
				</div>
			</div>

			<div className="mt-8 w-full max-w-2xl rounded-xl border border-border bg-surface-secondary p-4">
				<div className="mb-3 flex items-center gap-2">
					<Clock3 size={14} className="text-text-secondary" />
					<h2 className="text-sm font-semibold text-text-primary">History Projects</h2>
				</div>

				{loadingSessions ? (
					<div className="text-xs text-text-secondary">Loading...</div>
				) : sessions.length === 0 ? (
					<div className="text-xs text-text-secondary">No project history yet.</div>
				) : (
					<div className="max-h-80 space-y-2 overflow-y-auto pr-1">
						{sessions.map((session) => (
							<div key={session.id} className="flex items-center justify-between rounded-lg border border-border bg-surface p-3">
								<div className="min-w-0">
									<div className="truncate text-sm font-medium text-text-primary">{session.title}</div>
									<div className="mt-1 text-xs text-text-secondary">
										Status: {session.status} - Updated: {new Date(session.updated_at).toLocaleString()}
									</div>
								</div>
								<button
									onClick={() => openHistorySession(session.id)}
									className="ml-3 shrink-0 rounded-md border border-border px-2.5 py-1.5 text-xs text-text-primary transition-colors hover:border-brand hover:text-brand"
								>
									Continue
								</button>
							</div>
						))}
					</div>
				)}
			</div>
		</div>
	);
}
