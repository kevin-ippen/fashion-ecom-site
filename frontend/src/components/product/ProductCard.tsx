import { Link } from 'react-router-dom';
import { Heart, Star, Check, Eye } from 'lucide-react';
import toast from 'react-hot-toast';
import type { Product } from '@/types';
import { formatPrice, formatPercentage } from '@/lib/utils';
import { Button } from '@/components/ui/Button';
import { QuickViewModal } from './QuickViewModal';
import { useCartStore } from '@/stores/cartStore';
import { useState } from 'react';

interface ProductCardProps {
  product: Product;
  showPersonalization?: boolean;
}

export function ProductCard({ product, showPersonalization = false }: ProductCardProps) {
  const [isHovered, setIsHovered] = useState(false);
  const [showQuickView, setShowQuickView] = useState(false);
  const addItem = useCartStore((state) => state.addItem);

  const handleAddToCart = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    addItem(product);

    // Toast notification
    toast.success(
      <div className="flex items-center gap-3">
        <Check className="h-5 w-5" />
        <div>
          <p className="font-medium">Added to bag</p>
          <p className="text-xs opacity-80">{product.product_display_name}</p>
        </div>
      </div>,
      {
        duration: 2000,
      }
    );
  };

  return (
    <Link
      to={`/products/${product.product_id}`}
      className="group block hover-lift"
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
    >
      <div className="relative overflow-hidden bg-white">
        {/* Image container - minimal, no rounded corners for luxury feel */}
        <div className="relative aspect-product overflow-hidden bg-stone-100">
          <img
            src={product.image_url || ''}
            alt={product.product_display_name}
            className="h-full w-full object-cover transition-transform duration-500 ease-out group-hover:scale-105"
            loading="lazy"
          />

          {/* Subtle overlay on hover */}
          <div
            className={`absolute inset-0 bg-gradient-to-t from-black/60 via-black/0 to-transparent transition-opacity duration-500 ${
              isHovered ? 'opacity-100' : 'opacity-0'
            }`}
          >
            {/* Quick actions - slide up from bottom */}
            <div className={`absolute bottom-0 left-0 right-0 flex flex-col gap-2 p-4 transition-all duration-500 ${
              isHovered ? 'translate-y-0 opacity-100' : 'translate-y-4 opacity-0'
            }`}>
              <div className="flex gap-2">
                <Button
                  size="sm"
                  onClick={handleAddToCart}
                  className="flex-1 bg-white text-stone-900 hover:bg-stone-100 font-medium tracking-wide text-xs uppercase"
                >
                  Add to Bag
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  className="bg-white/90 hover:bg-white border-transparent"
                  onClick={(e) => {
                    e.preventDefault();
                    e.stopPropagation();
                  }}
                >
                  <Heart className="h-4 w-4" />
                </Button>
              </div>
              <Button
                size="sm"
                variant="outline"
                className="w-full bg-white/90 hover:bg-white border-transparent"
                onClick={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  setShowQuickView(true);
                }}
              >
                <Eye className="mr-2 h-4 w-4" />
                Quick View
              </Button>
            </div>
          </div>

          {/* Match score badge - only if personalized */}
          {showPersonalization && product.similarity_score && (
            <div className="absolute left-3 top-3 rounded-sm bg-stone-900/90 px-2.5 py-1 backdrop-blur-sm">
              <div className="flex items-center gap-1.5">
                <Star className="h-3 w-3 fill-amber-400 text-amber-400" />
                <span className="text-xs font-medium text-white">
                  {formatPercentage(product.similarity_score)}
                </span>
              </div>
            </div>
          )}
        </div>

        {/* Product info - minimal and refined */}
        <div className="space-y-2 py-4">
          {/* Brand name in small caps */}
          <p className="text-subtle text-stone-500">
            {product.sub_category}
          </p>

          {/* Product name - single line */}
          <h3 className="line-clamp-1 font-sans text-sm font-medium text-stone-900 tracking-tight">
            {product.product_display_name}
          </h3>

          {/* Price prominent */}
          <p className="font-sans text-base font-semibold text-stone-900">
            {formatPrice(product.price)}
          </p>

          {/* Color swatch - subtle */}
          {product.base_color && (
            <p className="text-xs text-stone-500 font-sans">
              {product.base_color}
            </p>
          )}

          {/* Personalization reason - refined */}
          {showPersonalization && product.personalization_reason && (
            <div className="mt-3 border-l-2 border-amber-500 bg-amber-50/50 px-3 py-2">
              <p className="text-xs leading-relaxed text-stone-700 font-sans">
                {product.personalization_reason}
              </p>
            </div>
          )}
        </div>
      </div>

      {/* Quick View Modal */}
      <QuickViewModal
        product={product}
        isOpen={showQuickView}
        onClose={() => setShowQuickView(false)}
      />
    </Link>
  );
}
