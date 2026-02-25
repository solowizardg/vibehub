import type { ChatMessage } from '@/hooks/use-chat';
import { useAutoScroll } from '@/hooks/use-auto-scroll';
import { AIMessage } from './ai-message';
import { UserMessage } from './user-message';

interface MessagesProps {
	messages: ChatMessage[];
}

export function Messages({ messages }: MessagesProps) {
	const { ref } = useAutoScroll<HTMLDivElement>([messages]);

	if (messages.length === 0) {
		return (
			<div className="flex flex-1 items-center justify-center text-text-secondary">
				<p>Start a conversation to begin generating code.</p>
			</div>
		);
	}

	return (
		<div ref={ref} className="flex-1 overflow-y-auto px-4">
			{messages.map((msg) =>
				msg.role === 'user' ? <UserMessage key={msg.id} content={msg.content} /> : <AIMessage key={msg.id} content={msg.content} isStreaming={msg.isStreaming} />,
			)}
		</div>
	);
}
