import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Header } from '@/components/layout/Header';
import { Home } from '@/pages/Home';
import { Products } from '@/pages/Products';
import { ProductDetail } from '@/pages/ProductDetail';
import { Search } from '@/pages/Search';
import { UserProfile } from '@/pages/UserProfile';
import { Cart } from '@/pages/Cart';

// Create a client
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
      staleTime: 5 * 60 * 1000, // 5 minutes
    },
  },
});

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <div className="flex min-h-screen flex-col">
          <Header />
          <main className="flex-1">
            <Routes>
              <Route path="/" element={<Home />} />
              <Route path="/products" element={<Products />} />
              <Route path="/products/:productId" element={<ProductDetail />} />
              <Route path="/search" element={<Search />} />
              <Route path="/profile/:userId" element={<UserProfile />} />
              <Route path="/cart" element={<Cart />} />
            </Routes>
          </main>
          <footer className="border-t bg-gray-50 py-8">
            <div className="container mx-auto px-4 text-center text-sm text-gray-600">
              <p>Fashion Ecommerce Demo - Powered by Databricks</p>
            </div>
          </footer>
        </div>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

export default App;
