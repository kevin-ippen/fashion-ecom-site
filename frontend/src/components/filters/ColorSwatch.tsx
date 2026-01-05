import { Check } from 'lucide-react';
import { cn } from '@/lib/utils';

// Map color names to hex values
const COLOR_MAP: Record<string, string> = {
  Black: '#1C1917',
  White: '#FAFAF9',
  Grey: '#78716C',
  Red: '#DC2626',
  Blue: '#2563EB',
  Green: '#16A34A',
  Yellow: '#EAB308',
  Pink: '#EC4899',
  Purple: '#9333EA',
  Orange: '#EA580C',
  Brown: '#92400E',
  Beige: '#D4C5B9',
  Navy: '#1E3A8A',
  Teal: '#0D9488',
  Maroon: '#7F1D1D',
  Olive: '#4D7C0F',
};

interface ColorSwatchProps {
  color: string;
  selected: boolean;
  onClick: () => void;
}

export function ColorSwatch({ color, selected, onClick }: ColorSwatchProps) {
  const hexColor = COLOR_MAP[color] || '#D1D5DB'; // Fallback to gray

  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        'relative h-10 w-10 rounded-full border-2 transition-all duration-200',
        selected
          ? 'border-stone-900 scale-110 shadow-md'
          : 'border-stone-200 hover:border-stone-400 hover:scale-105'
      )}
      style={{ backgroundColor: hexColor }}
      title={color}
      aria-label={`${selected ? 'Selected' : 'Select'} ${color}`}
    >
      {selected && (
        <div className="absolute inset-0 flex items-center justify-center">
          <Check
            className={cn(
              'h-5 w-5',
              color === 'White' || color === 'Yellow' || color === 'Beige'
                ? 'text-stone-900'
                : 'text-white'
            )}
          />
        </div>
      )}
      {/* Border ring for white swatch */}
      {color === 'White' && (
        <div className="absolute inset-0 rounded-full border border-stone-200" />
      )}
    </button>
  );
}

// Color filter component
interface ColorFilterProps {
  colors: string[];
  selectedColor?: string;
  onSelectColor: (color: string | undefined) => void;
}

export function ColorFilter({ colors, selectedColor, onSelectColor }: ColorFilterProps) {
  return (
    <div>
      <label className="mb-3 block font-sans text-sm font-medium tracking-wide uppercase text-stone-900">
        Color
      </label>
      <div className="flex flex-wrap gap-3">
        {colors.map((color) => (
          <ColorSwatch
            key={color}
            color={color}
            selected={selectedColor === color}
            onClick={() => onSelectColor(selectedColor === color ? undefined : color)}
          />
        ))}
      </div>
      {selectedColor && (
        <button
          type="button"
          onClick={() => onSelectColor(undefined)}
          className="mt-3 text-xs text-stone-600 hover:text-stone-900 underline-offset-2 hover:underline"
        >
          Clear
        </button>
      )}
    </div>
  );
}
