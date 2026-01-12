import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Filter } from 'lucide-react';
import { productsApi } from '@/api/client';
import { ProductGrid } from '@/components/product/ProductGrid';
import { ProductFilters } from '@/types';
import { Button } from '@/components/ui/Button';
import { ColorSwatches } from '@/components/filters/ColorSwatches';
import { FilterPills } from '@/components/filters/FilterPills';
import { PriceRangeSlider } from '@/components/filters/PriceRangeSlider';
import { MobileFilterDrawer } from '@/components/filters/MobileFilterDrawer';

export function Products() {
  const [page, setPage] = useState(1);
  const [filters, setFilters] = useState<ProductFilters>({});
  const [showFilters, setShowFilters] = useState(false);

  const { data, isLoading } = useQuery({
    queryKey: ['products', page, filters],
    queryFn: () =>
      productsApi.list({
        page,
        page_size: 24,
        ...filters,
      }),
  });

  const { data: filterOptions } = useQuery({
    queryKey: ['filter-options'],
    queryFn: productsApi.getFilterOptions,
  });

  const handleFilterChange = (key: keyof ProductFilters, value: any) => {
    setFilters((prev) => ({ ...prev, [key]: value }));
    setPage(1); // Reset to first page when filters change
  };

  const clearFilters = () => {
    setFilters({});
    setPage(1);
  };

  const removeFilter = (key: keyof ProductFilters) => {
    setFilters((prev) => {
      const updated = { ...prev };
      delete updated[key];
      return updated;
    });
    setPage(1);
  };

  const activeFilterCount = Object.values(filters).filter((v) => v !== undefined).length;

  return (
    <div className="container mx-auto px-4 py-8">
      {/* Header */}
      <div className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">All Products</h1>
          <p className="mt-2 text-gray-600">
            {data?.total || 0} products available
          </p>
        </div>

        {/* Filter toggle (mobile) */}
        <Button
          variant="outline"
          onClick={() => setShowFilters(!showFilters)}
          className="lg:hidden"
        >
          <Filter className="mr-2 h-4 w-4" />
          Filters {activeFilterCount > 0 && `(${activeFilterCount})`}
        </Button>
      </div>

      <div className="flex gap-8">
        {/* Filters Sidebar - Desktop only */}
        <aside className="hidden w-64 flex-shrink-0 lg:block">
          <div className="sticky top-20 rounded-lg border bg-white p-6">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-lg font-semibold">Filters</h2>
              {activeFilterCount > 0 && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={clearFilters}
                  className="text-sm"
                >
                  Clear All
                </Button>
              )}
            </div>

            <div className="space-y-6">
              {/* Gender Filter */}
              {filterOptions?.genders && filterOptions.genders.length > 0 && (
                <div>
                  <label className="mb-2 block text-sm font-medium">Gender</label>
                  <select
                    value={filters.gender || ''}
                    onChange={(e) =>
                      handleFilterChange('gender', e.target.value || undefined)
                    }
                    className="w-full rounded-md border px-3 py-2 text-sm"
                  >
                    <option value="">All</option>
                    {filterOptions.genders.map((gender) => (
                      <option key={gender} value={gender}>
                        {gender}
                      </option>
                    ))}
                  </select>
                </div>
              )}

              {/* Category Filter */}
              {filterOptions?.master_categories &&
                filterOptions.master_categories.length > 0 && (
                  <div>
                    <label className="mb-2 block text-sm font-medium">Category</label>
                    <select
                      value={filters.master_category || ''}
                      onChange={(e) =>
                        handleFilterChange('master_category', e.target.value || undefined)
                      }
                      className="w-full rounded-md border px-3 py-2 text-sm"
                    >
                      <option value="">All</option>
                      {filterOptions.master_categories.map((cat) => (
                        <option key={cat} value={cat}>
                          {cat}
                        </option>
                      ))}
                    </select>
                  </div>
                )}

              {/* Color Filter - Visual Swatches */}
              {filterOptions?.colors && filterOptions.colors.length > 0 && (
                <div>
                  <ColorSwatches
                    colors={filterOptions.colors}
                    selectedColor={filters.base_color}
                    onColorSelect={(color) => handleFilterChange('base_color', color)}
                  />
                </div>
              )}

              {/* Season Filter */}
              {filterOptions?.seasons && filterOptions.seasons.length > 0 && (
                <div>
                  <label className="mb-2 block text-sm font-medium">Season</label>
                  <select
                    value={filters.season || ''}
                    onChange={(e) =>
                      handleFilterChange('season', e.target.value || undefined)
                    }
                    className="w-full rounded-md border px-3 py-2 text-sm"
                  >
                    <option value="">All</option>
                    {filterOptions.seasons.map((season) => (
                      <option key={season} value={season}>
                        {season}
                      </option>
                    ))}
                  </select>
                </div>
              )}

              {/* Price Range - Dual Slider */}
              {filterOptions?.price_range && (
                <div>
                  <PriceRangeSlider
                    min={filterOptions.price_range.min}
                    max={filterOptions.price_range.max}
                    selectedMin={filters.min_price}
                    selectedMax={filters.max_price}
                    onRangeChange={(min, max) => {
                      setFilters((prev) => ({
                        ...prev,
                        min_price: min,
                        max_price: max,
                      }));
                      setPage(1);
                    }}
                  />
                </div>
              )}
            </div>
          </div>
        </aside>

        {/* Products Grid */}
        <main className="flex-1">
          {/* Active Filter Pills */}
          <FilterPills
            filters={filters}
            onRemoveFilter={removeFilter}
            onClearAll={clearFilters}
          />

          <ProductGrid products={data?.products || []} isLoading={isLoading} />

          {/* Pagination */}
          {data && data.total > 0 && (
            <div className="mt-8 flex items-center justify-center gap-4">
              <Button
                variant="outline"
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page === 1}
              >
                Previous
              </Button>
              <span className="text-sm text-gray-600">
                Page {page} of {Math.ceil(data.total / (data.page_size || 24))}
              </span>
              <Button
                variant="outline"
                onClick={() => setPage((p) => p + 1)}
                disabled={!data.has_more}
              >
                Next
              </Button>
            </div>
          )}
        </main>
      </div>

      {/* Mobile Filter Drawer */}
      <MobileFilterDrawer
        isOpen={showFilters}
        onClose={() => setShowFilters(false)}
        onApply={() => {}}
        filterCount={activeFilterCount}
        resultCount={data?.total || 0}
      >
        <div className="space-y-6">
          {/* Gender Filter */}
          {filterOptions?.genders && filterOptions.genders.length > 0 && (
            <div>
              <label className="mb-2 block text-sm font-medium">Gender</label>
              <select
                value={filters.gender || ''}
                onChange={(e) =>
                  handleFilterChange('gender', e.target.value || undefined)
                }
                className="w-full rounded-md border px-3 py-2 text-sm"
              >
                <option value="">All</option>
                {filterOptions.genders.map((gender) => (
                  <option key={gender} value={gender}>
                    {gender}
                  </option>
                ))}
              </select>
            </div>
          )}

          {/* Category Filter */}
          {filterOptions?.master_categories &&
            filterOptions.master_categories.length > 0 && (
              <div>
                <label className="mb-2 block text-sm font-medium">Category</label>
                <select
                  value={filters.master_category || ''}
                  onChange={(e) =>
                    handleFilterChange('master_category', e.target.value || undefined)
                  }
                  className="w-full rounded-md border px-3 py-2 text-sm"
                >
                  <option value="">All</option>
                  {filterOptions.master_categories.map((cat) => (
                    <option key={cat} value={cat}>
                      {cat}
                    </option>
                  ))}
                </select>
              </div>
            )}

          {/* Color Filter - Visual Swatches */}
          {filterOptions?.colors && filterOptions.colors.length > 0 && (
            <div>
              <ColorSwatches
                colors={filterOptions.colors}
                selectedColor={filters.base_color}
                onColorSelect={(color) => handleFilterChange('base_color', color)}
              />
            </div>
          )}

          {/* Season Filter */}
          {filterOptions?.seasons && filterOptions.seasons.length > 0 && (
            <div>
              <label className="mb-2 block text-sm font-medium">Season</label>
              <select
                value={filters.season || ''}
                onChange={(e) =>
                  handleFilterChange('season', e.target.value || undefined)
                }
                className="w-full rounded-md border px-3 py-2 text-sm"
              >
                <option value="">All</option>
                {filterOptions.seasons.map((season) => (
                  <option key={season} value={season}>
                    {season}
                  </option>
                ))}
              </select>
            </div>
          )}

          {/* Price Range - Dual Slider */}
          {filterOptions?.price_range && (
            <div>
              <PriceRangeSlider
                min={filterOptions.price_range.min}
                max={filterOptions.price_range.max}
                selectedMin={filters.min_price}
                selectedMax={filters.max_price}
                onRangeChange={(min, max) => {
                  setFilters((prev) => ({
                    ...prev,
                    min_price: min,
                    max_price: max,
                  }));
                  setPage(1);
                }}
              />
            </div>
          )}

          {/* Clear All Button */}
          {activeFilterCount > 0 && (
            <div className="pt-4">
              <Button
                variant="ghost"
                size="lg"
                onClick={clearFilters}
                className="w-full"
              >
                Clear All Filters
              </Button>
            </div>
          )}
        </div>
      </MobileFilterDrawer>
    </div>
  );
}
