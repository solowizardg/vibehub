import { useState } from 'react';
import { Check, ChevronDown, ChevronUp, FileCode, Layers, Palette, Sparkles } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import Markdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import type { BlueprintVariant } from '@/types/api';
import { cn } from '@/lib/cn';

interface BlueprintVariantsComparisonProps {
	variants: BlueprintVariant[];
	selectedVariantId: string | null;
	onSelectVariant: (variantId: string) => void;
	isLoading?: boolean;
}

const styleIcons: Record<string, React.ReactNode> = {
	'Modern Minimalist': <Sparkles className="size-4" />,
	'Vibrant Creative': <Palette className="size-4" />,
	'Enterprise Professional': <FileCode className="size-4" />,
};

const styleGradients: Record<string, string> = {
	'Modern Minimalist': 'from-slate-500/20 to-blue-500/20',
	'Vibrant Creative': 'from-pink-500/20 to-purple-500/20',
	'Enterprise Professional': 'from-blue-600/20 to-cyan-500/20',
};

const styleBorderColors: Record<string, string> = {
	'Modern Minimalist': 'border-slate-400/50',
	'Vibrant Creative': 'border-pink-400/50',
	'Enterprise Professional': 'border-blue-400/50',
};

function VariantCard({
	variant,
	isSelected,
	isExpanded,
	onToggleExpand,
	onSelect,
	index,
}: {
	variant: BlueprintVariant;
	isSelected: boolean;
	isExpanded: boolean;
	onToggleExpand: () => void;
	onSelect: () => void;
	index: number;
}) {
	const totalFiles = variant.phases?.reduce((acc, p) => acc + (p.files?.length || 0), 0) || 0;
	const totalPhases = variant.phases?.length || 0;
	const styleName = variant.style_name;
	const icon = styleIcons[styleName] || <Layers className="size-4" />;
	const gradient = styleGradients[styleName] || 'from-gray-500/20 to-gray-600/20';
	const borderColor = isSelected
		? (styleBorderColors[styleName] || 'border-brand')
		: 'border-transparent';

	return (
		<motion.div
			initial={{ opacity: 0, y: 20 }}
			animate={{ opacity: 1, y: 0 }}
			transition={{ delay: index * 0.1 }}
			className={cn(
				'relative overflow-hidden rounded-xl border-2 bg-surface-secondary transition-all duration-300',
				isSelected ? borderColor : 'border-transparent hover:border-surface-tertiary',
				isSelected && 'ring-2 ring-brand/20'
			)}
		>
			{/* Gradient background */}
			<div className={cn('absolute inset-0 bg-gradient-to-br opacity-50', gradient)} />

			{/* Selection indicator */}
			{isSelected && (
				<div className="absolute right-3 top-3 flex size-6 items-center justify-center rounded-full bg-brand text-white">
					<Check className="size-4" />
				</div>
			)}

			<div className="relative">
				{/* Header */}
				<button
					onClick={onToggleExpand}
					className="flex w-full items-start gap-3 p-4 text-left"
				>
					<div className={cn(
						'flex size-10 shrink-0 items-center justify-center rounded-lg bg-surface-tertiary',
						isSelected && 'bg-brand/10 text-brand'
					)}>
						{icon}
					</div>
					<div className="min-w-0 flex-1">
						<h3 className="text-sm font-semibold text-text-primary">{variant.style_name}</h3>
						<p className="mt-0.5 text-xs text-text-secondary line-clamp-2">{variant.style_description}</p>
					</div>
					<div className="flex shrink-0 flex-col items-end gap-1">
						{isExpanded ? (
							<ChevronUp className="size-4 text-text-muted" />
						) : (
							<ChevronDown className="size-4 text-text-muted" />
						)}
					</div>
				</button>

				{/* Quick stats */}
				<div className="flex items-center gap-4 px-4 pb-3">
					<div className="flex items-center gap-1.5 text-xs text-text-muted">
						<Layers className="size-3.5" />
						<span>{totalPhases} phases</span>
					</div>
					<div className="flex items-center gap-1.5 text-xs text-text-muted">
						<FileCode className="size-3.5" />
						<span>{totalFiles} files</span>
					</div>
				</div>

				{/* Expanded content */}
				<AnimatePresence>
					{isExpanded && (
						<motion.div
							initial={{ height: 0, opacity: 0 }}
							animate={{ height: 'auto', opacity: 1 }}
							exit={{ height: 0, opacity: 0 }}
							transition={{ duration: 0.2 }}
							className="overflow-hidden border-t border-surface-tertiary"
						>
							<div className="space-y-4 p-4">
								{/* Project info */}
								<div>
									<h4 className="text-xs font-medium uppercase tracking-wider text-text-muted">Project</h4>
									<p className="mt-1 text-sm font-medium text-text-primary">{variant.project_name}</p>
									<p className="mt-0.5 text-xs text-text-secondary">{variant.description}</p>
								</div>

								{/* Blueprint markdown preview */}
								{variant.blueprint_markdown && (
									<div className="rounded-lg bg-surface-tertiary/50 p-3">
										<h4 className="mb-2 text-xs font-medium uppercase tracking-wider text-text-muted">
											Design Blueprint
										</h4>
										<div
											className={cn(
												'text-xs leading-relaxed text-text-secondary max-h-48 overflow-y-auto',
												'[&_h1]:mb-2 [&_h1]:text-sm [&_h1]:font-semibold [&_h1]:text-text-primary',
												'[&_h2]:mb-1 [&_h2]:mt-2 [&_h2]:text-xs [&_h2]:font-semibold [&_h2]:text-text-primary',
												'[&_h3]:mb-1 [&_h3]:mt-2 [&_h3]:text-[11px] [&_h3]:font-semibold [&_h3]:text-text-primary',
												'[&_p]:mb-2',
												'[&_ul]:mb-2 [&_ul]:ml-3 [&_ul]:list-disc',
												'[&_ol]:mb-2 [&_ol]:ml-3 [&_ol]:list-decimal',
												'[&_code]:rounded [&_code]:bg-surface-tertiary [&_code]:px-1 [&_code]:py-0.5 [&_code]:font-mono [&_code]:text-[10px]',
											)}
										>
											<Markdown remarkPlugins={[remarkGfm]}>
												{variant.blueprint_markdown.slice(0, 2000)}
											</Markdown>
										</div>
									</div>
								)}

								{/* Phases summary */}
								{variant.phases && variant.phases.length > 0 && (
									<div>
										<h4 className="mb-2 text-xs font-medium uppercase tracking-wider text-text-muted">
											Implementation Phases
										</h4>
										<div className="space-y-2">
											{variant.phases.map((phase, idx) => (
												<div
													key={idx}
													className="flex items-start gap-2 rounded-md bg-surface-tertiary/50 p-2"
												>
													<span className="flex size-5 shrink-0 items-center justify-center rounded-full bg-brand/10 text-[10px] font-bold text-brand">
														{idx + 1}
													</span>
													<div className="min-w-0 flex-1">
														<p className="text-xs font-medium text-text-primary">{phase.name}</p>
														{phase.description && (
															<p className="mt-0.5 text-[11px] text-text-secondary line-clamp-1">
															{phase.description}
															</p>
														)}
														{phase.files && phase.files.length > 0 && (
															<div className="mt-1 flex flex-wrap gap-1">
																{phase.files.slice(0, 3).map((f) => (
																	<span
																		key={f}
																		className="rounded bg-surface-tertiary px-1 py-0.5 font-mono text-[9px] text-text-muted"
																	>
																		{f.split('/').pop()}
																	</span>
																))}
																{phase.files.length > 3 && (
																	<span className="text-[9px] text-text-muted">
																		+{phase.files.length - 3} more
																	</span>
																)}
															</div>
														)}
													</div>
												</div>
											))}
										</div>
									</div>
								)}

								{/* Select button */}
								<button
									onClick={onSelect}
									disabled={isSelected}
									className={cn(
										'w-full rounded-lg px-4 py-2 text-sm font-medium transition-colors',
										isSelected
											? 'bg-surface-tertiary text-text-secondary cursor-not-allowed'
											: 'bg-brand text-white hover:bg-brand/90'
									)}
								>
									{isSelected ? (
										<span className="flex items-center justify-center">
											<Check className="mr-1.5 size-4" />
											Selected
										</span>
									) : (
										'Select This Design'
									)}
								</button>
							</div>
						</motion.div>
					)}
				</AnimatePresence>
			</div>
		</motion.div>
	);
}

