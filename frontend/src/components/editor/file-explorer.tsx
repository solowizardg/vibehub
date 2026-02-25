import { useState } from 'react';
import { ChevronRight, File, FolderClosed, FolderOpen } from 'lucide-react';
import { cn } from '@/lib/cn';

interface FileNode {
	name: string;
	path: string;
	isDir: boolean;
	children?: FileNode[];
}

function buildFileTree(paths: string[]): FileNode[] {
	const root: FileNode = { name: '', path: '', isDir: true, children: [] };

	for (const filePath of paths.sort()) {
		const parts = filePath.split('/');
		let current = root;

		for (let i = 0; i < parts.length; i++) {
			const part = parts[i];
			const isLast = i === parts.length - 1;
			const childPath = parts.slice(0, i + 1).join('/');

			let child = current.children?.find((c) => c.name === part);
			if (!child) {
				child = { name: part, path: childPath, isDir: !isLast, children: isLast ? undefined : [] };
				current.children?.push(child);
			}
			current = child;
		}
	}

	return root.children ?? [];
}

interface TreeNodeProps {
	node: FileNode;
	activePath: string | null;
	onSelect: (path: string) => void;
	depth: number;
}

function TreeNode({ node, activePath, onSelect, depth }: TreeNodeProps) {
	const [isOpen, setIsOpen] = useState(depth < 2);

	if (node.isDir) {
		return (
			<div>
				<button
					onClick={() => setIsOpen(!isOpen)}
					className="flex w-full items-center gap-1.5 rounded px-2 py-1 text-left text-xs text-text-secondary transition-colors hover:bg-surface-tertiary hover:text-text-primary"
					style={{ paddingLeft: `${depth * 12 + 8}px` }}
				>
					<ChevronRight size={12} className={cn('shrink-0 transition-transform', isOpen && 'rotate-90')} />
					{isOpen ? <FolderOpen size={14} className="shrink-0 text-brand" /> : <FolderClosed size={14} className="shrink-0 text-brand" />}
					<span className="truncate">{node.name}</span>
				</button>
				{isOpen && node.children?.map((child) => <TreeNode key={child.path} node={child} activePath={activePath} onSelect={onSelect} depth={depth + 1} />)}
			</div>
		);
	}

	return (
		<button
			onClick={() => onSelect(node.path)}
			className={cn(
				'flex w-full items-center gap-1.5 rounded px-2 py-1 text-left text-xs transition-colors',
				activePath === node.path ? 'bg-brand/10 text-brand' : 'text-text-secondary hover:bg-surface-tertiary hover:text-text-primary',
			)}
			style={{ paddingLeft: `${depth * 12 + 8}px` }}
		>
			<File size={14} className="shrink-0" />
			<span className="truncate">{node.name}</span>
		</button>
	);
}

interface FileExplorerProps {
	filePaths: string[];
	activePath: string | null;
	onSelect: (path: string) => void;
}

export function FileExplorer({ filePaths, activePath, onSelect }: FileExplorerProps) {
	const tree = buildFileTree(filePaths);

	return (
		<div className="flex w-[200px] shrink-0 flex-col border-r border-border bg-surface">
			<div className="flex items-center gap-2 border-b border-border px-3 py-2">
				<FolderClosed size={14} className="text-text-secondary" />
				<span className="text-xs font-medium text-text-secondary">Files</span>
			</div>
			<div className="flex-1 overflow-y-auto py-1">{tree.map((node) => <TreeNode key={node.path} node={node} activePath={activePath} onSelect={onSelect} depth={0} />)}</div>
		</div>
	);
}
