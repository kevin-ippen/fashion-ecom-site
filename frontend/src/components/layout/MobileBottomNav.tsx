import { Home, Search, Heart, User, ShoppingCart } from 'lucide-react';
import { Link, useLocation } from 'react-router-dom';
import { useCartStore } from '@/stores/cartStore';

export function MobileBottomNav() {
  const location = useLocation();
  const itemCount = useCartStore((state) => state.item_count);

  const navItems = [
    { icon: Home, label: 'Home', path: '/' },
    { icon: Search, label: 'Search', path: '/search' },
    { icon: Heart, label: 'Saved', path: '/wishlist' }, // Placeholder for future wishlist
    { icon: User, label: 'Account', path: '/profile' }, // Placeholder for account
    { icon: ShoppingCart, label: 'Cart', path: '/cart', badge: itemCount },
  ];

  const isActive = (path: string) => {
    if (path === '/') {
      return location.pathname === '/';
    }
    return location.pathname.startsWith(path);
  };

  return (
    <nav className="fixed bottom-0 left-0 right-0 z-50 bg-white border-t border-border shadow-2xl lg:hidden">
      <div className="flex items-center justify-around h-16 px-2">
        {navItems.map((item) => {
          const Icon = item.icon;
          const active = isActive(item.path);

          return (
            <Link
              key={item.path}
              to={item.path}
              className={`
                relative flex flex-col items-center justify-center
                flex-1 h-full gap-1
                transition-colors duration-200
                ${active 
                  ? 'text-primary' 
                  : 'text-muted-foreground hover:text-foreground'
                }
              `}
            >
              {/* Icon with badge */}
              <div className="relative">
                <Icon className={`h-6 w-6 ${active ? 'stroke-2' : 'stroke-[1.5]'}`} />
                
                {/* Badge for cart count */}
                {item.badge && item.badge > 0 && (
                  <span className="absolute -top-2 -right-2 flex h-5 w-5 items-center justify-center rounded-full bg-primary text-[10px] font-bold text-white">
                    {item.badge > 9 ? '9+' : item.badge}
                  </span>
                )}
              </div>

              {/* Label */}
              <span className={`text-[10px] font-medium tracking-wide uppercase ${active ? 'opacity-100' : 'opacity-70'}`}>
                {item.label}
              </span>

              {/* Active indicator bar */}
              {active && (
                <div className="absolute top-0 left-1/2 -translate-x-1/2 w-12 h-1 bg-primary rounded-b-full" />
              )}
            </Link>
          );
        })}
      </div>

      {/* Safe area spacing for iOS */}
      <div className="h-[env(safe-area-inset-bottom)] bg-white" />
    </nav>
  );
}
