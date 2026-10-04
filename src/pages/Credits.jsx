import { fmt, formatPrice, periodLabel, planFor, planForResolution, planList, resolutionList, tierName } from '../data.js';
import { toMs } from '../api/adapt.js';
import { useStore } from '../store.jsx';
import { ErrorState, PageHeader, Skeleton } from '../components/common.jsx';
import { CountUp } from '../components/deck/parts.jsx';
import Icon from '../components/Icon.jsx';
import { openPlanDialog } from '../components/planDialogBus.js';

function featuresOf(p) {
  const list = [];
  list.push(p.period_days
    ? `${p.credits} credits every ${p.period_days === 30 ? 'month' : `${p.period_days} days`}`
    : `${p.credits} credits to start`);
  list.push(p.tiers.length === 1 ? `${tierName(p.tiers[0])} motion tier only` : `${p.tiers.map(tierName).join(', ')} tiers`);
  if (p.period_days) list.push(`Active for ${p.period_days} days, then back to Free`);
  if (Array.isArray(p.perks)) list.push(...p.perks);
  return list;
}

// "Up to 1080p": the largest resolution the plan lists. null when the server sends no resolution data.
function resolutionCap(pricing, p) {
  if (!Array.isArray(p.resolutions) || !p.resolutions.length) return null;
  const known = resolutionList(pricing)
    .filter((r) => p.resolutions.includes(r.id))
    .sort((a, b) => (a.width || 0) * (a.height || 0) - (b.width || 0) * (b.height || 0));
  const top = known[known.length - 1];
  return `Up to ${top ? top.label || top.id : p.resolutions[p.resolutions.length - 1]}`;
}

function PlanCard({ p, index, rank, currentRank, planId, tiers, pricing, payReady, onPick }) {
  const isCurrent = p.id === planId;
  const isUpgrade = rank > currentRank;
  const resCap = resolutionCap(pricing, p);

  return (
    <article
      className={'spot-card pl-card rise' + (isCurrent ? ' is-current' : '')}
      style={{ '--i': index + 1 }}
      aria-label={`${p.name} plan`}
    >
      <header className="pl-card-top">
        <h3>{p.name}</h3>
        {isCurrent && <span className="pl-badge pl-badge--current">Current plan</span>}
      </header>

      <div className="pl-price">
        <b>{formatPrice(p.price_paise)}</b>
        <span>{periodLabel(p)}</span>
      </div>

      <ul className="pl-feats">
        {featuresOf(p).map((f) => (
          <li key={f}><Icon name="check" size={15} /><span>{f}</span></li>
        ))}
      </ul>

      <div className="pl-tiers" role="list" aria-label={`Motion tiers on ${p.name}`}>
        {tiers.map((t) => {
          const ok = p.tiers.includes(t.v);
          const need = !ok ? planFor(pricing, t.v) : null;
          return (
            <div key={t.v} role="listitem" className={'pl-tier' + (ok ? '' : ' is-locked')}>
              <span className="pl-tier-n">
                <Icon name={ok ? 'check' : 'lock'} size={14} />
                <b>{t.label}</b>
              </span>
              <span className="pl-tier-c mono">{t.cost == null ? '–' : `${t.cost} cr`}</span>
              {!ok && <span className="pl-tier-note">Needs {need ? need.name : 'a higher plan'}</span>}
            </div>
          );
        })}
        {resCap && (
          <div role="listitem" className="pl-tier pl-tier--res">
            <span className="pl-tier-n"><Icon name="check" size={14} /><b>Resolution</b></span>
            <span className="pl-tier-c mono">{resCap}</span>
          </div>
        )}
      </div>

      <div className="pl-card-act">
        {isCurrent && <button type="button" className="btn2 btn2--ghost btn2--block" disabled>Current plan</button>}
        {!isCurrent && isUpgrade && (
          <button type="button" className="btn2 btn2--primary btn2--block" onClick={() => onPick(p.id)} disabled={!payReady}>
            Upgrade to {p.name}
          </button>
        )}
      </div>
    </article>
  );
}

