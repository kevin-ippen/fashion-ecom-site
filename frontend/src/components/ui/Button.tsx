import { ButtonHTMLAttributes, forwardRef } from 'react';
import { cn } from '@/lib/utils';

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'default' | 'outline' | 'ghost' | 'link' | 'luxury';
  size?: 'sm' | 'md' | 'lg';
}

const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = 'default', size = 'md', ...props }, ref) => {
    return (
      <button
        className={cn(
          // Base styles - refined and minimal
          'inline-flex items-center justify-center font-sans font-medium tracking-wide',
          'transition-all duration-300 ease-out',
          'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-stone-900 focus-visible:ring-offset-2',
          'disabled:opacity-40 disabled:pointer-events-none disabled:cursor-not-allowed',

          // Variant styles
          {
            // Default: Rich black with subtle shadow
            'bg-stone-900 text-white hover:bg-stone-800 shadow-sm hover:shadow-md':
              variant === 'default',

            // Luxury: Gold accent for premium CTAs
            'bg-amber-600 text-white hover:bg-amber-700 shadow-md hover:shadow-lg hover:translate-y-[-1px]':
              variant === 'luxury',

            // Outline: Minimal border
            'border border-stone-300 bg-transparent hover:bg-stone-50 hover:border-stone-400 text-stone-900':
              variant === 'outline',

            // Ghost: Invisible until hover
            'hover:bg-stone-100 text-stone-700 hover:text-stone-900':
              variant === 'ghost',

            // Link: Underline style
            'text-stone-900 underline-offset-4 hover:underline':
              variant === 'link',
          },

          // Size styles
          {
            'h-9 px-4 text-xs uppercase': size === 'sm',
            'h-11 px-6 text-sm': size === 'md',
            'h-13 px-10 text-base': size === 'lg',
          },

          className
        )}
        ref={ref}
        {...props}
      />
    );
  }
);

Button.displayName = 'Button';

export { Button };
