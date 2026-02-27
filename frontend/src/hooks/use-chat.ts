import { useCallback, useEffect, useRef, useState } from 'react';
import { WebSocketClient } from '@/lib/websocket-client';
import type { ActivityLog } from '@/components/activity/activity-panel';
import type { BlueprintData } from '@/types/api';
import type { AgentState, PhaseData, ServerMessage } from '@/types/websocket';

export interface ChatFile {
	filePath: string;
	fileContents: string;
	language: string;
	isGenerating: boolean;
}

export interface ChatMessage {
	id: string;
	role: 'user' | 'assistant' | 'system';
	content: string;
	isStreaming?: boolean;
}

type ConnectionState = 'idle' | 'connecting' | 'connected' | 'disconnected' | 'failed';
interface UseChatOptions {
	readOnly?: boolean;
}

let _logIdCounter = 0;
const nextLogId = () => `log-${++_logIdCounter}`;

function appendLog(
	setter: React.Dispatch<React.SetStateAction<ActivityLog[]>>,
	type: ActivityLog['type'],
	content: string,
) {
	setter((prev) => [...prev, { id: nextLogId(), type, content, timestamp: Date.now() }]);
}

function appendOrStreamLlm(
	setter: React.Dispatch<React.SetStateAction<ActivityLog[]>>,
	token: string,
) {
	setter((prev) => {
		const last = prev[prev.length - 1];
		if (last?.type === 'llm') {
			return [...prev.slice(0, -1), { ...last, content: last.content + token }];
		}
		return [...prev, { id: nextLogId(), type: 'llm', content: token, timestamp: Date.now() }];
	});
}

