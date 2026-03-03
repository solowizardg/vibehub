import { Eye, MousePointer2 } from 'lucide-react';
import { cn } from '@/lib/cn';
import type { PreviewMode } from '@/types/websocket';

interface PreviewModeSwitcherProps {
	mode: PreviewMode;
	onModeChange: (mode: PreviewMode) => void;
	disabled?: boolean;
}

export function PreviewModeSwitcher({ mode, onModeChange, disabled = false }: PreviewModeSwitcherProps) {
	return (
		<div
			className={cn(
				'inline-flex items-center rounded-lg bg-surface-secondary p-1 gap-1',
				disabled && 'opacity-50 cursor-not-allowed',
			)}
		>
			<button
				onClick={() => onModeChange('preview')}
				disabled={disabled || mode === 'preview'}
				className={cn(
					'flex items-center gap-2 px-3 py-1.5 rounded-md text-sm font-medium transition-all',
					mode === 'preview'
						? 'bg-surface text-text-primary shadow-sm'
						: 'text-text-secondary hover:text-text-primary hover:bg-surface-tertiary',
					disabled && 'cursor-not-allowed',
				)}
				title="Preview mode - normal browsing and interaction"
			>
				<Eye size={14} />
				<span>Preview</span>
			</button>
			<button
				onClick={() => onModeChange('edit')}
				disabled={disabled || mode === 'edit'}
				className={cn(
					'flex items-center gap-2 px-3 py-1.5 rounded-md text-sm font-medium transition-all',
					mode === 'edit'
						? 'bg-brand text-white shadow-sm'
						: 'text-text-secondary hover:text-text-primary hover:bg-surface-tertiary',
					disabled && 'cursor-not-allowed',
				)}
				title="Edit mode - click elements to select for modification"
			>
				<MousePointer2 size={14} />
				<span>Edit</span>
			</button>
		</div>
	);
}
