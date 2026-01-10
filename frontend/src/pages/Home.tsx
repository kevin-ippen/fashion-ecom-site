import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { ArrowRight, Sparkles } from 'lucide-react';
import { productsApi, searchApi } from '@/api/client';
import { usePersonaStore } from '@/stores/personaStore';
import { ProductGrid } from '@/components/product/ProductGrid';
import { Button } from '@/components/ui/Button';

export function Home() {
  const selectedPersona = usePersonaStore((state) => state.selectedPersona);

  // Fetch trending products
  const { data: trendingData, isLoading: trendingLoading } = useQuery({
    queryKey: ['products', 'trending'],
    queryFn: () => productsApi.getTrending(8),
  });

  // Fetch seasonal products
  const { data: seasonalData, isLoading: seasonalLoading } = useQuery({
    queryKey: ['products', 'seasonal'],
    queryFn: () => productsApi.getSeasonal(undefined, 8),
  });

  // Fetch new arrivals
  const { data: newArrivalsData, isLoading: newArrivalsLoading } = useQuery({
    queryKey: ['products', 'new-arrivals'],
    queryFn: () => productsApi.getNewArrivals(8, 2017),
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

      {/* Trending Products Section */}
      <section className="border-t border-stone-200 bg-white py-20">
        <div className="container mx-auto px-4">
          <div className="mb-12 text-center">
            <h2 className="font-serif text-3xl font-semibold tracking-tight text-stone-900 md:text-4xl">
              Trending Now
            </h2>
            <p className="mt-3 font-sans text-base text-stone-600">
              Most popular styles this week
            </p>
          </div>
          <ProductGrid
            products={trendingData?.products || []}
            showPersonalization={false}
            isLoading={trendingLoading}
          />
          <div className="mt-12 text-center">
            <Link to="/products">
              <Button variant="outline" size="lg">
                View All Trending
                <ArrowRight className="ml-2 h-5 w-5" />
              </Button>
            </Link>
          </div>
        </div>
      </section>

      {/* Seasonal Collection Section */}
      <section className="border-t border-stone-200 bg-stone-50 py-20">
        <div className="container mx-auto px-4">
          <div className="mb-12 text-center">
            <h2 className="font-serif text-3xl font-semibold tracking-tight text-stone-900 md:text-4xl">
              Winter Collection
            </h2>
            <p className="mt-3 font-sans text-base text-stone-600">
              Stay warm and stylish this season
            </p>
          </div>
          <ProductGrid
            products={seasonalData?.products || []}
            showPersonalization={false}
            isLoading={seasonalLoading}
          />
        </div>
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
