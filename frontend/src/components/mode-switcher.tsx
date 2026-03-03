import { cn } from "@/lib/cn";

interface ModeSwitcherProps {
  mode: 'preview' | 'select';
  onChange: (mode: 'preview' | 'select') => void;
}

export function ModeSwitcher({ mode, onChange }: ModeSwitcherProps) {
  return (
    <div className="inline-flex bg-gray-100 rounded-lg p-1">
      <button
        className={cn(
          "px-4 py-2 rounded-md text-sm font-medium transition-all",
          mode === 'preview'
            ? "bg-white text-gray-900 shadow-sm"
            : "text-gray-600 hover:text-gray-900"
        )}
        onClick={() => onChange('preview')}
      >
        Preview
      </button>
      <button
        className={cn(
          "px-4 py-2 rounded-md text-sm font-medium transition-all",
          mode === 'select'
            ? "bg-white text-blue-600 shadow-sm"
            : "text-gray-600 hover:text-gray-900"
        )}
        onClick={() => onChange('select')}
      >
        Select
      </button>
    </div>
  );
}
