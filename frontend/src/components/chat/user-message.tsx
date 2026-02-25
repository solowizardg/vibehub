import { cn } from '@/lib/cn';

interface UserMessageProps {
	content: string;
}

export function UserMessage({ content }: UserMessageProps) {
	return (
		<div className="flex gap-3 py-3">
			<div className="flex size-8 shrink-0 items-center justify-center rounded-full bg-brand text-sm font-semibold text-white">U</div>
			<div className={cn('rounded-xl bg-surface-tertiary px-4 py-2.5 text-sm leading-relaxed text-text-primary')}>{content}</div>
		</div>
	);
}
