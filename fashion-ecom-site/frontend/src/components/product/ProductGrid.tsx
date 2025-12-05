import { Product } from '@/types';
import { ProductCard } from './ProductCard';

interface ProductGridProps {
  products: Product[];
  showPersonalization?: boolean;
  isLoading?: boolean;
}

export function ProductGrid({
  products,
  showPersonalization = false,
  isLoading = false,
}: ProductGridProps) {
  if (isLoading) {
    return (
      <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
        {Array.from({ length: 8 }).map((_, i) => (
          <div key={i} className="animate-pulse">
            <div className="aspect-[3/4] rounded-lg bg-gray-200" />
            <div className="mt-4 space-y-2">
              <div className="h-4 rounded bg-gray-200" />
              <div className="h-4 w-3/4 rounded bg-gray-200" />
            </div>
          </div>
        ))}
      </div>
    );
  }

  if (products.length === 0) {
    return (
      <div className="flex min-h-[400px] items-center justify-center">
        <div className="text-center">
          <p className="text-lg text-gray-500">No products found</p>
          <p className="mt-2 text-sm text-gray-400">Try adjusting your filters</p>
        </div>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
      {products.map((product) => (
        <ProductCard
          key={product.product_id}
          product={product}
          showPersonalization={showPersonalization}
        />
      ))}
    </div>
  );
}
