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
import Watch, { parseWatchHash } from './pages/Watch.jsx';
import './styles/watch.css';
import { StoreProvider } from './store.jsx';
import './theme.js';

// Public share links (#/watch/...) render on their own, without sign-in or the app shell.
const watch = parseWatchHash(window.location.hash);
window.addEventListener('hashchange', () => {
  if (!!parseWatchHash(window.location.hash) !== !!watch) window.location.reload();
});

createRoot(document.getElementById('root')).render(watch ? <StrictMode><Watch {...watch} /></StrictMode> :
  <StrictMode>
    <ClerkProvider publishableKey={import.meta.env.VITE_CLERK_PUBLISHABLE_KEY} afterSignOutUrl="/">
      <StoreProvider>
        <App />
      </StoreProvider>
    </ClerkProvider>
  </StrictMode>
);
