import { useParams, Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  User,
  ArrowLeft,
  ShoppingBag,
  DollarSign,
  Heart,
  TrendingUp,
  Sparkles,
} from 'lucide-react';
import { usersApi } from '@/api/client';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { ProductGrid } from '@/components/product/ProductGrid';
import { formatPrice } from '@/lib/utils';
import { usePersonaStore } from '@/stores/personaStore';

export function UserProfile() {
  const { userId } = useParams<{ userId: string }>();
  const { selectedPersona, setPersona } = usePersonaStore();

  // Fetch persona details
  const { data: persona, isLoading: personaLoading } = useQuery({
    queryKey: ['persona', userId],
    queryFn: () => usersApi.getPersona(userId!),
    enabled: !!userId,
  });

  // Fetch full profile with purchase history
  const { data: profile, isLoading: profileLoading } = useQuery({
    queryKey: ['profile', userId],
    queryFn: () => usersApi.getProfile(userId!),
    enabled: !!userId,
  });

  const isLoading = personaLoading || profileLoading;

  const handleActivatePersona = () => {
    if (persona) {
      setPersona(persona);
    }
  };

  if (isLoading) {
    return (
      <div className="container mx-auto px-4 py-8">
        <div className="animate-pulse space-y-8">
          <div className="h-48 rounded-lg bg-gray-200" />
          <div className="grid gap-6 md:grid-cols-3">
            <div className="h-32 rounded-lg bg-gray-200" />
            <div className="h-32 rounded-lg bg-gray-200" />
            <div className="h-32 rounded-lg bg-gray-200" />
          </div>
        </div>
      </div>
    );
  }

  if (!persona || !profile) {
    return (
      <div className="container mx-auto px-4 py-16 text-center">
        <h2 className="text-2xl font-bold">Profile not found</h2>
        <Link to="/" className="mt-4 inline-block text-blue-600 hover:underline">
          Back to home
        </Link>
      </div>
    );
  }

  const isActive = selectedPersona?.user_id === persona.user_id;

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="container mx-auto px-4 py-8">
        {/* Back button */}
        <Link
          to="/"
          className="mb-6 inline-flex items-center text-sm text-gray-600 hover:text-gray-900"
        >
          <ArrowLeft className="mr-2 h-4 w-4" />
          Back to home
        </Link>

        {/* Profile header */}
        <Card className="mb-8">
          <CardContent className="p-8">
            <div className="flex flex-col items-center gap-6 md:flex-row">
              <div className="flex h-24 w-24 items-center justify-center rounded-full bg-gradient-to-br from-blue-500 to-purple-600">
                <User className="h-12 w-12 text-white" />
              </div>
              <div className="flex-1 text-center md:text-left">
                <div className="flex items-center justify-center gap-3 md:justify-start">
                  <h1 className="text-3xl font-bold">{persona.name}</h1>
                  {isActive && (
                    <span className="rounded-full bg-green-100 px-3 py-1 text-sm font-medium text-green-800">
                      Active
                    </span>
                  )}
                </div>
                <p className="mt-2 text-lg text-gray-600">{persona.description}</p>
                <div className="mt-4 flex flex-wrap justify-center gap-2 md:justify-start">
                  {persona.style_tags.map((tag: string) => (
                    <span
                      key={tag}
                      className="rounded-full bg-blue-100 px-3 py-1 text-sm text-blue-800"
                    >
                      #{tag}
                    </span>
                  ))}
                </div>
              </div>
              {!isActive && (
                <Button size="lg" onClick={handleActivatePersona}>
                  <Sparkles className="mr-2 h-5 w-5" />
                  Activate Persona
                </Button>
              )}
            </div>
          </CardContent>
        </Card>

        {/* Stats grid */}
        <div className="mb-8 grid gap-6 md:grid-cols-4">
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="flex items-center gap-2 text-sm font-medium text-gray-500">
                <ShoppingBag className="h-4 w-4" />
                Interactions
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-3xl font-bold">{profile.num_interactions}</p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="flex items-center gap-2 text-sm font-medium text-gray-500">
                <DollarSign className="h-4 w-4" />
                Avg Price Point
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-3xl font-bold">{formatPrice(profile.avg_price_point)}</p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="flex items-center gap-2 text-sm font-medium text-gray-500">
                <TrendingUp className="h-4 w-4" />
                Price Range
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-3xl font-bold">
                {formatPrice(profile.price_range.min)} - {formatPrice(profile.price_range.max)}
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="flex items-center gap-2 text-sm font-medium text-gray-500">
                <Heart className="h-4 w-4" />
                Segment
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-xl font-bold">{profile.segment}</p>
            </CardContent>
          </Card>
        </div>

        {/* Preferences */}
        <div className="mb-8 grid gap-6 md:grid-cols-2">
          <Card>
            <CardHeader>
              <CardTitle>Preferred Categories</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex flex-wrap gap-2">
                {profile.preferred_categories.map((category) => (
                  <span
                    key={category}
                    className="rounded-lg bg-gray-100 px-4 py-2 text-sm font-medium text-gray-800"
                  >
                    {category}
                  </span>
                ))}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Favorite Colors</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex flex-wrap gap-2">
                {profile.color_prefs.map((color) => (
                  <span
                    key={color}
                    className="rounded-lg bg-gray-100 px-4 py-2 text-sm font-medium text-gray-800"
                  >
                    {color}
                  </span>
                ))}
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Shopping preferences breakdown */}
        <Card className="mb-8">
          <CardHeader>
            <CardTitle>Shopping Preferences</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div>
                <div className="mb-2 flex items-center justify-between text-sm">
                  <span className="text-gray-600">Price Distribution</span>
                  <span className="font-medium">
                    {formatPrice(profile.price_range.min)} -{' '}
                    {formatPrice(profile.price_range.max)}
                  </span>
                </div>
                <div className="relative h-2 w-full rounded-full bg-gray-200">
                  <div
                    className="absolute left-0 h-2 rounded-full bg-blue-600"
                    style={{
                      width: '100%',
                    }}
                  />
                </div>
                <div className="mt-1 flex justify-between text-xs text-gray-500">
                  <span>Min: {formatPrice(profile.price_range.min)}</span>
                  <span>Avg: {formatPrice(profile.price_range.avg)}</span>
                  <span>Max: {formatPrice(profile.price_range.max)}</span>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Purchase history */}
        <div>
          <div className="mb-6 flex items-center justify-between">
            <div>
              <h2 className="text-2xl font-bold">Recent Purchase History</h2>
              <p className="text-sm text-gray-600">
                Products that match {persona.name}'s style profile
              </p>
            </div>
            <Link to="/products">
              <Button variant="outline">Browse More Products</Button>
            </Link>
          </div>
          {profile.purchase_history.length > 0 ? (
            <ProductGrid products={profile.purchase_history} />
          ) : (
            <Card>
              <CardContent className="p-12 text-center">
                <ShoppingBag className="mx-auto h-12 w-12 text-gray-400" />
                <p className="mt-4 text-gray-600">No purchase history yet</p>
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
