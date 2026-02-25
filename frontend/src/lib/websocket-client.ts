import type { ClientMessage, ServerMessage } from '@/types/websocket';

type MessageHandler = (message: ServerMessage) => void;
type ConnectionState = 'idle' | 'connecting' | 'connected' | 'disconnected' | 'failed';

const MAX_RETRIES = 5;
const BASE_DELAY = 1000;
const MAX_DELAY = 30000;

export class WebSocketClient {
	private ws: WebSocket | null = null;
	private handlers: Set<MessageHandler> = new Set();
	private stateListeners: Set<(state: ConnectionState) => void> = new Set();
	private retryCount = 0;
	private retryTimer: ReturnType<typeof setTimeout> | null = null;
	private _state: ConnectionState = 'idle';
	private url: string;

	constructor(sessionId: string) {
		const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
		this.url = `${protocol}//${window.location.host}/ws/${sessionId}`;
	}

	get state(): ConnectionState {
		return this._state;
	}

	private setState(state: ConnectionState) {
		this._state = state;
		this.stateListeners.forEach((fn) => fn(state));
	}

	connect(): void {
		if (this.ws?.readyState === WebSocket.OPEN) return;
		this.setState('connecting');

		this.ws = new WebSocket(this.url);

		this.ws.onopen = () => {
			this.retryCount = 0;
			this.setState('connected');
		};

		this.ws.onmessage = (event) => {
			try {
				const msg: ServerMessage = JSON.parse(event.data);
				this.handlers.forEach((fn) => fn(msg));
			} catch {
				// ignore malformed messages
			}
		};

		this.ws.onclose = () => {
			this.setState('disconnected');
			this.scheduleReconnect();
		};

		this.ws.onerror = () => {
			this.ws?.close();
		};
	}

	private scheduleReconnect(): void {
		if (this.retryCount >= MAX_RETRIES) {
			this.setState('failed');
			return;
		}
		const delay = Math.min(BASE_DELAY * 2 ** this.retryCount, MAX_DELAY);
		this.retryCount++;
		this.retryTimer = setTimeout(() => {
			this.connect();
		}, delay);
	}

	send(message: ClientMessage): void {
		if (this.ws?.readyState === WebSocket.OPEN) {
			this.ws.send(JSON.stringify(message));
		}
	}

	onMessage(handler: MessageHandler): () => void {
		this.handlers.add(handler);
		return () => this.handlers.delete(handler);
	}

	onStateChange(handler: (state: ConnectionState) => void): () => void {
		this.stateListeners.add(handler);
		return () => this.stateListeners.delete(handler);
	}

	disconnect(): void {
		if (this.retryTimer) clearTimeout(this.retryTimer);
		this.retryCount = MAX_RETRIES;
		this.ws?.close();
		this.ws = null;
		this.setState('idle');
	}
}
