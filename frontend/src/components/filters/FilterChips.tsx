import { cn } from '@/lib/utils';
import { X } from 'lucide-react';

interface FilterChipProps {
  label: string;
  selected: boolean;
  onClick: () => void;
}

export function FilterChip({ label, selected, onClick }: FilterChipProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        'inline-flex items-center gap-2 rounded-full px-4 py-2 font-sans text-sm font-medium transition-all duration-200',
        selected
          ? 'bg-stone-900 text-white shadow-md hover:bg-stone-800'
          : 'bg-stone-100 text-stone-700 hover:bg-stone-200'
      )}
    >
      <span>{label}</span>
      {selected && <X className="h-3 w-3" />}
    </button>
  );
}

interface FilterChipsGroupProps {
  title: string;
  options: string[];
  selectedOptions: string[];
  onToggle: (option: string) => void;
  multiSelect?: boolean;
}

export function FilterChipsGroup({
  title,
  options,
  selectedOptions,
  onToggle,
  multiSelect = false,
}: FilterChipsGroupProps) {
  const handleClick = (option: string) => {
    if (multiSelect) {
      onToggle(option);
    } else {
      // Single select: toggle off if already selected
      if (selectedOptions.includes(option)) {
        onToggle(option);
      } else {
        onToggle(option);
      }
    }
  };

  return (
    <div>
      <label className="mb-3 block font-sans text-sm font-medium tracking-wide uppercase text-stone-900">
        {title}
      </label>
      <div className="flex flex-wrap gap-2">
        {options.map((option) => (
          <FilterChip
            key={option}
            label={option}
            selected={selectedOptions.includes(option)}
            onClick={() => handleClick(option)}
          />
        ))}
      </div>
    </div>
  );
}