export function BlueprintVariantsComparison({
	variants,
	selectedVariantId,
	onSelectVariant,
	isLoading,
}: BlueprintVariantsComparisonProps) {
	const [expandedVariantId, setExpandedVariantId] = useState<string | null>(null);

	if (isLoading) {
		return (
			<div className="space-y-4 p-4">
				<div className="text-center">
					<div className="mx-auto mb-3 size-8 animate-spin rounded-full border-2 border-brand border-t-transparent" />
					<p className="text-sm text-text-secondary">Generating blueprint variants...</p>
				</div>
				<div className="grid gap-4 md:grid-cols-3">
					{[1, 2, 3].map((i) => (
						<div
							key={i}
							className="h-48 animate-pulse rounded-xl bg-surface-secondary"
						/>
					))}
				</div>
			</div>
		);
	}

	if (!variants || variants.length === 0) {
		return null;
	}

	return (
		<div className="space-y-4 p-4">
			<div className="text-center">
				<h2 className="text-lg font-semibold text-text-primary">Choose Your Design</h2>
				<p className="mt-1 text-sm text-text-secondary">
					We&apos;ve generated {variants.length} different design approaches. Select the one that best fits your vision.
				</p>
			</div>

			<div className="grid gap-4 md:grid-cols-3">
				{variants.map((variant, index) => (
					<VariantCard
						key={variant.variant_id}
						variant={variant}
						isSelected={selectedVariantId === variant.variant_id}
						isExpanded={expandedVariantId === variant.variant_id}
						onToggleExpand={() =>
							setExpandedVariantId(
								expandedVariantId === variant.variant_id ? null : variant.variant_id
							)
						}
						onSelect={() => onSelectVariant(variant.variant_id)}
						index={index}
					/>
				))}
			</div>

			{selectedVariantId && (
				<motion.div
					initial={{ opacity: 0, y: 10 }}
					animate={{ opacity: 1, y: 0 }}
					className="rounded-lg bg-brand/10 p-3 text-center"
				>
					<p className="text-sm text-text-primary">
						Design selected! Starting implementation...
					</p>
				</motion.div>
			)}
		</div>
	);
}
