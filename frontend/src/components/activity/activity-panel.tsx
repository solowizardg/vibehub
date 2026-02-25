import { useState } from 'react';
import { ChevronDown, ChevronUp, Terminal, Trash2 } from 'lucide-react';
import { useAutoScroll } from '@/hooks/use-auto-scroll';
import { cn } from '@/lib/cn';

export interface ActivityLog {
	id: string;
	type: 'llm' | 'phase' | 'file' | 'sandbox' | 'error' | 'info';
	content: string;
	timestamp: number;
}

interface ActivityPanelProps {
	logs: ActivityLog[];
	onClear?: () => void;
}

const TYPE_STYLES: Record<ActivityLog['type'], string> = {
	llm: 'text-gray-300',
	phase: 'text-blue-400',
	file: 'text-green-400',
	sandbox: 'text-yellow-400',
	error: 'text-red-400',
	info: 'text-gray-500',
};

const TYPE_LABELS: Record<ActivityLog['type'], string> = {
	llm: 'LLM',
	phase: 'Phase',
	file: 'File',
	sandbox: 'Sandbox',
	error: 'Error',
	info: 'Info',
};

export function ActivityPanel({ logs, onClear }: ActivityPanelProps) {
	const [collapsed, setCollapsed] = useState(false);
	const { ref } = useAutoScroll<HTMLDivElement>([logs]);

	return (
		<div className={cn('flex flex-col border-t border-border', collapsed ? 'h-8' : 'h-64')}>
			<div
				className="flex shrink-0 cursor-pointer items-center justify-between bg-[#1e1e1e] px-3 py-1"
				onClick={() => setCollapsed((prev) => !prev)}
			>
				<div className="flex items-center gap-1.5">
					<Terminal size={12} className="text-gray-400" />
					<span className="text-[11px] font-medium text-gray-400">Activity</span>
					{logs.length > 0 && (
						<span className="text-[10px] text-gray-600">{logs.length}</span>
					)}
				</div>
				<div className="flex items-center gap-1">
					{!collapsed && onClear && logs.length > 0 && (
						<button
							onClick={(e) => {
								e.stopPropagation();
								onClear();
							}}
							className="rounded p-0.5 text-gray-600 hover:text-gray-400"
							title="Clear"
						>
							<Trash2 size={11} />
						</button>
					)}
					{collapsed ? (
						<ChevronUp size={12} className="text-gray-500" />
					) : (
						<ChevronDown size={12} className="text-gray-500" />
					)}
				</div>
			</div>

			{!collapsed && (
				<div
					ref={ref}
					className="flex-1 overflow-y-auto bg-[#1e1e1e] px-3 py-1 font-mono text-xs leading-5"
				>
					{logs.length === 0 ? (
						<div className="flex h-full items-center justify-center text-gray-600">
							Waiting for activity...
						</div>
					) : (
						logs.map((log) => (
							<LogEntry key={log.id} log={log} />
						))
					)}
				</div>
			)}
		</div>
	);
}

function LogEntry({ log }: { log: ActivityLog }) {
	const style = TYPE_STYLES[log.type];
	const label = TYPE_LABELS[log.type];

	if (log.type === 'llm') {
		return (
			<div className={cn('whitespace-pre-wrap break-words', style)}>
				{log.content}
			</div>
		);
	}

	return (
		<div className="flex gap-2">
			<span className={cn('shrink-0 font-semibold', style)}>[{label}]</span>
			<span className={cn('break-words', style)}>{log.content}</span>
		</div>
	);
}
