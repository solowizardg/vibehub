import { useEffect, useRef, useState } from 'react';
import { ExternalLink, Loader2, RefreshCw, MousePointer2 } from 'lucide-react';
import { cn } from '@/lib/cn';
import type { SelectedElement } from '@/types/websocket';

interface PreviewIframeProps {
	url: string | null;
	onElementSelect?: (element: SelectedElement) => void;
	selectionEnabled?: boolean;
}

export function PreviewIframe({ url, onElementSelect, selectionEnabled = true }: PreviewIframeProps) {
	const [loading, setLoading] = useState(true);
	const [error, setError] = useState(false);
	const [retryKey, setRetryKey] = useState(0);
	const [overlayReady, setOverlayReady] = useState(false);
	const iframeRef = useRef<HTMLIFrameElement>(null);

	// Enable/disable selection in iframe
	useEffect(() => {
		if (!iframeRef.current?.contentWindow || !overlayReady) return;

		const message = selectionEnabled
			? { type: 'VIBEHUB_ENABLE_SELECTION' }
			: { type: 'VIBEHUB_DISABLE_SELECTION' };

		iframeRef.current.contentWindow.postMessage(message, '*');
	}, [selectionEnabled, overlayReady]);

	// Listen for messages from iframe
	useEffect(() => {
		const handleMessage = (event: MessageEvent) => {
			// Only accept messages from our iframe
			if (event.source !== iframeRef.current?.contentWindow) return;

			switch (event.data?.type) {
				case 'VIBEHUB_OVERLAY_READY':
					setOverlayReady(true);
					// Enable selection by default when overlay is ready
					if (selectionEnabled) {
						event.source?.postMessage({ type: 'VIBEHUB_ENABLE_SELECTION' }, '*');
					}
					break;

				case 'VIBEHUB_ELEMENT_SELECTED':
					if (event.data.element) {
						onElementSelect?.(event.data.element);
					}
					break;
			}
		};

		window.addEventListener('message', handleMessage);
		return () => window.removeEventListener('message', handleMessage);
	}, [onElementSelect, selectionEnabled]);

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
					{selectionEnabled && (
						<div className="flex items-center gap-1 px-2 py-0.5 rounded bg-surface-secondary text-xs text-text-secondary">
							<MousePointer2 size={12} />
							<span>Click to select</span>
						</div>
					)}
					<button onClick={() => { setRetryKey((k) => k + 1); setLoading(true); setError(false); setOverlayReady(false); }} className="rounded p-1 text-text-secondary hover:bg-surface-tertiary hover:text-text-primary" title="Reload">
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
							onClick={() => { setRetryKey((k) => k + 1); setLoading(true); setError(false); setOverlayReady(false); }}
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
