import { Toaster as HotToaster } from 'react-hot-toast';

export function Toaster() {
  return (
    <HotToaster
      position="top-right"
      toastOptions={{
        // Default options
        duration: 3000,
        style: {
          background: 'hsl(30 10% 10%)',
          color: 'hsl(40 20% 99%)',
          padding: '16px',
          borderRadius: '4px',
          fontFamily: 'Inter, sans-serif',
          fontSize: '14px',
          fontWeight: '500',
        },
        // Success toast
        success: {
          iconTheme: {
            primary: 'hsl(38 70% 55%)', // Gold
            secondary: 'white',
          },
        },
        // Error toast
        error: {
          iconTheme: {
            primary: 'hsl(0 72% 51%)',
            secondary: 'white',
          },
          duration: 4000,
        },
      }}
    />
  );
}
