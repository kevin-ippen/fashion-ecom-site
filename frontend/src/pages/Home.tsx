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
    <div className="min-h-screen">
      {/* Hero Section */}
      <section className="bg-gradient-to-br from-blue-50 via-white to-purple-50 py-20">
        <div className="container mx-auto px-4">
          <div className="mx-auto max-w-3xl text-center">
            <h1 className="text-5xl font-bold tracking-tight text-gray-900 sm:text-6xl">
              Discover Fashion
              <br />
              <span className="text-blue-600">Powered by AI</span>
            </h1>
            <p className="mt-6 text-lg leading-8 text-gray-600">
              Experience personalized shopping with visual search and intelligent recommendations
              tailored to your style preferences.
            </p>
            <div className="mt-10 flex items-center justify-center gap-4">
              <Link to="/products">
                <Button size="lg">
                  Shop Now
                  <ArrowRight className="ml-2 h-5 w-5" />
                </Button>
              </Link>
              <Link to="/search">
                <Button variant="outline" size="lg">
                  Try Visual Search
                </Button>
              </Link>
            </div>
          </div>
        </div>
      </section>

      {/* Personalized Recommendations Section */}
      {selectedPersona && (
        <section className="border-t bg-gradient-to-r from-blue-50 to-purple-50 py-16">
          <div className="container mx-auto px-4">
            <div className="mb-8 flex items-center justify-between">
              <div>
                <div className="flex items-center gap-2">
                  <Sparkles className="h-6 w-6 text-blue-600" />
                  <h2 className="text-3xl font-bold">Recommended for You</h2>
                </div>
                <p className="mt-2 text-gray-600">
                  Personalized picks based on {selectedPersona.name}'s style preferences
                </p>
              </div>
              <Link to={`/profile/${selectedPersona.user_id}`}>
                <Button variant="outline">View Full Profile</Button>
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
      <section className="py-16">
        <div className="container mx-auto px-4">
          <div className="mb-8">
            <h2 className="text-3xl font-bold">
              {selectedPersona ? 'More to Explore' : 'Featured Products'}
            </h2>
            <p className="mt-2 text-gray-600">
              {selectedPersona
                ? 'Discover more items from our collection'
                : 'Check out our latest and most popular items'}
            </p>
          </div>
          <ProductGrid
            products={featuredData?.products || []}
            showPersonalization={false}
            isLoading={featuredLoading}
          />
          <div className="mt-8 text-center">
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
        <section className="border-t bg-gray-50 py-16">
          <div className="container mx-auto px-4 text-center">
            <div className="mx-auto max-w-2xl">
              <Sparkles className="mx-auto h-12 w-12 text-blue-600" />
              <h2 className="mt-4 text-3xl font-bold">Get Personalized Recommendations</h2>
              <p className="mt-4 text-lg text-gray-600">
                Select a shopping persona to see products tailored to your style, preferences, and
                budget.
              </p>
              <div className="mt-8">
                <Button size="lg">Choose Your Persona</Button>
              </div>
            </div>
          </div>
        </section>
      )}
    </div>
  );
}
