import { Check } from 'lucide-react';

interface ColorSwatchesProps {
  colors: string[];
  selectedColor?: string;
  onColorSelect: (color: string | undefined) => void;
}

// Map color names to hex values for visual representation
// Using common fashion color mappings
const COLOR_HEX_MAP: Record<string, string> = {
  // Neutrals
  'Black': '#000000',
  'White': '#FFFFFF',
  'Grey': '#808080',
  'Beige': '#F5F5DC',
  'Brown': '#8B4513',
  'Tan': '#D2B48C',
  'Cream': '#FFFDD0',
  'Off White': '#FAF9F6',
  'Charcoal': '#36454F',

  // Blues
  'Blue': '#0000FF',
  'Navy Blue': '#000080',
  'Navy': '#000080',
  'Teal': '#008080',
  'Turquoise Blue': '#40E0D0',
  'Sea Green': '#2E8B57',

  // Reds & Pinks
  'Red': '#FF0000',
  'Maroon': '#800000',
  'Burgundy': '#800020',
  'Pink': '#FFC0CB',
  'Rose': '#FF007F',
  'Magenta': '#FF00FF',
  'Rust': '#B7410E',

  // Purples
  'Purple': '#800080',
  'Lavender': '#E6E6FA',
  'Mauve': '#E0B0FF',

  // Greens
  'Green': '#008000',
  'Olive': '#808000',
  'Khaki': '#C3B091',
  'Lime Green': '#32CD32',
  'Fluorescent Green': '#39FF14',

  // Yellows & Oranges
  'Yellow': '#FFFF00',
  'Gold': '#FFD700',
  'Mustard': '#FFDB58',
  'Orange': '#FFA500',
  'Peach': '#FFE5B4',
  'Copper': '#B87333',

  // Metallics
  'Silver': '#C0C0C0',
  'Bronze': '#CD7F32',
  'Metallic': '#AAA9AD',
  'Gold Metallic': '#D4AF37',

  // Multi & Special
  'Multi': 'linear-gradient(135deg, #FF0000 0%, #00FF00 50%, #0000FF 100%)',
  'Multicolor': 'linear-gradient(135deg, #FF0000 0%, #00FF00 50%, #0000FF 100%)',
  'Multicolour': 'linear-gradient(135deg, #FF0000 0%, #00FF00 50%, #0000FF 100%)',
  'Fluorescent': '#CCFF00',
  'Neon': '#39FF14',
};

// Get hex color or fallback to a default
const getColorHex = (colorName: string): string => {
  return COLOR_HEX_MAP[colorName] || '#CCCCCC'; // Default to light gray
};

// Check if color needs a border (light colors on white background)
const needsBorder = (colorName: string): boolean => {
  const lightColors = ['White', 'Cream', 'Off White', 'Beige', 'Yellow', 'Peach', 'Lavender'];
  return lightColors.includes(colorName);
};

export function ColorSwatches({ colors, selectedColor, onColorSelect }: ColorSwatchesProps) {
  const handleColorClick = (color: string) => {
    // Toggle: if clicking the same color, deselect it
    if (selectedColor === color) {
      onColorSelect(undefined);
    } else {
      onColorSelect(color);
    }
  };

  return (
    <div className="space-y-3">
      <h3 className="text-micro text-muted-foreground font-semibold">Color</h3>

      <div className="flex flex-wrap gap-3">
        {colors.map((color) => {
          const isSelected = selectedColor === color;
          const hexColor = getColorHex(color);
          const showBorder = needsBorder(color);
          const isGradient = hexColor.startsWith('linear-gradient');

          return (
            <button
              key={color}
              onClick={() => handleColorClick(color)}
              className={`
                group relative flex flex-col items-center gap-2
                transition-all duration-200 ease-out
                hover:scale-110
                ${isSelected ? 'scale-105' : ''}
              `}
              title={color}
            >
              {/* Color circle */}
              <div
                className={`
                  w-10 h-10 rounded-full
                  transition-all duration-200
                  ${showBorder ? 'ring-1 ring-border' : ''}
                  ${isSelected ? 'ring-2 ring-primary ring-offset-2' : ''}
                  ${!isSelected ? 'hover:ring-2 hover:ring-muted-foreground/30 hover:ring-offset-2' : ''}
                  relative overflow-hidden
                `}
                style={{
                  background: hexColor,
                }}
              >
                {/* Checkmark for selected state */}
                {isSelected && (
                  <div className="absolute inset-0 flex items-center justify-center bg-black/20">
                    <Check
                      className={`h-5 w-5 ${
                        color === 'Black' || color === 'Navy Blue' || color === 'Navy' || color === 'Charcoal'
                          ? 'text-white'
                          : 'text-foreground'
                      }`}
                      strokeWidth={3}
                    />
                  </div>
                )}
              </div>

              {/* Color label - show on hover or when selected */}
              <span
                className={`
                  text-micro text-muted-foreground text-center
                  max-w-[60px] truncate
                  transition-opacity duration-200
                  ${isSelected ? 'opacity-100 font-semibold' : 'opacity-0 group-hover:opacity-100'}
                `}
              >
                {color}
              </span>
            </button>
          );
        })}
      </div>

      {/* Show selected color name prominently if one is selected */}
      {selectedColor && (
        <div className="flex items-center gap-2 pt-2 border-t border-border">
          <span className="text-body-sm text-muted-foreground">Selected:</span>
          <span className="text-body-sm font-medium">{selectedColor}</span>
          <button
            onClick={() => onColorSelect(undefined)}
            className="ml-auto text-body-sm text-muted-foreground hover:text-foreground transition-colors underline"
          >
            Clear
          </button>
        </div>
      )}
    </div>
  );
}
