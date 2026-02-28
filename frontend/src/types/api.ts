export interface BlueprintData {
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
	phases: {
		name: string;
		description: string;
		files: string[];
	}[];
}

export interface BlueprintVariant {
	variant_id: string;
	style_name: string;
	style_description: string;
	project_name: string;
	description: string;
	design_blueprint?: BlueprintData['design_blueprint'];
	phases?: {
		name: string;
		description: string;
		files: string[];
	}[];
	blueprint_markdown?: string;
}

export interface SessionInfo {
	id: string;
	title: string;
	status: string;
	template_name: string;
	preview_url: string | null;
	blueprint: BlueprintData | null;
	blueprint_markdown: string | null;
	blueprint_variants?: BlueprintVariant[];
	selected_variant_id?: string | null;
	created_at: string;
	updated_at: string;
}

export interface FileInfo {
	file_path: string;
	file_contents: string;
	language: string;
	phase_index: number;
}

export interface PhaseInfo {
	phase_index: number;
	name: string;
	description: string;
	status: 'pending' | 'active' | 'generating' | 'implementing' | 'validating' | 'completed' | 'error';
	files: string[] | null;
}

export interface MessageInfo {
	id: string;
	role: 'user' | 'assistant' | 'system' | 'tool';
	content: string;
	tool_calls: Record<string, unknown> | null;
	created_at: string;
}

export interface CreateSessionResponse {
	session_id: string;
	websocket_url: string;
}

export interface SessionDetail {
	session: SessionInfo;
	files: FileInfo[];
	phases: PhaseInfo[];
	messages: MessageInfo[];
}
