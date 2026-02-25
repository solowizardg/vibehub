import Markdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Bot } from 'lucide-react';
import { cn } from '@/lib/cn';

interface AIMessageProps {
	content: string;
	isStreaming?: boolean;
}

export function AIMessage({ content, isStreaming }: AIMessageProps) {
	return (
		<div className="flex gap-3 py-3">
			<div className="flex size-8 shrink-0 items-center justify-center rounded-full bg-brand/20 text-brand">
				<Bot size={18} />
			</div>
			<div className={cn('min-w-0 flex-1 text-sm leading-relaxed text-text-primary', '[&_pre]:overflow-x-auto [&_pre]:rounded-lg [&_pre]:bg-surface-secondary [&_pre]:p-3 [&_pre]:text-xs', '[&_code]:rounded [&_code]:bg-surface-secondary [&_code]:px-1.5 [&_code]:py-0.5 [&_code]:text-xs', '[&_p]:mb-2 [&_ul]:mb-2 [&_ul]:ml-4 [&_ul]:list-disc [&_ol]:mb-2 [&_ol]:ml-4 [&_ol]:list-decimal')}>
				<Markdown remarkPlugins={[remarkGfm]}>{content}</Markdown>
				{isStreaming && <span className="ml-0.5 inline-block h-4 w-1.5 animate-pulse bg-brand" />}
			</div>
		</div>
	);
}
