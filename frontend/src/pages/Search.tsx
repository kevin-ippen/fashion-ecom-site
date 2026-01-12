import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useDropzone } from 'react-dropzone';
import { Search as SearchIcon, Upload, X, Image as ImageIcon } from 'lucide-react';
import { searchApi } from '@/api/client';
import { ProductGrid } from '@/components/product/ProductGrid';
import { Button } from '@/components/ui/Button';
import { Card, CardContent } from '@/components/ui/Card';

type SearchMode = 'text' | 'image' | 'hybrid';

export function Search() {
  const [searchMode, setSearchMode] = useState<SearchMode>('text');
  const [textQuery, setTextQuery] = useState('');
  const [uploadedImage, setUploadedImage] = useState<File | null>(null);
  const [imagePreview, setImagePreview] = useState<string | null>(null);
  const [hasSearched, setHasSearched] = useState(false);

  // Text search query
  const {
    data: textSearchResults,
    isLoading: textSearchLoading,
    refetch: refetchTextSearch,
  } = useQuery({
    queryKey: ['text-search', textQuery],
    queryFn: () =>
      searchApi.searchByText({
        query: textQuery,
        limit: 20,
      }),
    enabled: false, // Only run when explicitly triggered
  });

  // Image search query
  const {
    data: imageSearchResults,
    isLoading: imageSearchLoading,
    refetch: refetchImageSearch,
  } = useQuery({
    queryKey: ['image-search', uploadedImage],
    queryFn: () =>
      searchApi.searchByImage({
        image: uploadedImage!,
        limit: 20,
      }),
    enabled: false, // Only run when explicitly triggered
  });

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    accept: {
      'image/*': ['.png', '.jpg', '.jpeg', '.gif'],
    },
    maxFiles: 1,
    onDrop: (acceptedFiles) => {
      if (acceptedFiles.length > 0) {
        const file = acceptedFiles[0];
        setUploadedImage(file);
        setImagePreview(URL.createObjectURL(file));
      }
    },
  });

  const handleTextSearch = () => {
    if (textQuery.trim()) {
      setHasSearched(true);
      refetchTextSearch();
    }
  };

  const handleImageSearch = () => {
    if (uploadedImage) {
      setHasSearched(true);
      refetchImageSearch();
    }
  };

  const handleClearImage = () => {
    setUploadedImage(null);
    if (imagePreview) {
      URL.revokeObjectURL(imagePreview);
      setImagePreview(null);
    }
  };

  const isSearching = textSearchLoading || imageSearchLoading;
  const searchResults =
    searchMode === 'text' ? textSearchResults : imageSearchResults;

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="container mx-auto px-4 py-8">
        {/* Header */}
        <div className="mb-8 text-center">
          <h1 className="text-4xl font-bold">AI-Powered Search</h1>
          <p className="mt-2 text-lg text-gray-600">
            Find products using text descriptions or upload an image
          </p>
        </div>

        {/* Search mode tabs */}
        <div className="mb-6 flex justify-center gap-2">
          <Button
            variant={searchMode === 'text' ? 'default' : 'outline'}
            onClick={() => setSearchMode('text')}
          >
            <SearchIcon className="mr-2 h-4 w-4" />
            Text Search
          </Button>
          <Button
            variant={searchMode === 'image' ? 'default' : 'outline'}
            onClick={() => setSearchMode('image')}
          >
            <ImageIcon className="mr-2 h-4 w-4" />
            Visual Search
          </Button>
        </div>

        {/* Search interface */}
        <div className="mx-auto max-w-2xl">
          {searchMode === 'text' ? (
            <Card>
              <CardContent className="p-6">
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={textQuery}
                    onChange={(e) => setTextQuery(e.target.value)}
                    onKeyPress={(e) => e.key === 'Enter' && handleTextSearch()}
                    placeholder="Describe what you're looking for... (e.g., 'red summer dress')"
                    className="flex-1 rounded-md border px-4 py-3 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                  <Button
                    onClick={handleTextSearch}
                    disabled={!textQuery.trim() || isSearching}
                    size="lg"
                  >
                    <SearchIcon className="h-5 w-5" />
                  </Button>
                </div>
                <div className="mt-3 flex flex-wrap gap-2">
                  <span className="text-xs text-gray-500">Try:</span>
                  {['casual t-shirt', 'formal shoes', 'winter jacket', 'sports wear'].map(
                    (example) => (
                      <button
                        key={example}
                        onClick={() => {
                          setTextQuery(example);
                        }}
                        className="rounded-full bg-gray-100 px-3 py-1 text-xs text-gray-700 hover:bg-gray-200"
                      >
                        {example}
                      </button>
                    )
                  )}
                </div>
              </CardContent>
            </Card>
          ) : (
            <Card>
              <CardContent className="p-6">
                {!imagePreview ? (
                  <div
                    {...getRootProps()}
                    className={`cursor-pointer rounded-lg border-2 border-dashed p-12 text-center transition-colors ${
                      isDragActive
                        ? 'border-blue-500 bg-blue-50'
                        : 'border-gray-300 hover:border-gray-400'
                    }`}
                  >
                    <input {...getInputProps()} />
                    <Upload className="mx-auto h-12 w-12 text-gray-400" />
                    <p className="mt-4 text-sm font-medium text-gray-900">
                      {isDragActive
                        ? 'Drop your image here'
                        : 'Drag & drop an image, or click to select'}
                    </p>
                    <p className="mt-2 text-xs text-gray-500">
                      PNG, JPG, GIF up to 10MB
                    </p>
                  </div>
                ) : (
                  <div className="space-y-4">
                    <div className="relative">
                      <img
                        src={imagePreview}
                        alt="Upload preview"
                        className="mx-auto max-h-64 rounded-lg"
                      />
                      <button
                        onClick={handleClearImage}
                        className="absolute right-2 top-2 rounded-full bg-black/50 p-2 text-white hover:bg-black/70"
                      >
                        <X className="h-4 w-4" />
                      </button>
                    </div>
                    <Button
                      onClick={handleImageSearch}
                      disabled={isSearching}
                      className="w-full"
                      size="lg"
                    >
                      <SearchIcon className="mr-2 h-5 w-5" />
                      Find Similar Products
                    </Button>
                  </div>
                )}
              </CardContent>
            </Card>
          )}
        </div>

        {/* Search results */}
        {hasSearched && (
          <div className="mt-12">
            {isSearching ? (
              <div className="text-center">
                <div className="inline-block h-8 w-8 animate-spin rounded-full border-4 border-gray-300 border-t-blue-600" />
                <p className="mt-4 text-gray-600">Searching for matching products...</p>
              </div>
            ) : searchResults && searchResults.products.length > 0 ? (
              <div>
                <div className="mb-6 flex items-center justify-between">
                  <div>
                    <h2 className="text-2xl font-bold">Search Results</h2>
                    <p className="text-sm text-gray-600">
                      Found {searchResults.products.length} matching products
                      {searchResults.query && (
                        <span> for "{searchResults.query}"</span>
                      )}
                    </p>
                  </div>
                  {searchMode === 'image' && (
                    <Button variant="outline" onClick={handleClearImage}>
                      Clear & Search Again
                    </Button>
                  )}
                </div>
                <ProductGrid
                  products={searchResults.products}
                />
              </div>
            ) : (
              <div className="rounded-lg border bg-white p-12 text-center">
                <SearchIcon className="mx-auto h-12 w-12 text-gray-400" />
                <h3 className="mt-4 text-lg font-semibold">No results found</h3>
                <p className="mt-2 text-sm text-gray-600">
                  Try different keywords or upload a different image
                </p>
              </div>
            )}
          </div>
        )}

        {/* How it works section */}
        {!hasSearched && (
          <div className="mx-auto mt-16 max-w-4xl">
            <h2 className="mb-8 text-center text-2xl font-bold">How It Works</h2>
            <div className="grid gap-8 md:grid-cols-2">
              <Card>
                <CardContent className="p-6">
                  <SearchIcon className="mb-4 h-10 w-10 text-blue-600" />
                  <h3 className="mb-2 text-lg font-semibold">Text Search</h3>
                  <p className="text-sm text-gray-600">
                    Describe what you're looking for using natural language. Our AI
                    understands context and finds products that match your description.
                  </p>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="p-6">
                  <ImageIcon className="mb-4 h-10 w-10 text-blue-600" />
                  <h3 className="mb-2 text-lg font-semibold">Visual Search</h3>
                  <p className="text-sm text-gray-600">
                    Upload an image of a product or style you like. Our AI analyzes the
                    visual features and finds similar items from our catalog.
                  </p>
                </CardContent>
              </Card>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
