import { Link } from 'react-router-dom';
import { ShoppingCart, User, Search } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { useCartStore } from '@/stores/cartStore';
import { usePersonaStore } from '@/stores/personaStore';
import { useState } from 'react';
import { PersonaSelector } from '@/components/user/PersonaSelector';

export function Header() {
  const [showPersonaSelector, setShowPersonaSelector] = useState(false);
  const itemCount = useCartStore((state) => state.item_count);
  const selectedPersona = usePersonaStore((state) => state.selectedPersona);

  return (
    <>
      <header className="sticky top-0 z-50 w-full border-b bg-white/95 backdrop-blur supports-[backdrop-filter]:bg-white/60">
        <div className="container mx-auto flex h-16 items-center justify-between px-4">
          {/* Logo */}
          <Link to="/" className="text-2xl font-bold">
            Fashion<span className="text-blue-600">.</span>
          </Link>

          {/* Navigation */}
          <nav className="hidden items-center gap-6 md:flex">
            <Link
              to="/products"
              className="text-sm font-medium transition-colors hover:text-primary"
            >
              Shop
            </Link>
            <Link
              to="/search"
              className="text-sm font-medium transition-colors hover:text-primary"
            >
              Search
            </Link>
          </nav>

          {/* Actions */}
          <div className="flex items-center gap-4">
            {/* Search icon (mobile) */}
            <Link to="/search" className="md:hidden">
              <Button variant="ghost" size="sm">
                <Search className="h-5 w-5" />
              </Button>
            </Link>

            {/* Persona selector */}
            <Button
              variant="outline"
              size="sm"
              onClick={() => setShowPersonaSelector(true)}
              className="gap-2"
            >
              <User className="h-4 w-4" />
              <span className="hidden sm:inline">
                {selectedPersona ? selectedPersona.name : 'Select Persona'}
              </span>
            </Button>

            {/* Cart */}
            <Link to="/cart">
              <Button variant="ghost" size="sm" className="relative">
                <ShoppingCart className="h-5 w-5" />
                {itemCount > 0 && (
                  <span className="absolute -right-1 -top-1 flex h-5 w-5 items-center justify-center rounded-full bg-blue-600 text-xs text-white">
                    {itemCount}
                  </span>
                )}
              </Button>
            </Link>
          </div>
        </div>

        {/* Persona info bar */}
        {selectedPersona && (
          <div className="border-t bg-blue-50 px-4 py-2">
            <div className="container mx-auto">
              <div className="flex items-center justify-between text-sm">
                <div className="flex items-center gap-4">
                  <span className="font-medium text-blue-900">
                    Shopping as: {selectedPersona.name}
                  </span>
                  <span className="text-blue-700">• {selectedPersona.segment}</span>
                  <Link
                    to={`/profile/${selectedPersona.user_id}`}
                    className="text-blue-600 hover:underline"
                  >
                    View Profile
                  </Link>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setShowPersonaSelector(true)}
                  className="text-blue-600 hover:text-blue-800"
                >
                  Change
                </Button>
              </div>
            </div>
          </div>
        )}
      </header>

      {/* Persona Selector Modal */}
      {showPersonaSelector && (
        <PersonaSelector onClose={() => setShowPersonaSelector(false)} />
      )}
    </>
  );
}
