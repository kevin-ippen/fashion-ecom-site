import { Check } from 'lucide-react';

interface SizeSelectorProps {
  sizes: string[];
  selectedSize?: string;
  onSizeSelect: (size: string) => void;
  unavailableSizes?: string[];
}

// Common size order for fashion items
const SIZE_ORDER = ['XXS', 'XS', 'S', 'M', 'L', 'XL', 'XXL', '2XL', '3XL'];

export function SizeSelector({ 
  sizes, 
  selectedSize, 
  onSizeSelect,
  unavailableSizes = []
}: SizeSelectorProps) {
  // Sort sizes by standard fashion order
  const sortedSizes = [...sizes].sort((a, b) => {
    const aIndex = SIZE_ORDER.indexOf(a);
    const bIndex = SIZE_ORDER.indexOf(b);
    if (aIndex === -1 && bIndex === -1) return a.localeCompare(b);
    if (aIndex === -1) return 1;
    if (bIndex === -1) return -1;
    return aIndex - bIndex;
  });

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-body font-medium text-foreground">Size</h3>
        <button className="text-body-sm text-primary hover:underline underline-offset-2">
          Size Guide
        </button>
      </div>

      {/* Size grid */}
      <div className="grid grid-cols-4 gap-2">
        {sortedSizes.map((size) => {
          const isSelected = selectedSize === size;
          const isUnavailable = unavailableSizes.includes(size);

          return (
            <button
              key={size}
              onClick={() => !isUnavailable && onSizeSelect(size)}
              disabled={isUnavailable}
              className={`
                relative h-12 rounded-md border-2 font-medium text-sm
                transition-all duration-200
                ${isSelected 
                  ? 'border-primary bg-primary text-white' 
                  : isUnavailable
                    ? 'border-border bg-muted text-muted-foreground cursor-not-allowed line-through'
                    : 'border-border bg-white hover:border-primary hover:bg-primary/5'
                }
              `}
            >
              <span>{size}</span>
              
              {/* Checkmark for selected */}
              {isSelected && (
                <Check className="absolute top-1 right-1 h-3 w-3" strokeWidth={3} />
              )}
            </button>
          );
        })}
      </div>

      {/* Selected size display */}
      {selectedSize && (
        <p className="text-body-sm text-muted-foreground">
          Selected: <span className="font-medium text-foreground">{selectedSize}</span>
        </p>
      )}
    </div>
  );
}