export default function Credits() {
  const {
    credits, plan, planExpiresAt, tiersAllowed, creditsError, refreshCredits, pricing, pricingError, refreshPricing,
    tiers, setTopupOpen, setTopupPack, user,
  } = useStore();

  const plans = [...planList(pricing)].sort((a, b) => a.price_paise - b.price_paise);
  const currentRank = Math.max(0, plans.findIndex((x) => x.id === plan));
  const current = plans.find((x) => x.id === plan);
  const payReady = !!(pricing && pricing.payments && pricing.payments.razorpay_configured);
  const packs = (pricing && pricing.packs) || [];
  const maxCost = Math.max(1, ...tiers.map((t) => t.cost || 0));
  const resolutions = resolutionList(pricing);
  const allowed = (t) => !tiersAllowed || tiersAllowed.includes(t);
  const expiry = toMs(planExpiresAt);
  const openPack = (id) => { setTopupPack(id); setTopupOpen(true); };

  return (
    <>
      <PageHeader kicker="05 / PLANS AND CREDITS" title="Plans and credits" sub="Choose a plan, top up credits and see what each video costs. Credits are charged when a job is submitted." />

      {pricing && !payReady && (
        <div className="notice notice--bad live-banner" role="alert">
          <Icon name="alert" size={18} />
          <div><b>Payments are not configured on this server</b><span>Plans and packs are shown for reference; checkout is disabled.</span></div>
        </div>
      )}

      {creditsError && (
        <div className="notice notice--bad live-banner" role="alert">
          <Icon name="alert" size={18} />
          <div><b>Could not load your balance</b><span>{creditsError}</span></div>
          <button type="button" className="btn2 btn2--ghost btn2--sm" onClick={refreshCredits}>Retry</button>
        </div>
      )}

      <section className="pl-plans" aria-labelledby="pl-plans-h">
        <div className="pl-plans-head rise" style={{ '--i': 0 }}>
          <h2 id="pl-plans-h">Plans</h2>
          <p>{plans.length ? 'Each plan unlocks a set of motion tiers and comes with its own credits.' : 'Plans come from the server.'}</p>
        </div>
        {!pricing && pricingError && <ErrorState title="Could not load plans" message={pricingError} onRetry={refreshPricing} />}
        {!pricing && !pricingError && (
          <div className="pl-grid" aria-busy="true" aria-label="Loading plans">
            {[0, 1, 2].map((i) => <Skeleton key={i} h={340} r={10} />)}
          </div>
        )}
        {pricing && (
          <div className="pl-grid">
            {plans.map((p, i) => (
              <PlanCard key={p.id} p={p} index={i} rank={i} currentRank={currentRank} planId={plan} tiers={tiers} pricing={pricing} payReady={payReady} onPick={openPlanDialog} />
            ))}
          </div>
        )}
      </section>

      <div className="cr-grid">
        <section className="balance-card spot-card rise" style={{ '--i': 3 }}>
          <div className="balance-glow" aria-hidden="true" />
          <div className="pl-bal-top">
            <span className="kicker">Available balance</span>
            <span className="pill pl-plan-pill">{current ? current.name : plan} plan</span>
          </div>
          <b className="balance-n">{credits == null ? '—' : <CountUp to={credits} on duration={1000} />}</b>
          <span className="balance-u">credits{expiry ? ` · plan active until ${fmt(expiry).slice(0, 10)}` : ''}</span>
          <div className="can-make">
            {tiers.map((t) => {
              const ok = allowed(t.v);
              return (
                <div key={t.v} className={ok ? '' : 'pl-can-locked'}>
                  {ok
                    ? <b>{credits == null || t.cost == null ? '—' : <CountUp to={Math.floor(credits / t.cost)} on duration={800} />}</b>
                    : <b className="pl-can-lock"><Icon name="lock" size={15} />Locked</b>}
                  <span>{t.label} videos</span>
                </div>
              );
            })}
          </div>
          <button type="button" className="btn2 btn2--primary" onClick={() => setTopupOpen(true)} disabled={!!pricing && !payReady}>
            <Icon name="plus" size={17} />Top up
          </button>
          {user && <span className="fine2">Signed in as {user.email}</span>}
        </section>

        <section className="panel spot-card rise" style={{ '--i': 4 }}>
          <div className="panel-head"><h3>Top-up packs</h3><span className="mono">Razorpay</span></div>
          {!pricing && pricingError && <ErrorState compact title="Could not load packs" message={pricingError} onRetry={refreshPricing} />}
          {!pricing && !pricingError && <div className="live-skel"><Skeleton h={54} /><Skeleton h={54} /><Skeleton h={54} /></div>}
          {pricing && packs.length === 0 && <p className="fine2">No top-up packs are available right now.</p>}
          {pricing && packs.length > 0 && (
            <div className="packs2">
              {packs.map((p) => (
                <button type="button" key={p.id} className="pack3" onClick={() => openPack(p.id)} disabled={!payReady}>
                  <span className="pack3-c"><b>{p.credits}</b> credits</span>
                  <span className="mono pack3-r">₹{(p.price_paise / 100 / p.credits).toFixed(2)} / credit</span>
                  <span className="pack3-p">{formatPrice(p.price_paise)}<Icon name="arrow" size={15} /></span>
                </button>
              ))}
            </div>
          )}
          <p className="fine2">
            {pricing && !payReady
              ? 'Payments are not configured on this server, so top-ups are disabled.'
              : 'Payment is handled by Razorpay Checkout. This app never sees card details.'}
          </p>
        </section>

        <section className="panel spot-card rise cr-wide" style={{ '--i': 5 }}>
          <div className="panel-head"><h3>Cost by tier</h3><span className="mono">cost_by_tier</span></div>
          <div className="cost-rows">
            {tiers.map((t) => {
              const ok = allowed(t.v);
              const need = !ok ? planFor(pricing, t.v) : null;
              return (
                <div key={t.v} className={ok ? '' : 'pl-row-locked'}>
                  <span className="cost-n">
                    <b>{t.label}</b>
                    <em>{t.desc}</em>
                    {!ok && <em className="pl-needs"><Icon name="lock" size={12} />{need ? `${need.name} and above` : 'Higher plan'}</em>}
                  </span>
                  <span className="cost-bar"><i style={{ width: `${t.cost == null ? 0 : (t.cost / maxCost) * 100}%` }} /></span>
                  <b className="mono">{t.cost == null ? '–' : `${t.cost} cr`}</b>
                </div>
              );
            })}
          </div>

          {resolutions.length > 0 && (
            <div className="ra">
              <h4 className="ra-h">Resolution add-ons</h4>
              <table className="ra-table">
                <thead>
                  <tr><th scope="col">Resolution</th><th scope="col">Size</th><th scope="col">Plan</th><th scope="col" className="ra-num">Add-on</th></tr>
                </thead>
                <tbody>
                  {resolutions.map((r) => {
                    const sur = Number(r.credit_surcharge) || 0;
                    const need = planForResolution(pricing, r.id);
                    return (
                      <tr key={r.id}>
                        <th scope="row">{r.label || r.id}</th>
                        <td className="mono">{r.width && r.height ? `${r.width}×${r.height}` : '–'}</td>
                        <td>{need ? `${need.name} and above` : '–'}</td>
                        <td className="ra-num mono">{sur > 0 ? `+${sur} cr` : 'included'}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
              <p className="fine2">Added to the tier cost of each video.</p>
            </div>
          )}
        </section>
      </div>
    </>
  );
}
