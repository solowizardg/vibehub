import { Activity, CheckCircle2 } from 'lucide-react';
import { cn } from '@/lib/cn';

interface SystemMessageProps {
	content: string;
}

export function SystemMessage({ content }: SystemMessageProps) {
	const isSuccess =
		content.toLowerCase().includes('completed') ||
		content.toLowerCase().includes('ready') ||
		content.toLowerCase().includes('validated');

	return (
		<div className="flex items-start gap-2 py-2">
			<div
				className={cn(
					'mt-0.5 flex size-5 shrink-0 items-center justify-center rounded-full border',
					isSuccess ? 'border-success/40 bg-success/10 text-success' : 'border-border bg-surface-tertiary text-text-muted',
				)}
			>
				{isSuccess ? <CheckCircle2 size={12} /> : <Activity size={12} />}
			</div>
			<div className="rounded-lg border border-border/70 bg-surface-secondary px-3 py-1.5 text-xs leading-relaxed text-text-secondary">
				{content}
			</div>
		</div>
	);
}
