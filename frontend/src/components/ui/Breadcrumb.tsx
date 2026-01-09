import { Link } from 'react-router-dom';
import { ChevronRight, Home } from 'lucide-react';

export interface BreadcrumbItem {
  label: string;
  href?: string;
}

interface BreadcrumbProps {
  items: BreadcrumbItem[];
  className?: string;
}

export function Breadcrumb({ items, className = '' }: BreadcrumbProps) {
  return (
    <nav aria-label="Breadcrumb" className={`flex items-center text-body-sm ${className}`}>
      <ol className="flex items-center flex-wrap gap-2">
        {/* Home link */}
        <li className="flex items-center">
          <Link
            to="/"
            className="text-muted-foreground hover:text-foreground transition-colors flex items-center gap-1"
            aria-label="Home"
          >
            <Home className="h-4 w-4" />
            <span className="sr-only">Home</span>
          </Link>
        </li>

        {/* Breadcrumb items */}
        {items.map((item, index) => {
          const isLast = index === items.length - 1;

          return (
            <li key={index} className="flex items-center gap-2">
              <ChevronRight className="h-4 w-4 text-muted-foreground" aria-hidden="true" />
              {item.href && !isLast ? (
                <Link
                  to={item.href}
                  className="text-muted-foreground hover:text-foreground transition-colors truncate max-w-[150px] md:max-w-none"
                >
                  {item.label}
                </Link>
              ) : (
                <span
                  className={`truncate max-w-[150px] md:max-w-none ${
                    isLast ? 'text-foreground font-medium' : 'text-muted-foreground'
                  }`}
                  aria-current={isLast ? 'page' : undefined}
                >
                  {item.label}
                </span>
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
