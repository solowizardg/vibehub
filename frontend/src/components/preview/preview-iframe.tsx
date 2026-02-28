import { useState, useRef, useEffect } from 'react';
import { ExternalLink, Loader2, RefreshCw } from 'lucide-react';
import { cn } from '@/lib/cn';

interface PreviewIframeProps {
	url: string | null;
	onElementSelect?: (info: {
		component: string;
		filePath: string;
		elementId?: string;
	}) => void;
}

export function PreviewIframe({ url, onElementSelect }: PreviewIframeProps) {
	const [loading, setLoading] = useState(true);
	const [error, setError] = useState(false);
	const [retryKey, setRetryKey] = useState(0);
	const iframeRef = useRef<HTMLIFrameElement>(null);

	// Enable edit mode when overlay is ready
	useEffect(() => {
		if (loading || !url) return;

		// Wait for overlay_ready message from iframe, then enable edit mode
		const handleOverlayReady = (e: MessageEvent) => {
			if (e.data?.type === 'overlay_ready') {
				console.log('[PreviewIframe] Received overlay_ready, enabling edit mode');
				const iframe = iframeRef.current;
				if (iframe?.contentWindow) {
					iframe.contentWindow.postMessage(
						{ type: 'set_edit_mode', enabled: true },
						'*'
					);
				}
			}
		};

		window.addEventListener('message', handleOverlayReady);

		// Fallback: try enabling edit mode after 2 seconds if overlay_ready not received
		const fallbackTimer = setTimeout(() => {
			console.log('[PreviewIframe] Fallback: enabling edit mode after timeout');
			const iframe = iframeRef.current;
			if (iframe?.contentWindow) {
				iframe.contentWindow.postMessage(
					{ type: 'set_edit_mode', enabled: true },
					'*'
				);
			}
		}, 2000);

		return () => {
			window.removeEventListener('message', handleOverlayReady);
			clearTimeout(fallbackTimer);
		};
	}, [loading, url]);

	// Listen for element selection from iframe
	useEffect(() => {
		const handleMessage = (e: MessageEvent) => {
			if (e.data?.type === 'element_selected') {
				console.log('[PreviewIframe] Element selected:', e.data);
				onElementSelect?.(e.data);
			}
		};
		window.addEventListener('message', handleMessage);
		return () => window.removeEventListener('message', handleMessage);
	}, [onElementSelect]);

	if (!url) {
		return (
			<div className="flex flex-1 flex-col items-center justify-center gap-3 text-text-secondary">
				<Loader2 size={24} className="animate-spin text-text-muted" />
				<p className="text-sm">Waiting for preview deployment...</p>
			</div>
		);
	}

	return (
		<div className="flex flex-1 flex-col overflow-hidden">
			<div className="flex items-center justify-between border-b border-border px-3 py-1.5">
				<div className="flex items-center gap-2 overflow-hidden">
					<span className="truncate text-xs text-text-secondary">{url}</span>
				</div>
				<div className="flex items-center gap-1">
					<button onClick={() => { setRetryKey((k) => k + 1); setLoading(true); setError(false); }} className="rounded p-1 text-text-secondary hover:bg-surface-tertiary hover:text-text-primary" title="Reload">
						<RefreshCw size={14} />
					</button>
					<a href={url} target="_blank" rel="noopener noreferrer" className="rounded p-1 text-text-secondary hover:bg-surface-tertiary hover:text-text-primary" title="Open in new tab">
						<ExternalLink size={14} />
					</a>
				</div>
			</div>
			<div className="relative flex-1">
				{loading && !error && (
					<div className="absolute inset-0 z-10 flex items-center justify-center bg-surface">
						<Loader2 size={24} className="animate-spin text-brand" />
					</div>
				)}
				{error && (
					<div className="absolute inset-0 z-10 flex flex-col items-center justify-center gap-3 bg-surface">
						<p className="text-sm text-error">Failed to load preview.</p>
						<button
							onClick={() => { setRetryKey((k) => k + 1); setLoading(true); setError(false); }}
							className="rounded-lg bg-brand px-3 py-1.5 text-xs text-white hover:bg-brand-dark"
						>
							Retry
						</button>
					</div>
				)}
				<iframe
					ref={iframeRef}
					key={retryKey}
					src={url}
					className={cn('h-full w-full border-0', loading && 'opacity-0')}
					onLoad={() => setLoading(false)}
					onError={() => { setLoading(false); setError(true); }}
					sandbox="allow-scripts allow-same-origin allow-forms allow-popups"
					title="Preview"
				/>
			</div>
		</div>
	);
}
