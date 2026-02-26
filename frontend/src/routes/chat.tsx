import { useEffect, useState } from 'react';
import { useLocation, useParams } from 'react-router';
import { Code, Eye, Play } from 'lucide-react';
import { useChat } from '@/hooks/use-chat';
import { Messages } from '@/components/chat/messages';
import { ChatInput } from '@/components/chat/chat-input';
import { BlueprintCard } from '@/components/blueprint/blueprint-card';
import { EditorPanel } from '@/components/editor/editor-panel';
import { PreviewIframe } from '@/components/preview/preview-iframe';
import { PhaseTimeline } from '@/components/timeline/phase-timeline';
import { ActivityPanel } from '@/components/activity/activity-panel';
import { cn } from '@/lib/cn';

type ViewTab = 'editor' | 'preview';

export function ChatPage() {
	const { chatId } = useParams<{ chatId: string }>();
	const location = useLocation();
	const [activeTab, setActiveTab] = useState<ViewTab>('editor');
	const [initialized, setInitialized] = useState(false);

	const {
		messages,
		files,
		phases,
		blueprint,
		isGenerating,
		previewUrl,
		connectionState,
		activityLogs,
		sendMessage,
		startGeneration,
		stopGeneration,
		initSession,
		clearActivityLogs,
	} = useChat(chatId);

	useEffect(() => {
		if (initialized || connectionState !== 'connected') return;

		const state = location.state as { query?: string; template?: string } | null;
		if (state?.query?.trim()) {
			initSession(state.query, state.template, false);
			setTimeout(() => startGeneration(state.query, state.template), 500);
		} else {
			initSession(undefined, state?.template, true);
		}
		setInitialized(true);
	}, [connectionState, initialized, initSession, location.state, startGeneration]);

	const tabs: { id: ViewTab; label: string; icon: typeof Code }[] = [
		{ id: 'editor', label: 'Editor', icon: Code },
		{ id: 'preview', label: 'Preview', icon: Eye },
	];

	return (
		<div className="flex flex-1 overflow-hidden">
			{/* Left panel: messages */}
			<div className="flex w-full max-w-lg flex-col border-r border-border">
				<Messages messages={messages} />
				{blueprint && <BlueprintCard blueprint={blueprint} />}
				<PhaseTimeline phases={phases} />
				<ChatInput onSend={sendMessage} onStop={stopGeneration} isGenerating={isGenerating} placeholder={isGenerating ? 'Send a suggestion...' : 'Ask a follow-up question...'} />
			</div>

			{/* Right panel: editor / preview + activity */}
			<div className="flex flex-1 flex-col overflow-hidden">
				{/* Tab bar */}
				<div className="flex shrink-0 items-center gap-1 border-b border-border px-3">
					{tabs.map((tab) => (
						<button
							key={tab.id}
							onClick={() => setActiveTab(tab.id)}
							className={cn(
								'flex items-center gap-1.5 border-b-2 px-3 py-2 text-xs font-medium transition-colors',
								activeTab === tab.id ? 'border-brand text-brand' : 'border-transparent text-text-secondary hover:text-text-primary',
							)}
						>
							<tab.icon size={14} />
							{tab.label}
						</button>
					))}

					{/* Connection indicator */}
					<div className="ml-auto flex items-center gap-1.5">
						{isGenerating && (
							<span className="flex items-center gap-1 text-xs text-brand">
								<Play size={10} className="fill-brand" />
								Generating
							</span>
						)}
						<div className={cn('size-1.5 rounded-full', connectionState === 'connected' ? 'bg-success' : connectionState === 'connecting' ? 'bg-warning' : 'bg-error')} title={connectionState} />
					</div>
				</div>

				{/* Tab content (upper) */}
				<div className="flex min-h-0 flex-1 overflow-hidden">
					{activeTab === 'editor' ? <EditorPanel files={files} /> : <PreviewIframe url={previewUrl} />}
				</div>

				{/* Activity panel (lower) */}
				<ActivityPanel logs={activityLogs} onClear={clearActivityLogs} />
			</div>
		</div>
	);
}
