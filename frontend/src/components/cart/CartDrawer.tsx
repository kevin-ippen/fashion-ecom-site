import { X, ShoppingBag, Minus, Plus, Trash2 } from 'lucide-react';
import { Link } from 'react-router-dom';
import { useCartStore } from '@/stores/cartStore';

interface CartDrawerProps {
  isOpen: boolean;
  onClose: () => void;
}

export function CartDrawer({ isOpen, onClose }: CartDrawerProps) {
  const { items, item_count, total_price, removeItem, updateQuantity } = useCartStore();

  // Close on escape key
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Escape') onClose();
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

      {/* Drawer */}
      <div
        className="fixed right-0 top-0 h-full w-full max-w-md bg-white shadow-2xl z-50 flex flex-col animate-slide-in-right"
        onKeyDown={handleKeyDown}
        role="dialog"
        aria-modal="true"
        aria-labelledby="cart-drawer-title"
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b border-border px-6 py-4">
          <h2 id="cart-drawer-title" className="text-title-lg font-semibold">
            Shopping Cart ({item_count})
          </h2>
          <button
            onClick={onClose}
            className="btn-ghost p-2 rounded-full hover:bg-accent transition-colors"
            aria-label="Close cart"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Cart Items */}
        {items.length === 0 ? (
          <div className="flex-1 flex flex-col items-center justify-center px-6 py-12 text-center">
            <ShoppingBag className="h-16 w-16 text-muted-foreground mb-4" />
            <h3 className="text-title font-semibold mb-2">Your cart is empty</h3>
            <p className="text-body-sm text-muted-foreground mb-6">
              Start adding items to your cart
            </p>
            <button
              onClick={onClose}
              className="btn btn-primary btn-md"
            >
              Continue Shopping
            </button>
          </div>
        ) : (
          <>
            {/* Scrollable Items List */}
            <div className="flex-1 overflow-y-auto px-6 py-4">
              <div className="space-y-4">
                {items.map((item) => (
                  <div
                    key={item.product_id}
                    className="flex gap-4 pb-4 border-b border-border/50 last:border-0"
                  >
                    {/* Product Image */}
                    <div className="w-24 h-32 flex-shrink-0 bg-muted rounded-md overflow-hidden">
                      <img
                        src={item.image_url}
                        alt={item.product_name}
                        className="w-full h-full object-cover"
                      />
                    </div>

                    {/* Product Details */}
                    <div className="flex-1 min-w-0">
                      <h4 className="text-body font-medium truncate-2 mb-1">
                        {item.product_name}
                      </h4>
                      <p className="text-body-sm text-muted-foreground mb-3">
                        ${item.price.toFixed(2)}
                      </p>

                      {/* Quantity Controls */}
                      <div className="flex items-center gap-3">
                        <div className="flex items-center border border-border rounded-md">
                          <button
                            onClick={() => updateQuantity(item.product_id, Math.max(1, item.quantity - 1))}
                            className="p-1.5 hover:bg-accent transition-colors"
                            aria-label="Decrease quantity"
                          >
                            <Minus className="h-3 w-3" />
                          </button>
                          <span className="px-3 text-sm font-medium">
                            {item.quantity}
                          </span>
                          <button
                            onClick={() => updateQuantity(item.product_id, item.quantity + 1)}
                            className="p-1.5 hover:bg-accent transition-colors"
                            aria-label="Increase quantity"
                          >
                            <Plus className="h-3 w-3" />
                          </button>
                        </div>

                        <button
                          onClick={() => removeItem(item.product_id)}
                          className="p-1.5 text-muted-foreground hover:text-error transition-colors"
                          aria-label="Remove item"
                        >
                          <Trash2 className="h-4 w-4" />
                        </button>
                      </div>
                    </div>

                    {/* Item Total */}
                    <div className="text-right">
                      <p className="text-body font-semibold">
                        ${(item.price * item.quantity).toFixed(2)}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Footer */}
            <div className="border-t border-border px-6 py-4 space-y-4">
              {/* Subtotal */}
              <div className="flex items-center justify-between text-title">
                <span className="font-medium">Subtotal</span>
                <span className="font-semibold">
                  ${total_price.toFixed(2)}
                </span>
              </div>

              {/* Trust Badges */}
              <div className="space-y-2 text-body-sm text-muted-foreground">
                <p className="flex items-center gap-2">
                  <span className="text-success">✓</span> Free shipping over $100
                </p>
                <p className="flex items-center gap-2">
                  <span className="text-success">✓</span> Free 30-day returns
                </p>
              </div>

              {/* Actions */}
              <div className="space-y-2">
                <Link
                  to="/checkout"
                  className="btn btn-primary btn-lg w-full"
                  onClick={onClose}
                >
                  Checkout
                </Link>
                <button
                  onClick={onClose}
                  className="btn btn-ghost btn-md w-full"
                >
                  Continue Shopping
                </button>
              </div>
            </div>
          </>
        )}
      </div>
    </>
  );
}
