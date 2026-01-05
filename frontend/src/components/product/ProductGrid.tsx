import { motion } from 'framer-motion';
import { Product } from '@/types';
import { ProductCard } from './ProductCard';
import { ProductGridSkeleton } from '@/components/ui/Skeleton';

interface ProductGridProps {
  products: Product[];
  showPersonalization?: boolean;
  isLoading?: boolean;
}

const containerVariants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: {
      staggerChildren: 0.05, // Delay between each item
    },
  },
};

const itemVariants = {
  hidden: { opacity: 0, y: 20 },
  visible: {
    opacity: 1,
    y: 0,
    transition: {
      duration: 0.4,
      ease: [0.4, 0, 0.2, 1] as const, // easeOut cubic bezier
    },
  },
};

export function ProductGrid({
  products,
  showPersonalization = false,
  isLoading = false,
}: ProductGridProps) {
  if (isLoading) {
    return <ProductGridSkeleton count={8} />;
  }

  if (products.length === 0) {
    return (
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        className="flex min-h-[400px] items-center justify-center"
      >
        <div className="text-center">
          <p className="font-sans text-lg text-stone-600">No products found</p>
          <p className="mt-2 text-sm text-stone-500">Try adjusting your filters</p>
        </div>
      </motion.div>
    );
  }

  return (
    <motion.div
      variants={containerVariants}
      initial="hidden"
      animate="visible"
      className="grid grid-cols-2 gap-4 md:grid-cols-3 lg:grid-cols-4 lg:gap-6"
    >
      {products.map((product) => (
        <motion.div key={product.product_id} variants={itemVariants}>
          <ProductCard
            product={product}
            showPersonalization={showPersonalization}
          />
        </motion.div>
      ))}
    </motion.div>
  );
}
