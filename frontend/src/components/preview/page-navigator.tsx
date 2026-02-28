import { FileText, Home } from 'lucide-react';
import { cn } from '@/lib/cn';

interface PageNavigatorProps {
	pages: { path: string; label: string }[];
	currentPath: string;
	onNavigate: (path: string) => void;
}

export function PageNavigator({ pages, currentPath, onNavigate }: PageNavigatorProps) {
	const getPageLabel = (path: string) => {
		if (path === '/' || path === '') return 'Home';
		// Remove leading slash and capitalize
		const clean = path.replace(/^\//, '').replace(/-/g, ' ');
		return clean.charAt(0).toUpperCase() + clean.slice(1);
	};

	const getPageIcon = (path: string) => {
		if (path === '/' || path === '') return Home;
		return FileText;
	};

	return (
		<div className="flex h-full w-48 flex-col border-r border-border bg-surface-secondary">
			<div className="border-b border-border px-3 py-2">
				<h3 className="text-xs font-semibold text-text-secondary uppercase tracking-wider">Pages</h3>
			</div>
			<div className="flex-1 overflow-y-auto py-2">
				{pages.map((page) => {
					const Icon = getPageIcon(page.path);
					const isActive = currentPath === page.path || (currentPath === '' && page.path === '/');
					return (
						<button
							key={page.path}
							onClick={() => onNavigate(page.path)}
							className={cn(
								'flex w-full items-center gap-2 px-3 py-2 text-left text-sm transition-colors',
								isActive
									? 'bg-brand/10 text-brand'
									: 'text-text-secondary hover:bg-surface-tertiary hover:text-text-primary'
							)}
						>
							<Icon size={14} />
							<span className="truncate">{page.label || getPageLabel(page.path)}</span>
						</button>
					);
				})}
			</div>
			<div className="border-t border-border px-3 py-2">
				<p className="text-[10px] text-text-muted">
					Hold <kbd className="rounded bg-surface-tertiary px-1 py-0.5 font-mono text-text-secondary">Alt</kbd> to select component
				</p>
			</div>
		</div>
	);
}
