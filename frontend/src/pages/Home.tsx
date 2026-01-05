import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { ArrowRight, Sparkles } from 'lucide-react';
import { productsApi, searchApi } from '@/api/client';
import { usePersonaStore } from '@/stores/personaStore';
import { ProductGrid } from '@/components/product/ProductGrid';
import { Button } from '@/components/ui/Button';

export function Home() {
  const selectedPersona = usePersonaStore((state) => state.selectedPersona);

  // Fetch featured products
  const { data: featuredData, isLoading: featuredLoading } = useQuery({
    queryKey: ['products', 'featured'],
    queryFn: () =>
      productsApi.list({
        page: 1,
        page_size: 8,
        sort_by: 'price',
        sort_order: 'DESC',
      }),
  });

  // Fetch personalized recommendations if persona is selected
  const { data: recommendationsData, isLoading: recommendationsLoading } = useQuery({
    queryKey: ['recommendations', selectedPersona?.user_id],
    queryFn: () => searchApi.getRecommendations(selectedPersona!.user_id, 8),
    enabled: !!selectedPersona,
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

      {/* Personalized Recommendations Section */}
      {selectedPersona && (
        <section className="border-t border-stone-200 bg-white py-20">
          <div className="container mx-auto px-4">
            <div className="mb-12 flex flex-col items-start justify-between gap-4 md:flex-row md:items-center">
              <div>
                <div className="mb-3 flex items-center gap-3">
                  <Sparkles className="h-6 w-6 text-amber-600" />
                  <h2 className="font-serif text-3xl font-semibold tracking-tight text-stone-900 md:text-4xl">
                    Curated for You
                  </h2>
                </div>
                <p className="font-sans text-base text-stone-600">
                  Personalized selections for {selectedPersona.name}
                </p>
              </div>
              <Link to={`/profile/${selectedPersona.user_id}`}>
                <Button variant="outline">View Profile</Button>
              </Link>
            </div>
            <ProductGrid
              products={recommendationsData?.products || []}
              showPersonalization={true}
              isLoading={recommendationsLoading}
            />
          </div>
        </section>
      )}

      {/* Featured Products Section */}
      <section className="border-t border-stone-200 bg-stone-50 py-20">
        <div className="container mx-auto px-4">
          <div className="mb-12 text-center">
            <h2 className="font-serif text-3xl font-semibold tracking-tight text-stone-900 md:text-4xl">
              {selectedPersona ? 'Discover More' : 'New Arrivals'}
            </h2>
            <p className="mt-3 font-sans text-base text-stone-600">
              {selectedPersona
                ? 'Explore our latest collection'
                : 'Fresh styles added weekly'}
            </p>
          </div>
          <ProductGrid
            products={featuredData?.products || []}
            showPersonalization={false}
            isLoading={featuredLoading}
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

      {/* Call to action for persona selection */}
      {!selectedPersona && (
        <section className="border-t border-stone-200 bg-white py-20">
          <div className="container mx-auto px-4 text-center">
            <div className="mx-auto max-w-2xl">
              <div className="mx-auto mb-6 flex h-16 w-16 items-center justify-center rounded-full bg-amber-100">
                <Sparkles className="h-8 w-8 text-amber-600" />
              </div>
              <h2 className="font-serif text-3xl font-semibold tracking-tight text-stone-900 md:text-4xl">
                Personalized Experience
              </h2>
              <p className="mt-4 font-sans text-base leading-relaxed text-stone-600 md:text-lg">
                Choose a style persona to unlock AI-powered recommendations tailored to your
                preferences, budget, and lifestyle.
              </p>
              <div className="mt-8">
                <Button size="lg" variant="luxury">
                  Choose Your Persona
                </Button>
              </div>
            </div>
          </div>
        </section>
      )}
    </div>
  );
}
