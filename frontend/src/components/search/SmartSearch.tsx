import { X, Search, TrendingUp, Clock } from 'lucide-react';
import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { searchApi } from '@/api/client';
import type { Product } from '@/types';

interface SmartSearchProps {
  isOpen: boolean;
  onClose: () => void;
}

const TRENDING_QUERIES = [
  'summer dresses',
  'casual friday',
  'vintage style',
  'minimalist wardrobe',
  'streetwear',
];

export function SmartSearch({ isOpen, onClose }: SmartSearchProps) {
  const [query, setQuery] = useState('');
  const [recentSearches, setRecentSearches] = useState<string[]>([]);
  const inputRef = useRef<HTMLInputElement>(null);
  const navigate = useNavigate();

  // Load recent searches from localStorage
  useEffect(() => {
    const stored = localStorage.getItem('recentSearches');
    if (stored) {
      setRecentSearches(JSON.parse(stored));
    }
  }, [isOpen]);

  // Focus input when modal opens
  useEffect(() => {
    if (isOpen && inputRef.current) {
      inputRef.current.focus();
    }
  }, [isOpen]);

  // Search for products as user types
  const { data: searchResults } = useQuery({
    queryKey: ['search', query],
    queryFn: () => searchApi.searchByText({ query, limit: 5 }),
    enabled: query.length >= 2,
  });

  // Handle search submission
  const handleSearch = (searchQuery: string) => {
    if (!searchQuery.trim()) return;

    // Save to recent searches
    const updated = [
      searchQuery,
      ...recentSearches.filter((s) => s !== searchQuery),
    ].slice(0, 5);
    setRecentSearches(updated);
    localStorage.setItem('recentSearches', JSON.stringify(updated));

    // Navigate to search page
    navigate(`/search?q=${encodeURIComponent(searchQuery)}`);
    onClose();
  };

  // Handle key press
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Escape') {
      onClose();
    } else if (e.key === 'Enter' && query.trim()) {
      handleSearch(query);
    }
  };

  if (!isOpen) return null;

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/50 z-50 animate-fade-in"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Modal */}
      <div
        className="fixed top-0 left-1/2 -translate-x-1/2 w-full max-w-2xl bg-white shadow-2xl z-50 animate-slide-down rounded-b-lg overflow-hidden"
        role="dialog"
        aria-modal="true"
        aria-labelledby="search-modal-title"
      >
        {/* Search Input */}
        <div className="flex items-center gap-3 px-6 py-4 border-b border-border">
          <Search className="h-5 w-5 text-muted-foreground flex-shrink-0" />
          <input
            ref={inputRef}
            type="text"
            placeholder="Search for products, styles, or trends..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            className="flex-1 text-body focus:outline-none placeholder:text-muted-foreground bg-transparent"
            aria-label="Search products"
          />
          <button
            onClick={onClose}
            className="btn-ghost p-2 rounded-full hover:bg-accent transition-colors flex-shrink-0"
            aria-label="Close search"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Search Results / Suggestions */}
        <div className="max-h-[60vh] overflow-y-auto">
          {query.length >= 2 && searchResults ? (
            /* Autocomplete Results */
            <div className="px-6 py-4">
              <h3 className="text-micro text-muted-foreground font-semibold mb-3">
                Results
              </h3>
              {searchResults.products && searchResults.products.length > 0 ? (
                <div className="space-y-2">
                  {searchResults.products.slice(0, 5).map((product: Product) => (
                    <button
                      key={product.product_id}
                      onClick={() => {
                        navigate(`/products/${product.product_id}`);
                        onClose();
                      }}
                      className="flex items-center gap-3 w-full px-3 py-2 hover:bg-accent rounded-md transition-colors text-left"
                    >
                      <div className="w-12 h-16 bg-muted rounded overflow-hidden flex-shrink-0">
                        <img
                          src={product.image_url}
                          alt={product.product_display_name}
                          className="w-full h-full object-cover"
                        />
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-body-sm font-medium truncate">
                          {product.product_display_name}
                        </p>
                        <p className="text-body-sm text-muted-foreground">
                          ${product.price}
                        </p>
                      </div>
                    </button>
                  ))}
                </div>
              ) : (
                <p className="text-body-sm text-muted-foreground">
                  No results found for "{query}"
                </p>
              )}
            </div>
          ) : (
            /* Default Suggestions */
            <div className="px-6 py-4 space-y-6">
              {/* Recent Searches */}
              {recentSearches.length > 0 && (
                <div>
                  <h3 className="text-micro text-muted-foreground font-semibold mb-3 flex items-center gap-2">
                    <Clock className="h-4 w-4" />
                    Recent Searches
                  </h3>
                  <div className="space-y-1">
                    {recentSearches.map((search, index) => (
                      <button
                        key={index}
                        onClick={() => handleSearch(search)}
                        className="block w-full text-left px-3 py-2 text-body-sm hover:bg-accent rounded-md transition-colors"
                      >
                        {search}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {/* Trending Queries */}
              <div>
                <h3 className="text-micro text-muted-foreground font-semibold mb-3 flex items-center gap-2">
                  <TrendingUp className="h-4 w-4" />
                  Trending Searches
                </h3>
                <div className="flex flex-wrap gap-2">
                  {TRENDING_QUERIES.map((trend) => (
                    <button
                      key={trend}
                      onClick={() => handleSearch(trend)}
                      className="badge badge-secondary hover:bg-secondary/80 transition-colors cursor-pointer"
                    >
                      {trend}
                    </button>
                  ))}
                </div>
              </div>

              {/* Quick Tip */}
              <div className="text-body-sm text-muted-foreground bg-accent/30 px-4 py-3 rounded-md">
                <p className="font-medium mb-1">Try searching for:</p>
                <p>"red cocktail dress" • "casual friday outfit" • "vintage 70s style"</p>
              </div>
            </div>
          )}
        </div>
      </div>
    </>
  );
}
