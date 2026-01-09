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
      className="group block"
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
    >
      <div className="relative overflow-hidden bg-white transition-all duration-300 group-hover:shadow-xl">
        {/* Image container - minimal, no rounded corners for luxury feel */}
        <div className="relative aspect-product overflow-hidden bg-stone-100 ring-1 ring-stone-200/50 transition-all duration-300 group-hover:ring-primary/30 group-hover:ring-2">
          <img
            src={product.image_url || ''}
            alt={product.product_display_name}
            className="h-full w-full object-cover transition-all duration-700 ease-out group-hover:scale-110 group-hover:brightness-95"
            loading="lazy"
          />

          {/* Subtle overlay on hover */}
          <div
            className={`absolute inset-0 bg-gradient-to-t from-black/70 via-black/0 to-transparent transition-all duration-500 ease-out ${
              isHovered ? 'opacity-100' : 'opacity-0'
            }`}
          >
            {/* Quick actions - slide up from bottom with stagger */}
            <div className={`absolute bottom-0 left-0 right-0 flex flex-col gap-2 p-4 transition-all duration-500 ease-out ${
              isHovered ? 'translate-y-0 opacity-100' : 'translate-y-8 opacity-0'
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

          {/* Badge Container - Top corners */}
          <div className="absolute inset-x-3 top-3 flex items-start justify-between pointer-events-none">
            {/* Left: Match score badge - only if personalized */}
            {showPersonalization && product.similarity_score && (
              <div className="rounded-sm bg-stone-900/90 px-2.5 py-1 backdrop-blur-sm">
                <div className="flex items-center gap-1.5">
                  <Star className="h-3 w-3 fill-amber-400 text-amber-400" />
                  <span className="text-xs font-medium text-white">
                    {formatPercentage(product.similarity_score)}
                  </span>
                </div>
              </div>
            )}

            {/* Right: NEW/SALE badges */}
            <div className="flex flex-col gap-2">
              {/* NEW badge - show for recent products (year 2016 is latest in dataset) */}
              {product.year >= 2016 && (
                <div className="badge badge-new shadow-md animate-fade-in">
                  NEW
                </div>
              )}

              {/* SALE badge - placeholder for future sale/discount feature */}
              {/* Uncomment when sale price data is available */}
              {/* {product.sale_price && product.sale_price < product.price && (
                <div className="badge badge-sale shadow-md animate-fade-in">
                  SALE
                </div>
              )} */}
            </div>
          </div>
        </div>

        {/* Product info - minimal and refined */}
        <div className="space-y-2 py-4 transition-all duration-300 group-hover:px-1">
          {/* Brand name in small caps */}
          <p className="text-subtle text-stone-500 transition-colors duration-300 group-hover:text-stone-700">
            {product.sub_category}
          </p>

          {/* Product name - single line */}
          <h3 className="line-clamp-1 font-sans text-sm font-medium text-stone-900 tracking-tight transition-colors duration-300 group-hover:text-primary">
            {product.product_display_name}
          </h3>

          {/* Price prominent */}
          <p className="font-sans text-base font-semibold text-stone-900 transition-all duration-300 group-hover:scale-105 origin-left">
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
