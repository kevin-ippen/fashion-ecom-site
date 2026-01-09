import { Link } from 'react-router-dom';
import { ShoppingCart, User, Search, Heart } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { useCartStore } from '@/stores/cartStore';
import { usePersonaStore } from '@/stores/personaStore';
import { useState, useEffect } from 'react';
import { PersonaSelector } from '@/components/user/PersonaSelector';
import { CartDrawer } from '@/components/cart/CartDrawer';
import { SmartSearch } from '@/components/search/SmartSearch';

export function Header() {
  const [showPersonaSelector, setShowPersonaSelector] = useState(false);
  const [showCartDrawer, setShowCartDrawer] = useState(false);
  const [showSearch, setShowSearch] = useState(false);
  const [isScrolled, setIsScrolled] = useState(false);

  const itemCount = useCartStore((state) => state.item_count);
  const selectedPersona = usePersonaStore((state) => state.selectedPersona);

  // Track scroll position for compact header
  useEffect(() => {
    const handleScroll = () => {
      setIsScrolled(window.scrollY > 50);
    };

    window.addEventListener('scroll', handleScroll, { passive: true });
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  return (
    <>
      {/* Announcement bar - luxury touch */}
      <div className="bg-stone-900 text-white">
        <div className="container mx-auto px-4 py-2">
          <p className="text-center text-xs font-sans tracking-wider uppercase">
            Free shipping on orders over $100 • New arrivals weekly
          </p>
        </div>
      </div>

      <header className={`sticky top-0 z-50 w-full border-b border-stone-200 bg-white/95 backdrop-blur-md transition-all duration-300 ${isScrolled ? 'shadow-md' : ''}`}>
        {/* Main navigation */}
        <div className="container mx-auto px-4">
          <div className={`flex items-center justify-between transition-all duration-300 ${isScrolled ? 'h-16' : 'h-20'}`}>
            {/* Logo - Refined serif */}
            <Link to="/" className="flex-shrink-0">
              <h1 className="font-serif text-3xl font-semibold tracking-tight text-stone-900">
                FASHION
              </h1>
            </Link>

            {/* Center Navigation - Desktop */}
            <nav className="hidden items-center gap-8 md:flex">
              <Link
                to="/products"
                className="font-sans text-sm font-medium tracking-wide uppercase text-stone-700 transition-colors hover:text-stone-900"
              >
                Shop
              </Link>
              <Link
                to="/products?gender=Women"
                className="font-sans text-sm font-medium tracking-wide uppercase text-stone-700 transition-colors hover:text-stone-900"
              >
                Women
              </Link>
              <Link
                to="/products?gender=Men"
                className="font-sans text-sm font-medium tracking-wide uppercase text-stone-700 transition-colors hover:text-stone-900"
              >
                Men
              </Link>
              <Link
                to="/search"
                className="font-sans text-sm font-medium tracking-wide uppercase text-stone-700 transition-colors hover:text-stone-900"
              >
                Search
              </Link>
            </nav>

            {/* Actions - Right aligned */}
            <div className="flex items-center gap-3">
              {/* Search - Desktop */}
              <Button
                variant="ghost"
                size="sm"
                className="hidden md:flex"
                onClick={() => setShowSearch(true)}
              >
                <Search className="h-5 w-5" />
              </Button>

              {/* Persona selector */}
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setShowPersonaSelector(true)}
                className="gap-2"
              >
                <User className="h-5 w-5" />
                <span className="hidden lg:inline text-xs">
                  {selectedPersona ? selectedPersona.name : 'Account'}
                </span>
              </Button>

              {/* Wishlist placeholder */}
              <Button variant="ghost" size="sm">
                <Heart className="h-5 w-5" />
              </Button>

              {/* Cart */}
              <Button
                variant="ghost"
                size="sm"
                className="relative"
                onClick={() => setShowCartDrawer(true)}
              >
                <ShoppingCart className="h-5 w-5" />
                {itemCount > 0 && (
                  <span className="absolute -right-1 -top-1 flex h-5 w-5 items-center justify-center rounded-full bg-stone-900 text-[10px] font-medium text-white animate-bounce-subtle">
                    {itemCount}
                  </span>
                )}
              </Button>
            </div>
          </div>
        </div>

        {/* Personalization info bar - when persona selected */}
        {selectedPersona && (
          <div className="border-t border-stone-200 bg-amber-50/30">
            <div className="container mx-auto px-4 py-2.5">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-4 text-sm">
                  <span className="font-sans font-medium text-stone-900">
                    Shopping as {selectedPersona.name}
                  </span>
                  <span className="text-stone-600">•</span>
                  <span className="font-sans text-stone-600">{selectedPersona.segment}</span>
                  <Link
                    to={`/profile/${selectedPersona.user_id}`}
                    className="font-sans text-xs text-stone-700 underline-offset-2 hover:underline"
                  >
                    View Profile
                  </Link>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setShowPersonaSelector(true)}
                  className="text-xs text-stone-600 hover:text-stone-900"
                >
                  Change Persona
                </Button>
              </div>
            </div>
          </div>
        )}
      </header>

      {/* Mobile nav - placeholder for future improvement */}
      {/* Would add a mobile menu drawer here */}

      {/* Persona Selector Modal */}
      {showPersonaSelector && (
        <PersonaSelector onClose={() => setShowPersonaSelector(false)} />
      )}

      {/* Cart Drawer */}
      <CartDrawer
        isOpen={showCartDrawer}
        onClose={() => setShowCartDrawer(false)}
      />

      {/* Smart Search Modal */}
      <SmartSearch
        isOpen={showSearch}
        onClose={() => setShowSearch(false)}
      />
    </>
  );
}
