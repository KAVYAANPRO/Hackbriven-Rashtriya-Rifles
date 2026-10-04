import { ClerkProvider } from '@clerk/react';
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import './styles/ds.css';
import './styles/theme.css';
import './styles/app.css';
import './styles/landing.css';
import './styles/login.css';
import './styles/studio.css';
import './styles/create.css';
import './styles/plans.css';
import './styles/live.css';
import './styles/fx.css';
import App from './App.jsx';
import { StoreProvider } from './store.jsx';

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <ClerkProvider publishableKey={import.meta.env.VITE_CLERK_PUBLISHABLE_KEY} afterSignOutUrl="/">
      <StoreProvider>
        <App />
      </StoreProvider>
    </ClerkProvider>
  </StrictMode>
);
