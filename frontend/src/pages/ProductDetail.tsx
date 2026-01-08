import { useParams, Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { ArrowLeft, ShoppingCart, Heart, Package, Truck, Shield } from 'lucide-react';
import { productsApi } from '@/api/client';
import { useCartStore } from '@/stores/cartStore';
import { Button } from '@/components/ui/Button';
import { ProductGrid } from '@/components/product/ProductGrid';
import { formatPrice } from '@/lib/utils';
import { useState } from 'react';

export function ProductDetail() {
  const { productId } = useParams<{ productId: string }>();
  const [quantity, setQuantity] = useState(1);
  const addItem = useCartStore((state) => state.addItem);

  // Fetch product details
  const { data: product, isLoading } = useQuery({
    queryKey: ['product', productId],
    queryFn: () => productsApi.getById(productId!),
    enabled: !!productId,
  });

  // Fetch similar products (visual similarity)
  const { data: similarProductsResponse } = useQuery({
    queryKey: ['similar-products', productId],
    queryFn: async () => {
      return await productsApi.getSimilar(productId!, 4);
    },
    enabled: !!productId,
  });

  // Fetch complete-the-look products (outfit pairings)
  const { data: completeTheLookResponse } = useQuery({
    queryKey: ['complete-the-look', productId],
    queryFn: async () => {
      return await productsApi.getCompleteTheLook(productId!, 4);
    },
    enabled: !!productId,
  });

  const similarProducts = similarProductsResponse?.products || [];
  const completeTheLookProducts = completeTheLookResponse?.products || [];

  const handleAddToCart = () => {
    if (product) {
      addItem(product, quantity);
    }
  };

  if (isLoading) {
    return (
      <div className="container mx-auto px-4 py-8">
        <div className="animate-pulse">
          <div className="grid gap-8 lg:grid-cols-2">
            <div className="aspect-[3/4] rounded-lg bg-gray-200" />
            <div className="space-y-4">
              <div className="h-8 w-3/4 rounded bg-gray-200" />
              <div className="h-6 w-1/4 rounded bg-gray-200" />
              <div className="h-20 rounded bg-gray-200" />
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (!product) {
    return (
      <div className="container mx-auto px-4 py-16 text-center">
        <h2 className="text-2xl font-bold">Product not found</h2>
        <Link to="/products" className="mt-4 inline-block text-blue-600 hover:underline">
          Back to products
        </Link>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="container mx-auto px-4 py-8">
        {/* Back button */}
        <Link
          to="/products"
          className="mb-6 inline-flex items-center text-sm text-gray-600 hover:text-gray-900"
        >
          <ArrowLeft className="mr-2 h-4 w-4" />
          Back to products
        </Link>

        {/* Product details */}
        <div className="grid gap-8 lg:grid-cols-2">
          {/* Image section */}
          <div className="space-y-4">
            <div className="overflow-hidden rounded-lg bg-white shadow-lg">
              <img
                src={product.image_url || ''}
                alt={product.product_display_name}
                className="aspect-[3/4] w-full object-cover"
              />
            </div>
          </div>

          {/* Info section */}
          <div className="space-y-6">
            <div>
              <h1 className="text-3xl font-bold text-gray-900">
                {product.product_display_name}
              </h1>
              <p className="mt-2 text-sm text-gray-500">
                Product ID: {product.product_id}
              </p>
            </div>

            {/* Price */}
            <div className="flex items-baseline gap-4">
              <p className="text-4xl font-bold text-gray-900">{formatPrice(product.price)}</p>
            </div>

            {/* Product details */}
            <div className="space-y-3">
              <h3 className="font-semibold text-gray-900">Product Details</h3>
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <p className="text-gray-500">Category</p>
                  <p className="font-medium">{product.master_category}</p>
                </div>
                <div>
                  <p className="text-gray-500">Type</p>
                  <p className="font-medium">{product.article_type}</p>
                </div>
                <div>
                  <p className="text-gray-500">Color</p>
                  <p className="font-medium">{product.base_color}</p>
                </div>
                <div>
                  <p className="text-gray-500">Season</p>
                  <p className="font-medium">{product.season}</p>
                </div>
                <div>
                  <p className="text-gray-500">Gender</p>
                  <p className="font-medium">{product.gender}</p>
                </div>
                <div>
                  <p className="text-gray-500">Usage</p>
                  <p className="font-medium">{product.usage}</p>
                </div>
              </div>
            </div>

            {/* Quantity selector */}
            <div>
              <label className="mb-2 block text-sm font-medium text-gray-700">Quantity</label>
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setQuantity(Math.max(1, quantity - 1))}
                >
                  -
                </Button>
                <span className="w-12 text-center font-medium">{quantity}</span>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setQuantity(quantity + 1)}
                >
                  +
                </Button>
              </div>
            </div>

            {/* Actions */}
            <div className="flex gap-4">
              <Button size="lg" className="flex-1" onClick={handleAddToCart}>
                <ShoppingCart className="mr-2 h-5 w-5" />
                Add to Cart
              </Button>
              <Button variant="outline" size="lg">
                <Heart className="h-5 w-5" />
              </Button>
            </div>

            {/* Features */}
            <div className="space-y-3 border-t pt-6">
              <div className="flex items-center gap-3 text-sm text-gray-600">
                <Truck className="h-5 w-5" />
                <span>Free shipping on orders over $50</span>
              </div>
              <div className="flex items-center gap-3 text-sm text-gray-600">
                <Package className="h-5 w-5" />
                <span>Easy returns within 30 days</span>
              </div>
              <div className="flex items-center gap-3 text-sm text-gray-600">
                <Shield className="h-5 w-5" />
                <span>1 year warranty</span>
              </div>
            </div>
          </div>
        </div>

        {/* Similar products - Visual similarity */}
        {similarProducts && similarProducts.length > 0 && (
          <div className="mt-16">
            <h2 className="mb-6 text-2xl font-bold">You Might Also Like</h2>
            <p className="mb-4 text-sm text-gray-600">
              Visually similar products based on style and appearance
            </p>
            <ProductGrid
              products={similarProducts}
              showPersonalization={false}
            />
          </div>
        )}

        {/* Complete the Look - Outfit pairings */}
        {completeTheLookProducts && completeTheLookProducts.length > 0 && (
          <div className="mt-16">
            <h2 className="mb-6 text-2xl font-bold">Complete the Look</h2>
            <p className="mb-4 text-sm text-gray-600">
              Products from styled outfits that pair well together
            </p>
            <ProductGrid
              products={completeTheLookProducts}
              showPersonalization={false}
            />
          </div>
        )}
      </div>
    </div>
  );
}
