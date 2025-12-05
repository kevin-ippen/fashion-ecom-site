import { useQuery } from '@tanstack/react-query';
import { X, User } from 'lucide-react';
import { usersApi } from '@/api/client';
import { usePersonaStore } from '@/stores/personaStore';
import { Button } from '@/components/ui/Button';
import { Card, CardContent } from '@/components/ui/Card';
import { formatPrice } from '@/lib/utils';

interface PersonaSelectorProps {
  onClose: () => void;
}

export function PersonaSelector({ onClose }: PersonaSelectorProps) {
  const { data: personas, isLoading } = useQuery({
    queryKey: ['personas'],
    queryFn: usersApi.listPersonas,
  });

  const { selectedPersona, setPersona } = usePersonaStore();

  const handleSelectPersona = (persona: any) => {
    setPersona(persona);
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="max-h-[90vh] w-full max-w-4xl overflow-y-auto rounded-lg bg-white p-6 shadow-2xl">
        {/* Header */}
        <div className="mb-6 flex items-center justify-between">
          <div>
            <h2 className="text-2xl font-bold">Choose Your Shopping Persona</h2>
            <p className="mt-1 text-sm text-gray-500">
              Select a persona to see personalized recommendations
            </p>
          </div>
          <Button variant="ghost" size="sm" onClick={onClose}>
            <X className="h-5 w-5" />
          </Button>
        </div>

        {/* Loading state */}
        {isLoading && (
          <div className="space-y-4">
            {Array.from({ length: 3 }).map((_, i) => (
              <div key={i} className="h-32 animate-pulse rounded-lg bg-gray-200" />
            ))}
          </div>
        )}

        {/* Personas grid */}
        {personas && (
          <div className="grid gap-4 md:grid-cols-2">
            {personas.map((persona) => (
              <Card
                key={persona.user_id}
                className={`cursor-pointer transition-all hover:shadow-lg ${
                  selectedPersona?.user_id === persona.user_id
                    ? 'ring-2 ring-blue-600'
                    : ''
                }`}
                onClick={() => handleSelectPersona(persona)}
              >
                <CardContent className="p-6">
                  <div className="flex items-start gap-4">
                    <div className="flex h-12 w-12 items-center justify-center rounded-full bg-blue-100">
                      <User className="h-6 w-6 text-blue-600" />
                    </div>
                    <div className="flex-1">
                      <div className="flex items-center justify-between">
                        <h3 className="font-semibold">{persona.name}</h3>
                        {selectedPersona?.user_id === persona.user_id && (
                          <span className="rounded-full bg-blue-600 px-2 py-1 text-xs text-white">
                            Active
                          </span>
                        )}
                      </div>
                      <p className="mt-1 text-sm text-gray-600">{persona.description}</p>

                      {/* Stats */}
                      <div className="mt-4 grid grid-cols-2 gap-3 text-xs">
                        <div>
                          <div className="font-medium text-gray-500">Avg Price</div>
                          <div className="mt-1 font-semibold">
                            {formatPrice(persona.avg_price_point)}
                          </div>
                        </div>
                        <div>
                          <div className="font-medium text-gray-500">Segment</div>
                          <div className="mt-1 font-semibold">{persona.segment}</div>
                        </div>
                      </div>

                      {/* Preferences */}
                      <div className="mt-3">
                        <div className="text-xs font-medium text-gray-500">
                          Preferred Categories:
                        </div>
                        <div className="mt-1 flex flex-wrap gap-1">
                          {persona.preferred_categories.slice(0, 3).map((cat: string) => (
                            <span
                              key={cat}
                              className="rounded bg-gray-100 px-2 py-0.5 text-xs text-gray-700"
                            >
                              {cat}
                            </span>
                          ))}
                        </div>
                      </div>

                      {/* Style tags */}
                      <div className="mt-3 flex flex-wrap gap-1">
                        {persona.style_tags.map((tag: string) => (
                          <span
                            key={tag}
                            className="rounded-full bg-blue-50 px-2 py-0.5 text-xs text-blue-700"
                          >
                            #{tag}
                          </span>
                        ))}
                      </div>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}

        {/* Browse without persona */}
        <div className="mt-6 border-t pt-6 text-center">
          <Button
            variant="outline"
            onClick={() => {
              setPersona(null);
              onClose();
            }}
          >
            Browse Without Persona
          </Button>
        </div>
      </div>
    </div>
  );
}
