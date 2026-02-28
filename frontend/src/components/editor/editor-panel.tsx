import { useState } from 'react';
import type { ChatFile } from '@/hooks/use-chat';
import { CodeEditor } from './code-editor';
import { FileExplorer } from './file-explorer';

interface EditorPanelProps {
	files: Record<string, ChatFile>;
	readOnly?: boolean;
	onEditFile?: (filePath: string, fileContents: string) => void;
}

export function EditorPanel({ files, readOnly = false, onEditFile }: EditorPanelProps) {
	const filePaths = Object.keys(files);
	const [activePath, setActivePath] = useState<string | null>(filePaths[0] ?? null);

	const activeFile = activePath ? files[activePath] : null;

	const handleEditorChange = (value: string) => {
		if (activePath && onEditFile && !readOnly) {
			onEditFile(activePath, value);
		}
	};

	if (filePaths.length === 0) {
		return (
			<div className="flex flex-1 items-center justify-center text-text-secondary">
				<p className="text-sm">No files generated yet.</p>
			</div>
		);
	}

	return (
		<div className="flex flex-1 overflow-hidden">
			<FileExplorer filePaths={filePaths} activePath={activePath} onSelect={setActivePath} />
			<div className="flex flex-1 flex-col overflow-hidden">
				{activeFile ? (
					<>
						<div className="flex items-center border-b border-border px-3 py-1.5">
							<span className="text-xs text-text-secondary">{activeFile.filePath}</span>
							{activeFile.isGenerating && <span className="ml-2 text-xs text-brand animate-pulse">generating...</span>}
							{!readOnly && !activeFile.isGenerating && <span className="ml-2 text-xs text-text-secondary">Editable</span>}
						</div>
						<div className="flex-1">
							<CodeEditor
								value={activeFile.fileContents}
								language={activeFile.language}
								readOnly={readOnly || activeFile.isGenerating}
								onChange={handleEditorChange}
							/>
						</div>
					</>
				) : (
					<div className="flex flex-1 items-center justify-center text-text-secondary">
						<p className="text-sm">Select a file to view.</p>
					</div>
				)}
			</div>
		</div>
	);
}
