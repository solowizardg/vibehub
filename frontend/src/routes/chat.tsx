import { useEffect, useState, useRef, useCallback } from 'react';
import { useLocation, useParams } from 'react-router';
import { Code, Eye, FolderTree, Play, PanelLeft } from 'lucide-react';
import { useChat } from '@/hooks/use-chat';
import { Messages } from '@/components/chat/messages';
import { ChatInput } from '@/components/chat/chat-input';
import { BlueprintCard } from '@/components/blueprint/blueprint-card';
import { EditorPanel } from '@/components/editor/editor-panel';
import { PreviewIframe } from '@/components/preview/preview-iframe';
import { ActivityPanel } from '@/components/activity/activity-panel';
import { cn } from '@/lib/cn';

type ViewTab = 'editor' | 'preview' | 'blueprint';

const MIN_PANEL_WIDTH = 280;
const MAX_PANEL_WIDTH = 600;
const COLLAPSED_WIDTH = 48;
const DEFAULT_WIDTH = 384; // w-96 = 24rem = 384px

export function ChatPage() {
	const { chatId } = useParams<{ chatId: string }>();
	const location = useLocation();
	const readOnlyFromQuery = new URLSearchParams(location.search).get('readonly') === '1';
	const locationState = (location.state as { query?: string; template?: string; readonly?: boolean; rebuildSandbox?: boolean } | null) ?? null;
	const readOnly = readOnlyFromQuery || locationState?.readonly === true;
	const [activeTab, setActiveTab] = useState<ViewTab>('editor');
	const [initialized, setInitialized] = useState(false);

	// Sidebar state
	const [panelWidth, setPanelWidth] = useState(() => {
		const saved = localStorage.getItem('vibehub.chatPanelWidth');
		return saved ? parseInt(saved, 10) : DEFAULT_WIDTH;
	});
	const [isCollapsed, setIsCollapsed] = useState(() => {
		return localStorage.getItem('vibehub.chatPanelCollapsed') === 'true';
	});
	const [isResizing, setIsResizing] = useState(false);
	const panelRef = useRef<HTMLDivElement>(null);
	const resizeStartX = useRef(0);
	const resizeStartWidth = useRef(0);

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
		hasExistingData,
	} = useChat(chatId, { readOnly });

	useEffect(() => {
		if (initialized || connectionState !== 'connected') return;

		if (readOnly) {
			initSession(undefined, locationState?.template, true, true, true);
		} else {
			// Send session_init and let backend handle resuming if needed
			// Backend _resume_generation_if_needed will automatically resume unfinished generations
			initSession(undefined, locationState?.template, true, false, locationState?.rebuildSandbox === true);
		}
		setInitialized(true);
	}, [connectionState, initialized, initSession, locationState, readOnly]);

	const tabs: { id: ViewTab; label: string; icon: typeof Code }[] = [
		{ id: 'editor', label: 'Editor', icon: Code },
		{ id: 'preview', label: 'Preview', icon: Eye },
		{ id: 'blueprint', label: 'Blueprint', icon: FolderTree },
	];

	// Resize handlers
	const handleResizeStart = useCallback((e: React.MouseEvent) => {
		if (isCollapsed) return;
		setIsResizing(true);
		resizeStartX.current = e.clientX;
		resizeStartWidth.current = panelWidth;
		e.preventDefault();
	}, [isCollapsed, panelWidth]);

	const handleResizeMove = useCallback((e: MouseEvent) => {
		if (!isResizing) return;
		const delta = e.clientX - resizeStartX.current;
		const newWidth = Math.max(MIN_PANEL_WIDTH, Math.min(MAX_PANEL_WIDTH, resizeStartWidth.current + delta));
		setPanelWidth(newWidth);
		localStorage.setItem('vibehub.chatPanelWidth', String(newWidth));
	}, [isResizing]);

	const handleResizeEnd = useCallback(() => {
		setIsResizing(false);
	}, []);

	useEffect(() => {
		if (isResizing) {
			window.addEventListener('mousemove', handleResizeMove);
			window.addEventListener('mouseup', handleResizeEnd);
			return () => {
				window.removeEventListener('mousemove', handleResizeMove);
				window.removeEventListener('mouseup', handleResizeEnd);
			};
		}
	}, [isResizing, handleResizeMove, handleResizeEnd]);

	const toggleCollapse = useCallback(() => {
		const newCollapsed = !isCollapsed;
		setIsCollapsed(newCollapsed);
		localStorage.setItem('vibehub.chatPanelCollapsed', String(newCollapsed));
	}, [isCollapsed]);

	return (
		<div className="flex flex-1 overflow-hidden">
			{/* Left panel: messages - Collapsed state */}
			{isCollapsed ? (
				<div
					className="flex flex-col items-center border-r border-border bg-surface py-3"
					style={{ width: COLLAPSED_WIDTH }}
				>
					<button
						onClick={toggleCollapse}
						className="flex h-10 w-10 items-center justify-center rounded-lg text-text-secondary hover:bg-surface-secondary hover:text-text-primary"
						title="Expand chat panel"
					>
						<PanelLeft size={20} />
					</button>
					<div className="mt-4 flex flex-col items-center gap-2">
						{messages.length > 0 && (
							<div className="flex h-6 w-6 items-center justify-center rounded-full bg-brand text-xs text-white">
								{messages.filter(m => m.role === 'assistant').length}
							</div>
						)}
					</div>
				</div>
			) : (
				<>
					{/* Left panel: messages - Expanded state */}
					<div
						ref={panelRef}
						className="flex min-h-0 flex-col border-r border-border"
						style={{ width: panelWidth }}
					>
						{/* Collapse button */}
						<div className="flex items-center justify-end border-b border-border px-2 py-1">
							<button
								onClick={toggleCollapse}
								className="flex h-7 w-7 items-center justify-center rounded-md text-text-tertiary hover:bg-surface-secondary hover:text-text-secondary"
								title="Collapse chat panel"
							>
								<PanelLeft size={16} />
							</button>
						</div>
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
					{/* Resize handle */}
					<div
						onMouseDown={handleResizeStart}
						className={cn(
							'w-1 cursor-col-resize bg-transparent hover:bg-brand/30',
							isResizing && 'bg-brand/50'
						)}
						style={{ marginLeft: '-2px', marginRight: '-2px', zIndex: 10 }}
					/>
				</>
			)}

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
