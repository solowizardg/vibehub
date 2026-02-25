import Editor from '@monaco-editor/react';

interface CodeEditorProps {
	value: string;
	language: string;
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

export function CodeEditor({ value, language }: CodeEditorProps) {
	return (
		<Editor
			height="100%"
			language={detectLanguage(language)}
			value={value}
			theme="vs-dark"
			options={{
				readOnly: true,
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
