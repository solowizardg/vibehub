import { useState } from 'react';
import { ChevronDown, FileCode, FolderTree, Layers } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import Markdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import type { BlueprintData } from '@/types/api';
import { cn } from '@/lib/cn';

interface BlueprintCardProps {
	blueprint: BlueprintData;
	blueprintMarkdown?: string | null;
}

export function BlueprintCard({ blueprint, blueprintMarkdown }: BlueprintCardProps) {
	const [expanded, setExpanded] = useState(true);

	const totalFiles = blueprint.phases.reduce((acc, p) => acc + p.files.length, 0);

	return (
		<div className="px-4 py-3">
			<div className="rounded-xl border border-brand/30 bg-brand/5">
				<button
					onClick={() => setExpanded(!expanded)}
					className="flex w-full items-center gap-3 px-4 py-3 text-left"
				>
					<div className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-brand/10">
						<FolderTree size={16} className="text-brand" />
					</div>
					<div className="min-w-0 flex-1">
						<h3 className="text-sm font-semibold text-text-primary">{blueprint.project_name}</h3>
						<p className="truncate text-xs text-text-secondary">{blueprint.description}</p>
					</div>
					<div className="flex items-center gap-2 text-xs text-text-muted">
						<span className="flex items-center gap-1">
							<Layers size={12} />
							{blueprint.phases.length} phases
						</span>
						<span className="flex items-center gap-1">
							<FileCode size={12} />
							{totalFiles} files
						</span>
						<ChevronDown
							size={14}
							className={cn('transition-transform', expanded && 'rotate-180')}
						/>
					</div>
				</button>

				<AnimatePresence>
					{expanded && (
						<motion.div
							initial={{ height: 0, opacity: 0 }}
							animate={{ height: 'auto', opacity: 1 }}
							exit={{ height: 0, opacity: 0 }}
							transition={{ duration: 0.2 }}
							className="overflow-hidden"
						>
							<div className="border-t border-brand/20 px-4 py-3">
							<div className="space-y-3">
								{blueprintMarkdown && (
									<div className="rounded-lg bg-surface-secondary/60 p-3">
										<p className="mb-2 font-mono text-[11px] uppercase tracking-wider text-text-muted">
											Blueprint.md
										</p>
										<div
											className={cn(
												'text-xs leading-relaxed text-text-secondary',
												'[&_h1]:mb-2 [&_h1]:text-base [&_h1]:font-semibold [&_h1]:text-text-primary',
												'[&_h2]:mb-1 [&_h2]:mt-3 [&_h2]:text-sm [&_h2]:font-semibold [&_h2]:text-text-primary',
												'[&_h3]:mb-1 [&_h3]:mt-2 [&_h3]:text-xs [&_h3]:font-semibold [&_h3]:text-text-primary',
												'[&_p]:mb-2',
												'[&_ul]:mb-2 [&_ul]:ml-4 [&_ul]:list-disc',
												'[&_ol]:mb-2 [&_ol]:ml-4 [&_ol]:list-decimal',
												'[&_code]:rounded [&_code]:bg-surface-tertiary [&_code]:px-1 [&_code]:py-0.5 [&_code]:font-mono [&_code]:text-[11px]',
											)}
										>
											<Markdown remarkPlugins={[remarkGfm]}>{blueprintMarkdown}</Markdown>
										</div>
									</div>
								)}

								{blueprint.phases.map((phase, idx) => (
										<div key={idx} className="rounded-lg bg-surface-secondary/60 p-3">
											<div className="mb-1 flex items-center gap-2">
												<span className="flex size-5 items-center justify-center rounded-full bg-brand/10 text-[10px] font-bold text-brand">
													{idx + 1}
												</span>
												<span className="text-xs font-medium text-text-primary">{phase.name}</span>
											</div>
											{phase.description && (
												<p className="mb-2 pl-7 text-[11px] leading-relaxed text-text-secondary">
													{phase.description}
												</p>
											)}
											{phase.files.length > 0 && (
												<div className="flex flex-wrap gap-1 pl-7">
													{phase.files.map((f) => (
														<span
															key={f}
															className="rounded bg-surface-tertiary px-1.5 py-0.5 font-mono text-[10px] text-text-secondary"
														>
															{f}
														</span>
													))}
												</div>
											)}
										</div>
									))}
								</div>
							</div>
						</motion.div>
					)}
				</AnimatePresence>
			</div>
		</div>
	);
}
