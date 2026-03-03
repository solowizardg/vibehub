import { type KeyboardEvent, useRef, useState } from 'react';
import { ArrowRight, Square } from 'lucide-react';
import { cn } from '@/lib/cn';
import { SelectedElementCard } from './selected-element-card';
import type { SelectedElement } from '@/types/websocket';

interface ChatInputProps {
	onSend: (message: string) => void;
	onStop?: () => void;
	isGenerating?: boolean;
	disabled?: boolean;
	placeholder?: string;
	selectedElement?: SelectedElement | null;
	onClearSelection?: () => void;
}

export function ChatInput({ onSend, onStop, isGenerating, disabled, placeholder, selectedElement, onClearSelection }: ChatInputProps) {
	const [value, setValue] = useState('');
	const textareaRef = useRef<HTMLTextAreaElement>(null);

	const handleSubmit = () => {
		const trimmed = value.trim();
		if (!trimmed || disabled) return;
		onSend(trimmed);
		setValue('');
		if (textareaRef.current) textareaRef.current.style.height = '36px';
	};

	const handleKeyDown = (e: KeyboardEvent) => {
		if (e.key === 'Enter' && !e.shiftKey) {
			e.preventDefault();
			handleSubmit();
		}
	};

	const handleInput = () => {
		const el = textareaRef.current;
		if (!el) return;
		el.style.height = '36px';
		el.style.height = `${Math.min(el.scrollHeight, 120)}px`;
	};

	const inputPlaceholder = selectedElement
		? `Describe how to modify ${selectedElement.component || selectedElement.tagName}...`
		: (placeholder ?? 'Describe what you want to build...');

	return (
		<div className="border-t border-border p-4 pb-5">
			{selectedElement && onClearSelection && (
				<div className="mb-3">
					<SelectedElementCard
						element={selectedElement}
						onClear={onClearSelection}
					/>
				</div>
			)}
			<div className="flex items-end gap-2 rounded-xl border border-border bg-surface-secondary p-2">
				<textarea
					ref={textareaRef}
					value={value}
					onChange={(e) => setValue(e.target.value)}
					onKeyDown={handleKeyDown}
					onInput={handleInput}
					placeholder={inputPlaceholder}
					disabled={disabled}
					rows={1}
					className={cn(
						'flex-1 resize-none bg-transparent px-2 py-1 text-sm text-text-primary outline-none placeholder:text-text-muted',
						disabled && 'opacity-50',
					)}
					style={{ height: '36px', maxHeight: '120px' }}
				/>
				<div className="flex items-center gap-1">
					{isGenerating && onStop ? (
						<button onClick={onStop} className="flex size-8 items-center justify-center rounded-lg bg-error/20 text-error transition-colors hover:bg-error/30" title="Stop generation">
							<Square size={14} />
						</button>
					) : null}
					<button
						onClick={handleSubmit}
						disabled={!value.trim() || disabled}
						className={cn(
							'flex size-8 items-center justify-center rounded-lg bg-brand text-white transition-colors hover:bg-brand-dark',
							(!value.trim() || disabled) && 'cursor-not-allowed opacity-40',
						)}
					>
						<ArrowRight size={16} />
					</button>
				</div>
			</div>
		</div>
	);
}
