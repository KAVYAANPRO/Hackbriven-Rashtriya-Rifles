import { useStore } from './store.jsx';
import { ADMIN_ROUTES } from './data.js';
import AppShell from './components/AppShell.jsx';
import Icon from './components/Icon.jsx';
import PointerFX from './components/PointerFX.jsx';
import { ErrorState } from './components/common.jsx';
import Landing from './pages/Landing.jsx';
import Login from './pages/Login.jsx';
import Create from './pages/Create.jsx';
import Jobs from './pages/Jobs.jsx';
import JobDetail from './pages/JobDetail.jsx';
import Orchestra from './pages/Orchestra.jsx';
import Analytics from './pages/Analytics.jsx';
import Credits from './pages/Credits.jsx';
import Settings from './pages/Settings.jsx';

const PAGES = {
  create: Create,
  jobs: Jobs,
  job: JobDetail,
  orchestra: Orchestra,
  analytics: Analytics,
  credits: Credits,
  settings: Settings,
};

function BootScreen({ error, onRetry, onSignOut }) {
  return (
    <div className="boot2">
      {error ? (
        <ErrorState title="Can't reach the server" message={error} onRetry={onRetry}>
          <button type="button" className="btn2 btn2--ghost" onClick={onSignOut}>Sign out</button>
        </ErrorState>
      ) : (
        <div className="boot2-load" role="status"><i className="spin" />Restoring your session…</div>
      )}
    </div>
  );
}

export default function App() {
  const { route, authed, booting, bootError, retryBoot, signOut, toast, user } = useStore();

  let view;
  if (route === 'landing') view = <Landing />;
  else if (booting) view = <BootScreen />;
  else if (bootError && !authed) view = <BootScreen error={bootError} onRetry={retryBoot} onSignOut={signOut} />;
  else if (!authed) view = <Login />;
  else {
    // Admin-only pages fall back to Create for everyone else (the backend refuses their data anyway).
    const allowed = !ADMIN_ROUTES.includes(route) || !!(user && user.is_admin);
    const Page = (allowed && PAGES[route]) || Create;
    view = <AppShell><Page /></AppShell>;
  }

  return (
    <div className="app-root">
      <PointerFX />
      {view}
      {toast && <div className="st-toast" role="status"><Icon name="check" size={16} />{toast}</div>}
    </div>
  );
}
