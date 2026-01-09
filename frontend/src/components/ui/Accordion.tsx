import { ChevronDown } from 'lucide-react';
import { useState } from 'react';

export interface AccordionItem {
  title: string;
  content: React.ReactNode;
  defaultOpen?: boolean;
}

interface AccordionProps {
  items: AccordionItem[];
}

export function Accordion({ items }: AccordionProps) {
  const [openIndexes, setOpenIndexes] = useState<Set<number>>(
    new Set(items.map((item, index) => item.defaultOpen ? index : -1).filter(i => i !== -1))
  );

  const toggleItem = (index: number) => {
    setOpenIndexes((prev) => {
      const newSet = new Set(prev);
      if (newSet.has(index)) {
        newSet.delete(index);
      } else {
        newSet.add(index);
      }
      return newSet;
    });
  };

  return (
    <div className="divide-y divide-border border-y border-border">
      {items.map((item, index) => {
        const isOpen = openIndexes.has(index);

        return (
          <div key={index} className="py-4">
            {/* Accordion Header */}
            <button
              onClick={() => toggleItem(index)}
              className="flex w-full items-center justify-between text-left transition-colors hover:text-primary"
            >
              <h3 className="text-body font-semibold text-foreground">
                {item.title}
              </h3>
              <ChevronDown
                className={`h-5 w-5 transition-transform duration-300 ${
                  isOpen ? 'rotate-180' : ''
                }`}
              />
            </button>

            {/* Accordion Content */}
            <div
              className={`overflow-hidden transition-all duration-300 ease-out ${
                isOpen ? 'max-h-96 opacity-100 mt-4' : 'max-h-0 opacity-0'
              }`}
            >
              <div className="text-body-sm text-muted-foreground space-y-2">
                {item.content}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
