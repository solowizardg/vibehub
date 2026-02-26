import { useMemo, useState } from 'react';
import { Check, Circle, Loader2, X } from 'lucide-react';
import type { PhaseData } from '@/types/websocket';
import { cn } from '@/lib/cn';

interface GenerationProgressMessageProps {
	phases: PhaseData[];
	events: string[];
}

function StatusIcon({ status }: { status: PhaseData['status'] }) {
	switch (status) {
		case 'completed':
			return <Check size={12} className="text-success" />;
		case 'generating':
		case 'implementing':
		case 'active':
		case 'validating':
			return <Loader2 size={12} className="animate-spin text-brand" />;
		case 'error':
			return <X size={12} className="text-error" />;
		default:
			return <Circle size={8} className="text-text-muted" />;
	}
}

function statusLabel(status: PhaseData['status']): string {
	switch (status) {
		case 'generating':
			return 'Planning...';
		case 'implementing':
			return 'Implementing...';
		case 'validating':
			return 'Validating...';
		case 'completed':
			return 'Done';
		case 'error':
			return 'Error';
		default:
			return 'Pending';
	}
}

export function GenerationProgressMessage({ phases, events }: GenerationProgressMessageProps) {
	const [activeTab, setActiveTab] = useState<'phases' | 'events'>('phases');
	const eventItems = useMemo(() => events.slice(-16).reverse(), [events]);

	return (
		<div className="py-3">
			<div className="rounded-xl border border-border bg-surface-secondary p-3">
				<div className="mb-3 flex items-center justify-between">
					<h3 className="text-xs font-semibold uppercase tracking-wider text-text-secondary">
						Generation Progress
					</h3>
					<div className="flex rounded-md border border-border/70 bg-surface-tertiary p-0.5">
						<button
							onClick={() => setActiveTab('phases')}
							className={cn(
								'rounded px-2 py-1 text-[11px] transition-colors',
								activeTab === 'phases' ? 'bg-brand/20 text-brand' : 'text-text-secondary hover:text-text-primary',
							)}
						>
							Phases
						</button>
						<button
							onClick={() => setActiveTab('events')}
							className={cn(
								'rounded px-2 py-1 text-[11px] transition-colors',
								activeTab === 'events' ? 'bg-brand/20 text-brand' : 'text-text-secondary hover:text-text-primary',
							)}
						>
							Events
						</button>
					</div>
				</div>

				{activeTab === 'phases' ? (
					<div className="space-y-0">
						{phases.map((phase, idx) => (
							<div key={phase.index} className="relative flex gap-3">
								<div className="flex flex-col items-center">
									<div
										className={cn(
											'flex size-5 shrink-0 items-center justify-center rounded-full border',
											phase.status === 'completed'
												? 'border-success bg-success/10'
												: phase.status === 'error'
													? 'border-error bg-error/10'
													: ['generating', 'implementing', 'active', 'validating'].includes(phase.status)
														? 'border-brand bg-brand/10'
														: 'border-border bg-surface-tertiary',
										)}
									>
										<StatusIcon status={phase.status} />
									</div>
									{idx < phases.length - 1 && <div className="w-px flex-1 bg-border" />}
								</div>
								<div className="min-w-0 flex-1 pb-3">
									<div className="flex items-center gap-2">
										<span className="text-sm font-medium text-text-primary">{phase.name}</span>
										<span
											className={cn(
												'text-xs',
												phase.status === 'completed'
													? 'text-success'
													: phase.status === 'error'
														? 'text-error'
														: ['generating', 'implementing'].includes(phase.status)
															? 'text-brand'
															: 'text-text-muted',
											)}
										>
											{statusLabel(phase.status)}
										</span>
									</div>
									{phase.description && <p className="mt-0.5 text-xs text-text-secondary">{phase.description}</p>}
									{phase.files && phase.files.length > 0 && (
										<div className="mt-1.5 flex flex-wrap gap-1">
											{phase.files.map((f) => (
												<span key={`${phase.index}-${f}`} className="rounded bg-surface-tertiary px-1.5 py-0.5 text-[10px] text-text-secondary">
													{f.split('/').pop()}
												</span>
											))}
										</div>
									)}
								</div>
							</div>
						))}
					</div>
				) : (
					<div className="space-y-1">
						{eventItems.length === 0 ? (
							<p className="text-xs text-text-muted">No events yet.</p>
						) : (
							eventItems.map((event, idx) => (
								<div key={`event-${idx}`} className="rounded-md bg-surface-tertiary px-2 py-1 text-xs text-text-secondary">
									{event}
								</div>
							))
						)}
					</div>
				)}
			</div>
		</div>
	);
}
