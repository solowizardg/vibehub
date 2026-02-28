export interface BlueprintPayload {
	project_name: string;
	description: string;
	design_blueprint?: {
		visual_style?: {
			color_palette?: string[];
			typography?: string;
			spacing?: string;
		};
		interaction_design?: {
			core_patterns?: string[];
			component_states?: string[];
			motion?: string;
		};
		ui_principles?: string[];
	};
	phases: { name: string; description: string; files: string[] }[];
}

export interface AgentState {
	session_id: string;
	status: string;
	read_only?: boolean;
	blueprint?: BlueprintPayload | null;
	blueprint_markdown?: string | null;
	generated_files_map: Record<string, { filePath: string; fileContents: string; language?: string }>;
	generated_phases: PhaseData[];
	current_phase: number;
	should_be_generating: boolean;
	conversation_messages: ConversationMessage[];
}

export interface PhaseData {
	index: number;
	name: string;
	description?: string;
	status: 'pending' | 'active' | 'generating' | 'implementing' | 'validating' | 'completed' | 'error';
	files: string[];
}

export interface ConversationMessage {
	role: 'user' | 'assistant' | 'system';
	content: string;
}

export interface BlueprintVariantPayload {
	variant_id: string;
	style_name: string;
	style_description: string;
	project_name: string;
	description: string;
	blueprint_markdown?: string;
}

export type ServerMessage =
	| { type: 'agent_connected'; state: AgentState; preview_url?: string }
	| { type: 'generation_started' }
	| { type: 'generation_complete'; preview_url?: string; error?: string }
	| { type: 'generation_stopped' }
	| { type: 'phase_generating'; phase: PhaseData }
	| { type: 'phase_implementing'; phase_index: number }
	| { type: 'phase_implemented'; phase_index: number }
	| { type: 'phase_validated'; phase_index: number }
	| { type: 'file_generating'; filePath: string }
	| { type: 'file_chunk_generated'; filePath: string; chunk: string }
	| { type: 'file_generated'; filePath: string; fileContents: string; language?: string }
	| { type: 'llm_token'; node: string; token: string }
	| { type: 'conversation_response'; content: string; isStreaming: boolean }
	| { type: 'sandbox_status'; status: string; attempt?: number }
	| { type: 'sandbox_log'; stream: 'stdout' | 'stderr'; text: string }
	| { type: 'sandbox_preview'; url: string }
	| { type: 'sandbox_error'; message: string }
	| { type: 'blueprint_generated'; blueprint: BlueprintPayload; blueprint_markdown?: string }
	| { type: 'blueprint_variants_generating'; count: number }
	| { type: 'blueprint_variants_generated'; variants: BlueprintVariantPayload[] }
	| { type: 'blueprint_selected'; variant_id: string; blueprint?: BlueprintPayload; blueprint_markdown?: string }
	| { type: 'deployment_started' }
	| { type: 'deployment_completed'; previewUrl: string }
	| { type: 'error'; message: string }
	| { type: 'blueprint_chunk'; chunk: string };

export type ClientMessage =
	| { type: 'session_init'; query: string; template?: string; read_only?: boolean; rebuild_sandbox?: boolean }
	| { type: 'generate_all'; query?: string; template?: string; read_only?: boolean }
	| { type: 'user_suggestion'; message: string; read_only?: boolean }
	| { type: 'stop_generation'; read_only?: boolean }
	| { type: 'file_edit'; filePath: string; fileContents: string }
	| { type: 'select_blueprint_variant'; variantId: string }
	| { type: 'deploy' };
