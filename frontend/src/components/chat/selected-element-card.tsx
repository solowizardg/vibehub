import { X, FileCode, Component, MousePointer } from 'lucide-react';
import type { SelectedElement } from '@/types/websocket';

interface SelectedElementCardProps {
	element: SelectedElement;
	onClear: () => void;
}

export function SelectedElementCard({ element, onClear }: SelectedElementCardProps) {
	const componentName = element.component || element.tagName;
	const fileName = element.filePath ? element.filePath.split('/').pop() : 'unknown';

	return (
		<div className="rounded-lg border border-brand/30 bg-brand/5 p-3 animate-in fade-in slide-in-from-bottom-2">
			<div className="flex items-start justify-between gap-2">
				<div className="flex items-center gap-2">
					<div className="flex h-6 w-6 items-center justify-center rounded bg-brand/20">
						<MousePointer size={14} className="text-brand" />
					</div>
					<span className="text-xs font-medium text-brand">Selected Component</span>
				</div>
				<button
					onClick={onClear}
					className="rounded p-1 text-text-secondary hover:bg-surface-secondary hover:text-text-primary"
					title="Clear selection"
				>
					<X size={14} />
				</button>
			</div>

			<div className="mt-2 space-y-1.5">
				<div className="flex items-center gap-2 text-xs">
					<Component size={12} className="text-text-muted" />
					<span className="font-medium text-text-secondary">Component:</span>
					<span className="font-mono text-text-primary">{componentName}</span>
				</div>

				{element.filePath && (
					<div className="flex items-center gap-2 text-xs">
						<FileCode size={12} className="text-text-muted" />
						<span className="font-medium text-text-secondary">File:</span>
						<span className="truncate font-mono text-text-primary max-w-[200px]" title={element.filePath}>
							{fileName}
						</span>
					</div>
				)}

				{element.textContent && (
					<div className="mt-1.5 truncate text-xs text-text-muted italic">
						"{element.textContent.slice(0, 60)}{element.textContent.length > 60 ? '...' : ''}"
					</div>
				)}
			</div>

			<div className="mt-2 text-xs text-text-secondary">
				Describe how to modify this component below...
			</div>
		</div>
	);
}
