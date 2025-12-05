import { Link } from 'react-router-dom';
import { Trash2, Plus, Minus, ShoppingBag, ArrowRight, Tag } from 'lucide-react';
import { useCartStore } from '@/stores/cartStore';
import { Button } from '@/components/ui/Button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { formatPrice } from '@/lib/utils';
import { useState } from 'react';

export function Cart() {
  const { items, total, removeItem, updateQuantity, clearCart } = useCartStore();
  const [showCheckoutSuccess, setShowCheckoutSuccess] = useState(false);

  const handleCheckout = () => {
    setShowCheckoutSuccess(true);
    // In a real app, this would process payment
    setTimeout(() => {
      clearCart();
      setShowCheckoutSuccess(false);
    }, 3000);
  };

  if (showCheckoutSuccess) {
    return (
      <div className="container mx-auto px-4 py-16">
        <Card className="mx-auto max-w-md">
          <CardContent className="p-12 text-center">
            <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-green-100">
              <ShoppingBag className="h-8 w-8 text-green-600" />
            </div>
            <h2 className="mb-2 text-2xl font-bold text-green-900">Order Placed!</h2>
            <p className="text-gray-600">
              This is a demo, so no actual transaction was processed.
            </p>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (items.length === 0) {
    return (
      <div className="container mx-auto px-4 py-16">
        <Card className="mx-auto max-w-md">
          <CardContent className="p-12 text-center">
            <ShoppingBag className="mx-auto h-16 w-16 text-gray-400" />
            <h2 className="mt-4 text-2xl font-bold">Your cart is empty</h2>
            <p className="mt-2 text-gray-600">Add some products to get started</p>
            <Link to="/products" className="mt-6 inline-block">
              <Button size="lg">
                Browse Products
                <ArrowRight className="ml-2 h-5 w-5" />
              </Button>
            </Link>
          </CardContent>
        </Card>
      </div>
    );
  }

  const shipping = total > 50 ? 0 : 9.99;
  const tax = total * 0.08; // 8% tax
  const finalTotal = total + shipping + tax;

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="container mx-auto px-4 py-8">
        <h1 className="mb-8 text-3xl font-bold">Shopping Cart</h1>

        <div className="grid gap-8 lg:grid-cols-3">
          {/* Cart items */}
          <div className="lg:col-span-2">
            <Card>
              <CardHeader>
                <CardTitle>Cart Items ({items.length})</CardTitle>
              </CardHeader>
              <CardContent className="p-0">
                <div className="divide-y">
                  {items.map((item) => {
                    const product = item.product;
                    if (!product) return null;

                    return (
                      <div key={item.product_id} className="p-6">
                        <div className="flex gap-4">
                          {/* Product image */}
                          <Link
                            to={`/products/${product.product_id}`}
                            className="flex-shrink-0"
                          >
                            <img
                              src={product.image_url || ''}
                              alt={product.product_display_name}
                              className="h-24 w-24 rounded-lg object-cover"
                            />
                          </Link>

                          {/* Product details */}
                          <div className="flex flex-1 flex-col justify-between">
                            <div>
                              <Link
                                to={`/products/${product.product_id}`}
                                className="font-medium text-gray-900 hover:text-blue-600"
                              >
                                {product.product_display_name}
                              </Link>
                              <p className="mt-1 text-sm text-gray-500">
                                {product.base_color} • {product.article_type}
                              </p>
                            </div>

                            <div className="flex items-center justify-between">
                              {/* Quantity controls */}
                              <div className="flex items-center gap-2">
                                <Button
                                  variant="outline"
                                  size="sm"
                                  onClick={() =>
                                    updateQuantity(
                                      item.product_id,
                                      Math.max(1, item.quantity - 1)
                                    )
                                  }
                                >
                                  <Minus className="h-3 w-3" />
                                </Button>
                                <span className="w-8 text-center font-medium">
                                  {item.quantity}
                                </span>
                                <Button
                                  variant="outline"
                                  size="sm"
                                  onClick={() =>
                                    updateQuantity(item.product_id, item.quantity + 1)
                                  }
                                >
                                  <Plus className="h-3 w-3" />
                                </Button>
                              </div>

                              {/* Price and remove */}
                              <div className="flex items-center gap-4">
                                <p className="text-lg font-semibold">
                                  {formatPrice(product.price * item.quantity)}
                                </p>
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  onClick={() => removeItem(item.product_id)}
                                  className="text-red-600 hover:text-red-700"
                                >
                                  <Trash2 className="h-4 w-4" />
                                </Button>
                              </div>
                            </div>
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </CardContent>
            </Card>

            {/* Continue shopping */}
            <div className="mt-6">
              <Link to="/products">
                <Button variant="outline">
                  <ArrowRight className="mr-2 h-4 w-4 rotate-180" />
                  Continue Shopping
                </Button>
              </Link>
            </div>
          </div>

          {/* Order summary */}
          <div>
            <Card className="sticky top-20">
              <CardHeader>
                <CardTitle>Order Summary</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                {/* Subtotal */}
                <div className="flex justify-between text-sm">
                  <span className="text-gray-600">Subtotal</span>
                  <span className="font-medium">{formatPrice(total)}</span>
                </div>

                {/* Shipping */}
                <div className="flex justify-between text-sm">
                  <span className="text-gray-600">Shipping</span>
                  <span className="font-medium">
                    {shipping === 0 ? (
                      <span className="text-green-600">FREE</span>
                    ) : (
                      formatPrice(shipping)
                    )}
                  </span>
                </div>

                {/* Free shipping banner */}
                {total < 50 && (
                  <div className="rounded-lg bg-blue-50 p-3 text-sm text-blue-900">
                    <Tag className="mb-1 inline h-4 w-4" />
                    <span className="ml-1">
                      Add {formatPrice(50 - total)} more for FREE shipping!
                    </span>
                  </div>
                )}

                {/* Tax */}
                <div className="flex justify-between text-sm">
                  <span className="text-gray-600">Estimated Tax</span>
                  <span className="font-medium">{formatPrice(tax)}</span>
                </div>

                <div className="border-t pt-4">
                  <div className="flex justify-between">
                    <span className="text-lg font-semibold">Total</span>
                    <span className="text-2xl font-bold">{formatPrice(finalTotal)}</span>
                  </div>
                </div>

                {/* Checkout button */}
                <Button
                  className="w-full"
                  size="lg"
                  onClick={handleCheckout}
                >
                  Proceed to Checkout
                </Button>

                {/* Demo notice */}
                <div className="rounded-lg bg-gray-50 p-3 text-center text-xs text-gray-600">
                  This is a demo. No payment will be processed.
                </div>

                {/* Features */}
                <div className="space-y-2 border-t pt-4 text-sm text-gray-600">
                  <div className="flex items-center gap-2">
                    <div className="h-1.5 w-1.5 rounded-full bg-green-600" />
                    <span>Free returns within 30 days</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <div className="h-1.5 w-1.5 rounded-full bg-green-600" />
                    <span>Secure checkout</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <div className="h-1.5 w-1.5 rounded-full bg-green-600" />
                    <span>24/7 customer support</span>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </div>
  );
}
