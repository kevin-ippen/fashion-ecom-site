import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { ArrowRight, Sparkles } from 'lucide-react';
import { productsApi } from '@/api/client';
import { ProductGrid } from '@/components/product/ProductGrid';
import { Button } from '@/components/ui/Button';

export function Home() {
  // Fetch new arrivals
  const { data: newArrivalsData, isLoading: newArrivalsLoading } = useQuery({
    queryKey: ['products', 'new-arrivals'],
    queryFn: () => productsApi.getNewArrivals(8, 2017),
  });

  return (
    <div className="min-h-screen bg-stone-50">
      {/* Hero Section - Editorial Style */}
      <section className="relative bg-stone-100 py-24 md:py-32">
        <div className="container mx-auto px-4">
          <div className="mx-auto max-w-4xl">
            {/* Eyebrow text */}
            <p className="text-subtle mb-6 text-center text-stone-600">
              Spring Collection 2025
            </p>

            {/* Hero headline - elegant serif */}
            <h1 className="mb-8 text-center font-serif text-5xl font-semibold leading-tight tracking-tight text-stone-900 md:text-7xl">
              Timeless Elegance
              <br />
              <span className="font-light italic">Redefined</span>
            </h1>

            {/* Subheadline */}
            <p className="mx-auto mb-12 max-w-2xl text-center font-sans text-base leading-relaxed text-stone-600 md:text-lg">
              Experience fashion curated by AI. Discover pieces that match your unique style through
              visual search and intelligent recommendations.
            </p>

            {/* CTAs - refined buttons */}
            <div className="flex flex-col items-center justify-center gap-4 sm:flex-row">
              <Link to="/products">
                <Button size="lg" className="w-full sm:w-auto">
                  Explore Collection
                  <ArrowRight className="ml-2 h-5 w-5" />
                </Button>
              </Link>
              <Link to="/search">
                <Button variant="outline" size="lg" className="w-full sm:w-auto">
                  <Sparkles className="mr-2 h-5 w-5" />
                  Visual Search
                </Button>
              </Link>
            </div>
          </div>
        </div>

        {/* Decorative element */}
        <div className="absolute bottom-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-stone-300 to-transparent"></div>
      </section>

      {/* New Arrivals Section */}
      <section className="border-t border-stone-200 bg-white py-20">
        <div className="container mx-auto px-4">
          <div className="mb-12 text-center">
            <h2 className="font-serif text-3xl font-semibold tracking-tight text-stone-900 md:text-4xl">
              New Arrivals
            </h2>
            <p className="mt-3 font-sans text-base text-stone-600">
              Fresh styles just added
            </p>
          </div>
          <ProductGrid
            products={newArrivalsData?.products || []}
            showPersonalization={false}
            isLoading={newArrivalsLoading}
          />
          <div className="mt-12 text-center">
            <Link to="/products">
              <Button variant="outline" size="lg">
                View All Products
                <ArrowRight className="ml-2 h-5 w-5" />
              </Button>
            </Link>
          </div>
        </div>
      </section>
    </div>
  );
}
