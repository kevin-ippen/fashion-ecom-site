import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { Cart, CartItem, Product } from '@/types';

interface CartStore extends Cart {
  addItem: (product: Product, quantity?: number) => void;
  removeItem: (productId: string) => void;
  updateQuantity: (productId: string, quantity: number) => void;
  clearCart: () => void;
}

export const useCartStore = create<CartStore>()(
  persist(
    (set) => ({
      items: [],
      total: 0,
      item_count: 0,

      addItem: (product: Product, quantity = 1) =>
        set((state) => {
          const existingItem = state.items.find(
            (item) => item.product_id === product.product_id
          );

          let newItems: CartItem[];
          if (existingItem) {
            newItems = state.items.map((item) =>
              item.product_id === product.product_id
                ? { ...item, quantity: item.quantity + quantity }
                : item
            );
          } else {
            newItems = [
              ...state.items,
              { product_id: product.product_id, quantity, product },
            ];
          }

          const total = newItems.reduce(
            (sum, item) => sum + (item.product?.price || 0) * item.quantity,
            0
          );
          const item_count = newItems.reduce((sum, item) => sum + item.quantity, 0);

          return { items: newItems, total, item_count };
        }),

      removeItem: (productId: string) =>
        set((state) => {
          const newItems = state.items.filter((item) => item.product_id !== productId);
          const total = newItems.reduce(
            (sum, item) => sum + (item.product?.price || 0) * item.quantity,
            0
          );
          const item_count = newItems.reduce((sum, item) => sum + item.quantity, 0);

          return { items: newItems, total, item_count };
        }),

      updateQuantity: (productId: string, quantity: number) =>
        set((state) => {
          if (quantity <= 0) {
            return state;
          }

          const newItems = state.items.map((item) =>
            item.product_id === productId ? { ...item, quantity } : item
          );

          const total = newItems.reduce(
            (sum, item) => sum + (item.product?.price || 0) * item.quantity,
            0
          );
          const item_count = newItems.reduce((sum, item) => sum + item.quantity, 0);

          return { items: newItems, total, item_count };
        }),

      clearCart: () => set({ items: [], total: 0, item_count: 0 }),
    }),
    {
      name: 'cart-storage',
    }
  )
);
