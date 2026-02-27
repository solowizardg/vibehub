import type { ChatMessage } from '@/hooks/use-chat';
import { useAutoScroll } from '@/hooks/use-auto-scroll';
import { AIMessage } from './ai-message';
import { SystemMessage } from './system-message';
import { UserMessage } from './user-message';

interface MessagesProps {
	messages: ChatMessage[];
}

export function Messages({ messages }: MessagesProps) {
	const { ref } = useAutoScroll<HTMLDivElement>([messages]);

	if (messages.length === 0) {
		return (
			<div className="flex min-h-0 flex-1 items-center justify-center text-text-secondary">
				<p>Start a conversation to begin generating code.</p>
			</div>
		);
	}

	return (
		<div ref={ref} className="min-h-0 flex-1 overflow-y-auto px-4">
			{messages.map((msg) => {
				if (msg.role === 'user') return <UserMessage key={msg.id} content={msg.content} />;
				if (msg.role === 'system') return <SystemMessage key={msg.id} content={msg.content} />;
				return <AIMessage key={msg.id} content={msg.content} isStreaming={msg.isStreaming} />;
			})}
		</div>
	);
}