export function useChat(sessionId: string | undefined, options: UseChatOptions = {}) {
	const readOnly = options.readOnly ?? false;
	const [messages, setMessages] = useState<ChatMessage[]>([]);
	const [files, setFiles] = useState<Record<string, ChatFile>>({});
	const [phases, setPhases] = useState<PhaseData[]>([]);
	const [activityLogs, setActivityLogs] = useState<ActivityLog[]>([]);
	const [isGenerating, setIsGenerating] = useState(false);
	const [blueprint, setBlueprint] = useState<BlueprintData | null>(null);
	const [blueprintMarkdown, setBlueprintMarkdown] = useState<string | null>(null);
	const [previewUrl, setPreviewUrl] = useState<string | null>(null);
	const [connectionState, setConnectionState] = useState<ConnectionState>('idle');

	const wsRef = useRef<WebSocketClient | null>(null);
	const msgIdCounter = useRef(0);
	const streamingNodeRef = useRef<string | null>(null);

	const nextId = () => `msg-${++msgIdCounter.current}`;

	const handleMessage = useCallback((msg: ServerMessage) => {
		const pushSystemMessage = (content: string) => {
			const text = content.trim();
			if (!text) return;
			setMessages((prev) => {
				const last = prev[prev.length - 1];
				if (last?.role === 'system' && last.content === text) return prev;
				return [...prev, { id: nextId(), role: 'system', content: text }];
			});
		};

		switch (msg.type) {
			case 'agent_connected': {
				const state: AgentState = msg.state;
				if (state.generated_files_map) {
					const restored: Record<string, ChatFile> = {};
					for (const [path, file] of Object.entries(state.generated_files_map)) {
						restored[path] = {
							filePath: file.filePath,
							fileContents: file.fileContents,
							language: file.language ?? 'plaintext',
							isGenerating: false,
						};
					}
					setFiles(restored);
				}
				if (state.generated_phases) setPhases(state.generated_phases);
				if (state.blueprint) setBlueprint(state.blueprint);
				if (typeof state.blueprint_markdown === 'string') setBlueprintMarkdown(state.blueprint_markdown);
				if (state.conversation_messages && state.conversation_messages.length > 0) {
					setMessages(
						state.conversation_messages.map((m) => ({
							id: nextId(),
							role: m.role,
							content: m.content,
						})),
					);
				}
				if (msg.preview_url) setPreviewUrl(msg.preview_url);
				appendLog(setActivityLogs, 'info', 'Connected to agent');
				if (state.read_only) {
					pushSystemMessage('This historical project is in read-only mode.');
				}
				break;
			}

			case 'generation_started':
				setIsGenerating(true);
				streamingNodeRef.current = null;
				appendLog(setActivityLogs, 'info', 'Generation started');
				pushSystemMessage('Starting generation...');
				break;

			case 'generation_complete':
				setIsGenerating(false);
				streamingNodeRef.current = null;
				if (msg.preview_url) setPreviewUrl(msg.preview_url);
				if (msg.error) {
					appendLog(setActivityLogs, 'error', msg.error);
					setMessages((prev) => [...prev, { id: nextId(), role: 'assistant', content: `Error: ${msg.error}` }]);
				}
				appendLog(setActivityLogs, 'info', 'Generation complete');
				pushSystemMessage('Generation completed.');
				break;

			case 'generation_stopped':
				setIsGenerating(false);
				streamingNodeRef.current = null;
				appendLog(setActivityLogs, 'info', 'Generation stopped');
				pushSystemMessage('Generation stopped.');
				break;

			case 'blueprint_generated':
				setBlueprint(msg.blueprint);
				if (typeof msg.blueprint_markdown === 'string') {
					setBlueprintMarkdown(msg.blueprint_markdown);
				}
				streamingNodeRef.current = null;
				appendLog(setActivityLogs, 'info', `Blueprint ready: ${msg.blueprint.project_name}`);
				pushSystemMessage(`Blueprint ready: ${msg.blueprint.project_name}`);
				break;

			case 'phase_generating':
				setPhases((prev) => {
					const exists = prev.find((p) => p.index === msg.phase.index);
					if (exists) return prev.map((p) => (p.index === msg.phase.index ? { ...msg.phase, status: 'generating' } : p));
					return [...prev, { ...msg.phase, status: 'generating' }];
				});
				appendLog(setActivityLogs, 'phase', `Generating phase ${msg.phase.index + 1}: ${msg.phase.name}`);
				pushSystemMessage(`Planning phase ${msg.phase.index + 1}: ${msg.phase.name}`);
				break;

			case 'phase_implementing':
				setPhases((prev) => prev.map((p) => (p.index === msg.phase_index ? { ...p, status: 'implementing' } : p)));
				appendLog(setActivityLogs, 'phase', `Implementing phase ${msg.phase_index + 1}`);
				pushSystemMessage(`Implementing phase ${msg.phase_index + 1}...`);
				break;

			case 'phase_implemented':
				setPhases((prev) => prev.map((p) => (p.index === msg.phase_index ? { ...p, status: 'completed' } : p)));
				appendLog(setActivityLogs, 'phase', `Phase ${msg.phase_index + 1} completed`);
				pushSystemMessage(`Phase ${msg.phase_index + 1} completed.`);
				break;

			case 'phase_validated':
				setPhases((prev) => prev.map((p) => (p.index === msg.phase_index ? { ...p, status: 'completed' } : p)));
				pushSystemMessage(`Phase ${msg.phase_index + 1} validated.`);
				break;

			case 'file_generating':
				setFiles((prev) => ({
					...prev,
					[msg.filePath]: {
						filePath: msg.filePath,
						fileContents: '',
						language: 'plaintext',
						isGenerating: true,
					},
				}));
				appendLog(setActivityLogs, 'file', `Generating ${msg.filePath}`);
				break;

			case 'file_chunk_generated':
				setFiles((prev) => ({
					...prev,
					[msg.filePath]: {
						...prev[msg.filePath],
						fileContents: (prev[msg.filePath]?.fileContents ?? '') + msg.chunk,
					},
				}));
				break;

			case 'file_generated':
				setFiles((prev) => ({
					...prev,
					[msg.filePath]: {
						filePath: msg.filePath,
						fileContents: msg.fileContents,
						language: msg.language ?? 'plaintext',
						isGenerating: false,
					},
				}));
				appendLog(setActivityLogs, 'file', `Generated ${msg.filePath}`);
				break;

			case 'llm_token': {
				const prevNode = streamingNodeRef.current;
				const nodeChanged = prevNode !== null && prevNode !== msg.node;
				streamingNodeRef.current = msg.node;

				if (nodeChanged) {
					appendLog(setActivityLogs, 'info', `--- ${msg.node} ---`);
				}
				appendOrStreamLlm(setActivityLogs, msg.token);
				break;
			}

			case 'sandbox_status': {
				const labels: Record<string, string> = {
					creating: 'Creating sandbox environment...',
					writing_files: 'Writing files to sandbox...',
					installing: 'Installing dependencies (npm install)...',
					validating: 'Running validation checks (typecheck/lint/build)...',
					building: 'Building project (npm run build)...',
					starting_server: 'Starting preview server...',
					starting_server_attempt: `Starting server (attempt ${msg.attempt ?? '?'})...`,
					server_command_started: `Server command launched (attempt ${msg.attempt ?? '?'})...`,
					server_already_running: 'Server already running, reusing existing process...',
					fixing: `Fixing errors (attempt ${msg.attempt ?? '?'})...`,
				};
				const label = labels[msg.status] ?? `Sandbox: ${msg.status}`;
				appendLog(setActivityLogs, 'sandbox', label);
				pushSystemMessage(label);
				streamingNodeRef.current = null;
				break;
			}

			case 'sandbox_log':
				if (msg.text.trim()) {
					appendLog(setActivityLogs, 'sandbox', msg.text.trim());
				}
				break;

			case 'sandbox_preview':
				setPreviewUrl(msg.url);
				appendLog(setActivityLogs, 'sandbox', `Preview ready: ${msg.url}`);
				pushSystemMessage(`Preview ready: ${msg.url}`);
				break;

			case 'sandbox_error':
				appendLog(setActivityLogs, 'error', `Sandbox: ${msg.message}`);
				pushSystemMessage(`Sandbox error: ${msg.message}`);
				break;

			case 'conversation_response':
				if (msg.isStreaming) {
					setMessages((prev) => {
						const last = prev[prev.length - 1];
						if (last?.role === 'assistant' && last.isStreaming) {
							return [...prev.slice(0, -1), { ...last, content: last.content + msg.content }];
						}
						return [...prev, { id: nextId(), role: 'assistant', content: msg.content, isStreaming: true }];
					});
				} else {
					setMessages((prev) => {
						const last = prev[prev.length - 1];
						if (last?.role === 'assistant' && last.isStreaming) {
							return [...prev.slice(0, -1), { ...last, content: msg.content, isStreaming: false }];
						}
						return [...prev, { id: nextId(), role: 'assistant', content: msg.content }];
					});
				}
				break;

			case 'deployment_completed':
				setPreviewUrl(msg.previewUrl);
				appendLog(setActivityLogs, 'info', `Deployed: ${msg.previewUrl}`);
				break;

			case 'error':
				appendLog(setActivityLogs, 'error', msg.message);
				pushSystemMessage(`Generation error: ${msg.message}`);
				break;

			default:
				break;
		}
	}, []);

	useEffect(() => {
		if (!sessionId) return;

		const client = new WebSocketClient(sessionId);
		wsRef.current = client;

		client.onMessage(handleMessage);
		client.onStateChange(setConnectionState);
		client.connect();

		return () => {
			client.disconnect();
			wsRef.current = null;
		};
	}, [sessionId, handleMessage]);

	const sendMessage = useCallback(
		(content: string) => {
			if (!wsRef.current || readOnly) return;
			setMessages((prev) => [...prev, { id: nextId(), role: 'user', content }]);
			wsRef.current.send({ type: 'user_suggestion', message: content });
		},
		[readOnly],
	);

	const startGeneration = useCallback((query?: string, template?: string) => {
		if (readOnly) return;
		wsRef.current?.send({ type: 'generate_all', query, template });
	}, [readOnly]);

	const stopGeneration = useCallback(() => {
		if (readOnly) return;
		wsRef.current?.send({ type: 'stop_generation' });
	}, [readOnly]);

	const initSession = useCallback(
		(query?: string, template = 'react-vite', hydrateOnly = false, readOnlyMode = readOnly, rebuildSandbox = false) => {
			wsRef.current?.send({
				type: 'session_init',
				query: query ?? '',
				template,
				read_only: readOnlyMode,
				rebuild_sandbox: rebuildSandbox,
			});
			if (!hydrateOnly && query?.trim()) {
				setMessages([{ id: nextId(), role: 'user', content: query }]);
			}
		},
		[readOnly],
	);

	const clearActivityLogs = useCallback(() => {
		setActivityLogs([]);
	}, []);

	return {
		messages,
		files,
		phases,
		blueprint,
		blueprintMarkdown,
		readOnly,
		isGenerating,
		previewUrl,
		connectionState,
		activityLogs,
		sendMessage,
		startGeneration,
		stopGeneration,
		initSession,
		clearActivityLogs,
	};
}
