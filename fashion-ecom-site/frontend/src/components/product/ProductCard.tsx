import { Link } from 'react-router-dom';
import { ShoppingCart, Heart, Star } from 'lucide-react';
import type { Product } from '@/types';
import { formatPrice, formatPercentage } from '@/lib/utils';
import { Button } from '@/components/ui/Button';
import { useCartStore } from '@/stores/cartStore';
import { useState } from 'react';

interface ProductCardProps {
  product: Product;
  showPersonalization?: boolean;
}

export function ProductCard({ product, showPersonalization = false }: ProductCardProps) {
  const [isHovered, setIsHovered] = useState(false);
  const addItem = useCartStore((state) => state.addItem);

  const handleAddToCart = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    addItem(product);
  };

  return (
    <Link
      to={`/products/${product.product_id}`}
      className="group block"
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
    >
      <div className="relative overflow-hidden rounded-lg bg-white shadow-sm transition-all duration-300 hover:shadow-xl">
        {/* Image container */}
        <div className="relative aspect-[3/4] overflow-hidden bg-gray-100">
          <img
            src={product.image_url || ''}
            alt={product.product_display_name}
            className="h-full w-full object-cover transition-transform duration-300 group-hover:scale-105"
            loading="lazy"
          />

          {/* Overlay actions */}
          <div
            className={`absolute inset-0 bg-black/40 transition-opacity duration-300 ${
              isHovered ? 'opacity-100' : 'opacity-0'
            }`}
          >
            <div className="flex h-full items-end justify-center gap-2 p-4">
              <Button
                size="sm"
                onClick={handleAddToCart}
                className="flex-1 bg-white text-black hover:bg-gray-100"
              >
                <ShoppingCart className="mr-2 h-4 w-4" />
                Add to Cart
              </Button>
              <Button
                size="sm"
                variant="outline"
                className="bg-white/90 hover:bg-white"
                onClick={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                }}
              >
                <Heart className="h-4 w-4" />
              </Button>
            </div>
          </div>

          {/* Similarity score badge */}
          {showPersonalization && product.similarity_score && (
            <div className="absolute left-2 top-2 rounded-full bg-black/70 px-2 py-1 text-xs font-medium text-white backdrop-blur-sm">
              <Star className="mr-1 inline h-3 w-3 fill-yellow-400 text-yellow-400" />
              {formatPercentage(product.similarity_score)} Match
            </div>
          )}
        </div>

        {/* Product info */}
        <div className="p-4">
          <h3 className="line-clamp-2 text-sm font-medium text-gray-900">
            {product.product_display_name}
          </h3>

          <div className="mt-2 flex items-baseline justify-between">
            <p className="text-lg font-semibold text-gray-900">{formatPrice(product.price)}</p>
            <p className="text-xs text-gray-500">{product.base_color}</p>
          </div>

          {/* Category badges */}
          <div className="mt-2 flex flex-wrap gap-1">
            <span className="rounded bg-gray-100 px-2 py-0.5 text-xs text-gray-600">
              {product.sub_category}
            </span>
            <span className="rounded bg-gray-100 px-2 py-0.5 text-xs text-gray-600">
              {product.season}
            </span>
          </div>

          {/* Personalization reason */}
          {showPersonalization && product.personalization_reason && (
            <div className="mt-3 rounded-md bg-blue-50 p-2 text-xs text-blue-700">
              {product.personalization_reason}
            </div>
          )}
        </div>
      </div>
    </Link>
  );
}
