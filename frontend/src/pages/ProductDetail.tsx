import { useParams, Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { ShoppingCart, Heart, Package, Truck, Shield } from 'lucide-react';
import { productsApi } from '@/api/client';
import { useCartStore } from '@/stores/cartStore';
import { Button } from '@/components/ui/Button';
import { ProductGrid } from '@/components/product/ProductGrid';
import { Breadcrumb } from '@/components/ui/Breadcrumb';
import { SizeSelector } from '@/components/product/SizeSelector';
import { Accordion } from '@/components/ui/Accordion';
import { formatPrice } from '@/lib/utils';
import { useState } from 'react';

export function ProductDetail() {
  const { productId } = useParams<{ productId: string }>();
  const [quantity, setQuantity] = useState(1);
  const [selectedSize, setSelectedSize] = useState<string>();
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

  // Build breadcrumb items
  const breadcrumbItems = [
    { label: product.gender, href: `/products?gender=${product.gender}` },
    { label: product.master_category, href: `/products?master_category=${product.master_category}` },
    { label: product.sub_category, href: `/products?sub_category=${product.sub_category}` },
    { label: product.product_display_name }, // Current product, no href
  ];

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="container mx-auto px-4 py-8">
        {/* Breadcrumb navigation */}
        <Breadcrumb items={breadcrumbItems} className="mb-6" />

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

            {/* Color */}
            <div>
              <p className="text-body-sm text-muted-foreground mb-1">Color</p>
              <p className="text-body font-medium">{product.base_color}</p>
            </div>

            {/* Size Selector */}
            <SizeSelector
              sizes={['XS', 'S', 'M', 'L', 'XL']}
              selectedSize={selectedSize}
              onSizeSelect={setSelectedSize}
              unavailableSizes={['XS']} // Demo: XS is out of stock
            />

            {/* Quantity selector */}
            <div className="space-y-2">
              <label className="block text-body font-medium text-foreground">Quantity</label>
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

            {/* Trust Badges */}
            <div className="space-y-2 rounded-lg bg-accent/30 p-4">
              <div className="flex items-center gap-3 text-body-sm text-foreground">
                <Truck className="h-5 w-5 text-primary" />
                <span>Free shipping on orders over $50</span>
              </div>
              <div className="flex items-center gap-3 text-body-sm text-foreground">
                <Package className="h-5 w-5 text-primary" />
                <span>Free 30-day returns</span>
              </div>
              <div className="flex items-center gap-3 text-body-sm text-foreground">
                <Shield className="h-5 w-5 text-primary" />
                <span>Secure checkout</span>
              </div>
            </div>

            {/* Expandable Product Details */}
            <Accordion
              items={[
                {
                  title: 'Product Details',
                  defaultOpen: true,
                  content: (
                    <div className="grid grid-cols-2 gap-x-4 gap-y-3">
                      <div>
                        <p className="font-medium text-foreground">Category</p>
                        <p>{product.master_category}</p>
                      </div>
                      <div>
                        <p className="font-medium text-foreground">Type</p>
                        <p>{product.article_type}</p>
                      </div>
                      <div>
                        <p className="font-medium text-foreground">Gender</p>
                        <p>{product.gender}</p>
                      </div>
                      <div>
                        <p className="font-medium text-foreground">Season</p>
                        <p>{product.season}</p>
                      </div>
                      <div>
                        <p className="font-medium text-foreground">Usage</p>
                        <p>{product.usage}</p>
                      </div>
                      <div>
                        <p className="font-medium text-foreground">Year</p>
                        <p>{product.year}</p>
                      </div>
                    </div>
                  ),
                },
                {
                  title: 'Shipping & Returns',
                  content: (
                    <div className="space-y-3">
                      <p>Free standard shipping on orders over $50.</p>
                      <p>Orders ship within 1-2 business days.</p>
                      <p>
                        Returns accepted within 30 days of purchase. Items must be unworn
                        with tags attached.
                      </p>
                    </div>
                  ),
                },
                {
                  title: 'Size & Fit',
                  content: (
                    <div className="space-y-3">
                      <p>Model is 5'9" and wearing size S.</p>
                      <p>Fits true to size. Take your normal size.</p>
                      <p>Designed for a relaxed fit.</p>
                    </div>
                  ),
                },
              ]}
            />
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
