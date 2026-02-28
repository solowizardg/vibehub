import { useEffect, useState } from 'react';
import { useLocation, useParams } from 'react-router';
import { Code, Eye, FolderTree, Play } from 'lucide-react';
import { useChat } from '@/hooks/use-chat';
import { Messages } from '@/components/chat/messages';
import { ChatInput } from '@/components/chat/chat-input';
import { BlueprintCard } from '@/components/blueprint/blueprint-card';
import { EditorPanel } from '@/components/editor/editor-panel';
import { PreviewIframe } from '@/components/preview/preview-iframe';
import { ActivityPanel } from '@/components/activity/activity-panel';
import { cn } from '@/lib/cn';

type ViewTab = 'editor' | 'preview' | 'blueprint';

export function ChatPage() {
	const { chatId } = useParams<{ chatId: string }>();
	const location = useLocation();
	const readOnlyFromQuery = new URLSearchParams(location.search).get('readonly') === '1';
	const locationState = (location.state as { query?: string; template?: string; readonly?: boolean; rebuildSandbox?: boolean } | null) ?? null;
	const readOnly = readOnlyFromQuery || locationState?.readonly === true;
	const [activeTab, setActiveTab] = useState<ViewTab>('editor');
	const [initialized, setInitialized] = useState(false);

	const {
		messages,
		files,
		blueprint,
		blueprintMarkdown,
		isGenerating,
		previewUrl,
		connectionState,
		activityLogs,
		sendMessage,
		startGeneration,
		stopGeneration,
		initSession,
		clearActivityLogs,
		editFile,
		selectedElement,
		handleElementSelect,
		clearElementSelection,
	} = useChat(chatId, { readOnly });

	useEffect(() => {
		if (initialized || connectionState !== 'connected') return;

		if (readOnly) {
			initSession(undefined, locationState?.template, true, true, true);
		} else if (locationState?.query?.trim()) {
			initSession(locationState.query, locationState.template, false, false, false);
			setTimeout(() => startGeneration(locationState.query, locationState.template), 500);
		} else {
			initSession(undefined, locationState?.template, true, false, locationState?.rebuildSandbox === true);
		}
		setInitialized(true);
	}, [connectionState, initialized, initSession, locationState, readOnly, startGeneration]);

	const tabs: { id: ViewTab; label: string; icon: typeof Code }[] = [
		{ id: 'editor', label: 'Editor', icon: Code },
		{ id: 'preview', label: 'Preview', icon: Eye },
		{ id: 'blueprint', label: 'Blueprint', icon: FolderTree },
	];

	return (
		<div className="flex flex-1 overflow-hidden">
			{/* Left panel: messages */}
			<div className="flex min-h-0 w-full max-w-lg flex-col border-r border-border">
				<Messages messages={messages} />
				<ChatInput
					onSend={sendMessage}
					onStop={stopGeneration}
					isGenerating={isGenerating}
					disabled={readOnly}
					placeholder={
						readOnly
							? 'History project is read-only. Create a new project to regenerate code.'
							: isGenerating
								? 'Send a suggestion...'
								: selectedElement
									? `Describe changes for ${selectedElement.component}...`
									: 'Ask a follow-up question...'
					}
					selectedComponent={selectedElement}
					onClearSelection={clearElementSelection}
				/>
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
						{isGenerating && !readOnly && (
							<span className="flex items-center gap-1 text-xs text-brand">
								<Play size={10} className="fill-brand" />
								Generating
							</span>
						)}
						{readOnly && <span className="text-xs text-text-secondary">Read-only</span>}
						<div className={cn('size-1.5 rounded-full', connectionState === 'connected' ? 'bg-success' : connectionState === 'connecting' ? 'bg-warning' : 'bg-error')} title={connectionState} />
					</div>
				</div>

				{/* Tab content (upper) */}
				<div className="flex min-h-0 flex-1 overflow-hidden">
					{activeTab === 'editor' && <EditorPanel files={files} readOnly={readOnly} onEditFile={editFile} />}
					{activeTab === 'preview' && (
						<PreviewIframe
							url={previewUrl}
							onElementSelect={handleElementSelect}
						/>
					)}
					{activeTab === 'blueprint' && (
						<div className="flex min-h-0 flex-1 overflow-y-auto bg-surface px-4 py-4">
							<div className="mx-auto w-full max-w-5xl">
								{blueprint ? (
									<BlueprintCard blueprint={blueprint} blueprintMarkdown={blueprintMarkdown} />
								) : (
									<div className="rounded-xl border border-border bg-surface-secondary p-6 text-sm text-text-secondary">
										Blueprint is not available yet. Start generation to create it.
									</div>
								)}
							</div>
						</div>
					)}
				</div>

				{/* Activity panel (lower) */}
				<ActivityPanel logs={activityLogs} onClear={clearActivityLogs} />
			</div>
		</div>
	);
}
