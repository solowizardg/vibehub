import type { ReactNode } from 'react';
import { Sparkles } from 'lucide-react';
import { Link } from 'react-router';

interface MainLayoutProps {
	children: ReactNode;
}

export function MainLayout({ children }: MainLayoutProps) {
	return (
		<div className="flex h-screen flex-col bg-surface">
			{/* Top bar */}
			<header className="flex h-11 shrink-0 items-center justify-between border-b border-border px-4">
				<Link to="/" className="flex items-center gap-2 text-text-primary transition-colors hover:text-brand">
					<Sparkles size={18} className="text-brand" />
					<span className="text-sm font-bold tracking-tight">VibeHub</span>
				</Link>
			</header>

			{/* Main content */}
			<main className="flex flex-1 overflow-hidden">{children}</main>
		</div>
	);
}
