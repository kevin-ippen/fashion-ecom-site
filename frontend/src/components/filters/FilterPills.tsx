import { X } from 'lucide-react';
import { ProductFilters } from '@/types';

interface FilterPillsProps {
  filters: ProductFilters;
  onRemoveFilter: (key: keyof ProductFilters) => void;
  onClearAll: () => void;
}

// Helper to format filter labels
const getFilterLabel = (key: keyof ProductFilters, value: any): string => {
  const labels: Record<string, string> = {
    gender: 'Gender',
    master_category: 'Category',
    sub_category: 'Sub-category',
    base_color: 'Color',
    season: 'Season',
    min_price: 'Min Price',
    max_price: 'Max Price',
  };

  const label = labels[key] || key;

  // Format value display
  if (key === 'min_price' || key === 'max_price') {
    return `${label}: $${value}`;
  }

  return `${label}: ${value}`;
};

export function FilterPills({ filters, onRemoveFilter, onClearAll }: FilterPillsProps) {
  // Get active filters (non-undefined values)
  const activeFilters = Object.entries(filters).filter(([_, value]) => value !== undefined);

  // Don't render anything if no active filters
  if (activeFilters.length === 0) {
    return null;
  }

  return (
    <div className="flex items-center gap-2 flex-wrap pb-4 mb-6 border-b border-border">
      {/* Label */}
      <span className="text-body-sm text-muted-foreground font-medium">
        Active Filters:
      </span>

      {/* Filter Pills */}
      {activeFilters.map(([key, value]) => (
        <button
          key={key}
          onClick={() => onRemoveFilter(key as keyof ProductFilters)}
          className="
            inline-flex items-center gap-1.5
            px-3 py-1.5 rounded-full
            bg-primary/10 text-primary
            border border-primary/20
            text-body-sm font-medium
            hover:bg-primary/20 hover:border-primary/30
            transition-all duration-200
            group
          "
        >
          <span>{getFilterLabel(key as keyof ProductFilters, value)}</span>
          <X className="h-3.5 w-3.5 group-hover:scale-110 transition-transform" />
        </button>
      ))}

      {/* Clear All button - only show if 2+ filters */}
      {activeFilters.length >= 2 && (
        <button
          onClick={onClearAll}
          className="
            ml-2 text-body-sm text-muted-foreground
            hover:text-foreground underline-offset-2 hover:underline
            transition-colors
          "
        >
          Clear all
        </button>
      )}
    </div>
  );
}
