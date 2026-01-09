import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Header } from '@/components/layout/Header';
import { MobileBottomNav } from '@/components/layout/MobileBottomNav';
import { Toaster } from '@/components/ui/Toaster';
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
        <div className="flex min-h-screen flex-col bg-stone-50">
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
          <footer className="border-t border-stone-200 bg-white py-12 pb-20 lg:pb-12">
            <div className="container mx-auto px-4 text-center">
              <p className="font-sans text-sm text-stone-600">
                Fashion E-Commerce • Powered by Databricks AI
              </p>
            </div>
          </footer>
          <MobileBottomNav />
          <Toaster />
        </div>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

export default App;
