import { Check, Circle, Loader2, X } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import type { PhaseData } from '@/types/websocket';
import { cn } from '@/lib/cn';

interface PhaseTimelineProps {
	phases: PhaseData[];
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

export function PhaseTimeline({ phases }: PhaseTimelineProps) {
	if (phases.length === 0) return null;

	return (
		<div className="px-4 py-3">
			<div className="rounded-xl border border-border bg-surface-secondary p-3">
				<h3 className="mb-3 text-xs font-semibold uppercase tracking-wider text-text-secondary">Generation Progress</h3>
				<div className="space-y-0">
					<AnimatePresence mode="popLayout">
						{phases.map((phase, idx) => (
							<motion.div
								key={phase.index}
								initial={{ opacity: 0, height: 0 }}
								animate={{ opacity: 1, height: 'auto' }}
								exit={{ opacity: 0, height: 0 }}
								className="relative flex gap-3"
							>
								{/* Connector line */}
								<div className="flex flex-col items-center">
									<div className={cn('flex size-5 shrink-0 items-center justify-center rounded-full border', phase.status === 'completed' ? 'border-success bg-success/10' : phase.status === 'error' ? 'border-error bg-error/10' : ['generating', 'implementing', 'active', 'validating'].includes(phase.status) ? 'border-brand bg-brand/10' : 'border-border bg-surface-tertiary')}>
										<StatusIcon status={phase.status} />
									</div>
									{idx < phases.length - 1 && <div className="w-px flex-1 bg-border" />}
								</div>

								{/* Content */}
								<div className="min-w-0 flex-1 pb-4">
									<div className="flex items-center gap-2">
										<span className="text-sm font-medium text-text-primary">{phase.name}</span>
										<span className={cn('text-xs', phase.status === 'completed' ? 'text-success' : phase.status === 'error' ? 'text-error' : ['generating', 'implementing'].includes(phase.status) ? 'text-brand' : 'text-text-muted')}>
											{statusLabel(phase.status)}
										</span>
									</div>
									{phase.description && <p className="mt-0.5 text-xs text-text-secondary">{phase.description}</p>}
									{phase.files && phase.files.length > 0 && (
										<div className="mt-1.5 flex flex-wrap gap-1">
											{phase.files.map((f) => (
												<span key={f} className="rounded bg-surface-tertiary px-1.5 py-0.5 text-[10px] text-text-secondary">
													{f.split('/').pop()}
												</span>
											))}
										</div>
									)}
								</div>
							</motion.div>
						))}
					</AnimatePresence>
				</div>
			</div>
		</div>
	);
}
