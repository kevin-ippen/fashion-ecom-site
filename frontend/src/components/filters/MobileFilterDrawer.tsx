import { X } from 'lucide-react';
import { ReactNode } from 'react';

interface MobileFilterDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  onApply: () => void;
  children: ReactNode;
  filterCount: number;
  resultCount: number;
}

export function MobileFilterDrawer({
  isOpen,
  onClose,
  onApply,
  children,
  filterCount,
  resultCount,
}: MobileFilterDrawerProps) {
  if (!isOpen) return null;

  const handleApply = () => {
    onApply();
    onClose();
  };

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/60 z-50 animate-fade-in lg:hidden"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Drawer */}
      <div className="fixed inset-x-0 bottom-0 top-0 z-50 flex flex-col bg-white animate-slide-in-right lg:hidden">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-border px-4 py-4 bg-white sticky top-0 z-10">
          <div>
            <h2 className="text-title-lg font-semibold">Filters</h2>
            {filterCount > 0 && (
              <p className="text-body-sm text-muted-foreground mt-1">
                {filterCount} active filter{filterCount !== 1 ? 's' : ''}
              </p>
            )}
          </div>
          <button
            onClick={onClose}
            className="p-2 hover:bg-accent rounded-full transition-colors"
            aria-label="Close filters"
          >
            <X className="h-6 w-6" />
          </button>
        </div>

        {/* Filter Content - Scrollable */}
        <div className="flex-1 overflow-y-auto px-4 py-6">
          {children}
        </div>

        {/* Footer with Apply Button */}
        <div className="border-t border-border p-4 bg-white sticky bottom-0 space-y-3">
          {/* Result count preview */}
          <div className="text-center text-body-sm text-muted-foreground">
            {resultCount.toLocaleString()} product{resultCount !== 1 ? 's' : ''} found
          </div>

          {/* Action buttons */}
          <div className="flex gap-2">
            <button
              onClick={onClose}
              className="btn btn-ghost btn-lg flex-1"
            >
              Cancel
            </button>
            <button
              onClick={handleApply}
              className="btn btn-primary btn-lg flex-1"
            >
              Apply Filters
            </button>
          </div>
        </div>
      </div>
    </>
  );
}
