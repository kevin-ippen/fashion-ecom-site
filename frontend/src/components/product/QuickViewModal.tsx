import { Fragment } from 'react';
import { Dialog, Transition } from '@headlessui/react';
import { X, ShoppingCart, Heart } from 'lucide-react';
import { Link } from 'react-router-dom';
import toast from 'react-hot-toast';
import type { Product } from '@/types';
import { formatPrice } from '@/lib/utils';
import { Button } from '@/components/ui/Button';
import { useCartStore } from '@/stores/cartStore';

interface QuickViewModalProps {
  product: Product | null;
  isOpen: boolean;
  onClose: () => void;
}

export function QuickViewModal({ product, isOpen, onClose }: QuickViewModalProps) {
  const addItem = useCartStore((state) => state.addItem);

  if (!product) return null;

  const handleAddToBag = () => {
    addItem(product);
    toast.success(
      <div className="flex items-center gap-3">
        <ShoppingCart className="h-5 w-5" />
        <div>
          <p className="font-medium">Added to bag</p>
          <p className="text-xs opacity-80">{product.product_display_name}</p>
        </div>
      </div>
    );
    onClose();
  };

  return (
    <Transition appear show={isOpen} as={Fragment}>
      <Dialog as="div" className="relative z-50" onClose={onClose}>
        <Transition.Child
          as={Fragment}
          enter="ease-out duration-300"
          enterFrom="opacity-0"
          enterTo="opacity-100"
          leave="ease-in duration-200"
          leaveFrom="opacity-100"
          leaveTo="opacity-0"
        >
          <div className="fixed inset-0 bg-black/60 backdrop-blur-sm" />
        </Transition.Child>

        <div className="fixed inset-0 overflow-y-auto">
          <div className="flex min-h-full items-center justify-center p-4">
            <Transition.Child
              as={Fragment}
              enter="ease-out duration-300"
              enterFrom="opacity-0 scale-95"
              enterTo="opacity-100 scale-100"
              leave="ease-in duration-200"
              leaveFrom="opacity-100 scale-100"
              leaveTo="opacity-0 scale-95"
            >
              <Dialog.Panel className="w-full max-w-4xl transform overflow-hidden bg-white shadow-2xl transition-all">
                {/* Close button */}
                <button
                  onClick={onClose}
                  className="absolute right-4 top-4 z-10 rounded-full bg-white/90 p-2 text-stone-600 hover:bg-white hover:text-stone-900 transition-colors"
                  aria-label="Close"
                >
                  <X className="h-5 w-5" />
                </button>

                <div className="grid md:grid-cols-2">
                  {/* Image */}
                  <div className="aspect-product bg-stone-100">
                    <img
                      src={product.image_url || ''}
                      alt={product.product_display_name}
                      className="h-full w-full object-cover"
                    />
                  </div>

                  {/* Details */}
                  <div className="flex flex-col p-8 md:p-12">
                    {/* Category */}
                    <p className="text-subtle text-stone-500 mb-3">
                      {product.sub_category}
                    </p>

                    {/* Product name */}
                    <Dialog.Title className="font-serif text-2xl font-semibold tracking-tight text-stone-900 mb-4">
                      {product.product_display_name}
                    </Dialog.Title>

                    {/* Price */}
                    <p className="font-sans text-3xl font-bold text-stone-900 mb-6">
                      {formatPrice(product.price)}
                    </p>

                    {/* Details grid */}
                    <div className="mb-8 space-y-3 border-t border-stone-200 pt-6">
                      {product.base_color && (
                        <div className="flex justify-between text-sm">
                          <span className="text-stone-600">Color</span>
                          <span className="font-medium text-stone-900">{product.base_color}</span>
                        </div>
                      )}
                      {product.gender && (
                        <div className="flex justify-between text-sm">
                          <span className="text-stone-600">Gender</span>
                          <span className="font-medium text-stone-900">{product.gender}</span>
                        </div>
                      )}
                      {product.season && (
                        <div className="flex justify-between text-sm">
                          <span className="text-stone-600">Season</span>
                          <span className="font-medium text-stone-900">{product.season}</span>
                        </div>
                      )}
                      {product.usage && (
                        <div className="flex justify-between text-sm">
                          <span className="text-stone-600">Usage</span>
                          <span className="font-medium text-stone-900">{product.usage}</span>
                        </div>
                      )}
                    </div>

                    {/* Actions */}
                    <div className="mt-auto space-y-3">
                      <Button
                        size="lg"
                        className="w-full"
                        onClick={handleAddToBag}
                      >
                        <ShoppingCart className="mr-2 h-5 w-5" />
                        Add to Bag
                      </Button>

                      <div className="flex gap-3">
                        <Button
                          variant="outline"
                          size="lg"
                          className="flex-1"
                          onClick={(e) => {
                            e.preventDefault();
                            toast('Wishlist feature coming soon!', {
                              icon: '💛',
                            });
                          }}
                        >
                          <Heart className="mr-2 h-4 w-4" />
                          Wishlist
                        </Button>

                        <Link
                          to={`/products/${product.product_id}`}
                          className="flex-1"
                          onClick={onClose}
                        >
                          <Button
                            variant="ghost"
                            size="lg"
                            className="w-full"
                          >
                            View Full Details
                          </Button>
                        </Link>
                      </div>
                    </div>
                  </div>
                </div>
              </Dialog.Panel>
            </Transition.Child>
          </div>
        </div>
      </Dialog>
    </Transition>
  );
}
