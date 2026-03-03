import { X, Edit3 } from "lucide-react";

interface HighlightOverlayProps {
  targetRect: DOMRect | null;
  componentName: string;
  filePath: string;
  onEdit: () => void;
  onClose: () => void;
}

export function HighlightOverlay({
  targetRect,
  componentName,
  onEdit,
  onClose
}: HighlightOverlayProps) {
  if (!targetRect) return null;

  return (
    <>
      {/* Highlight border */}
      <div
        className="fixed pointer-events-none z-40 border-2 border-blue-500 bg-blue-500/10 rounded"
        style={{
          left: targetRect.left,
          top: targetRect.top,
          width: targetRect.width,
          height: targetRect.height,
        }}
      />

      {/* Component label */}
      <div
        className="fixed z-50 bg-blue-500 text-white px-3 py-1 rounded-t text-sm font-medium flex items-center gap-2"
        style={{
          left: targetRect.left,
          top: targetRect.top - 32,
        }}
      >
        <span>{componentName}</span>
        <button
          onClick={onClose}
          className="hover:bg-blue-600 rounded p-0.5"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Action buttons */}
      <div
        className="fixed z-50 flex gap-2"
        style={{
          left: targetRect.left,
          top: targetRect.bottom + 8,
        }}
      >
        <button
          onClick={onEdit}
          className="flex items-center gap-2 px-3 py-1.5 bg-blue-500 text-white text-sm font-medium rounded-md hover:bg-blue-600 transition-colors"
        >
          <Edit3 className="w-4 h-4" />
          Edit here
        </button>
        <button
          onClick={onClose}
          className="px-3 py-1.5 border border-gray-300 text-gray-700 text-sm font-medium rounded-md hover:bg-gray-50 transition-colors"
        >
          Cancel
        </button>
      </div>
    </>
  );
}
