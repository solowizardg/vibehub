import Editor from '@monaco-editor/react';
import type { OnChange } from '@monaco-editor/react';

interface CodeEditorProps {
	value: string;
	language: string;
	readOnly?: boolean;
	onChange?: (value: string) => void;
}

function detectLanguage(lang: string): string {
	const map: Record<string, string> = {
		typescriptreact: 'typescript',
		javascriptreact: 'javascript',
		tsx: 'typescript',
		jsx: 'javascript',
		ts: 'typescript',
		js: 'javascript',
		json: 'json',
		css: 'css',
		html: 'html',
		md: 'markdown',
		py: 'python',
		plaintext: 'plaintext',
	};
	return map[lang] ?? lang;
}

export function CodeEditor({ value, language, readOnly = false, onChange }: CodeEditorProps) {
	const handleChange: OnChange = (newValue) => {
		if (newValue !== undefined && onChange) {
			onChange(newValue);
		}
	};

	return (
		<Editor
			height="100%"
			language={detectLanguage(language)}
			value={value}
			theme="vs-dark"
			onChange={handleChange}
			options={{
				readOnly,
				minimap: { enabled: false },
				lineNumbers: 'on',
				fontSize: 13,
				scrollBeyondLastLine: false,
				wordWrap: 'on',
				renderWhitespace: 'none',
				overviewRulerBorder: false,
				hideCursorInOverviewRuler: true,
				padding: { top: 12 },
			}}
		/>
	);
}
