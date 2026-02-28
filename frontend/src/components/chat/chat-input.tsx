import { type KeyboardEvent, useEffect, useRef, useState } from 'react';
import { ArrowRight, Square, X } from 'lucide-react';
import { cn } from '@/lib/cn';

interface SelectedComponent {
	component: string;
	filePath: string;
}

interface ChatInputProps {
	onSend: (message: string) => void;
	onStop?: () => void;
	isGenerating?: boolean;
	disabled?: boolean;
	placeholder?: string;
	selectedComponent?: SelectedComponent | null;
	onClearSelection?: () => void;
}

export function ChatInput({
	onSend,
	onStop,
	isGenerating,
	disabled,
	placeholder,
	selectedComponent,
	onClearSelection,
}: ChatInputProps) {
	const [value, setValue] = useState('');
	const textareaRef = useRef<HTMLTextAreaElement>(null);

	useEffect(() => {
		if (selectedComponent) {
			const prefix = `修改 ${selectedComponent.component} 组件：`;
			if (!value.startsWith(prefix)) {
				setValue(prefix);
				if (textareaRef.current) {
					textareaRef.current.focus();
				}
			}
		}
	}, [selectedComponent]);

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

	return (
		<div className="border-t border-border p-4 pb-5">
			{selectedComponent && (
				<div className="mb-2 flex items-center gap-2">
					<span className="inline-flex items-center gap-1.5 rounded-md bg-brand/20 px-2.5 py-1 text-sm text-brand">
						<span>修改 {selectedComponent.component}</span>
						<button
							onClick={onClearSelection}
							className="ml-1 rounded-sm p-0.5 hover:bg-brand/20"
							title="清除选择"
						>
							<X size={12} />
						</button>
					</span>
				</div>
			)}
			<div className="flex items-end gap-2 rounded-xl border border-border bg-surface-secondary p-2">
				<textarea
					ref={textareaRef}
					value={value}
					onChange={(e) => setValue(e.target.value)}
					onKeyDown={handleKeyDown}
					onInput={handleInput}
					placeholder={placeholder ?? 'Describe what you want to build...'}
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
