import { useEffect, useMemo, useRef } from 'react';
import {
  LANGS, RES_NOTE, STYLE_PROMPT_MAX, planFor, planForResolution, resolutionList, resolutionOf, resolutionSurcharge,
  styleLabel, styleList, styleSwatch,
} from '../../data.js';
import { useStore } from '../../store.jsx';
import { useTheme } from '../../theme.js';
import { Seg, Skeleton } from '../common.jsx';
import Icon from '../Icon.jsx';
import ShapeGrid from '../ShapeGrid.jsx';
import StyleArt from './StyleArt.jsx';
import ImageDrop from './ImageDrop.jsx';
import { GRID_COLORS } from './PromptStep.jsx';
import CaptionControls from '../CaptionControls.jsx';

// Group the style list by style.group, keeping the server's order (a group sits where its first style is).
function groupStyles(list) {
  const groups = [];
  list.forEach((st) => {
    const name = st.group || '';
    let g = groups.find((x) => x.name === name);
    if (!g) { g = { name, items: [] }; groups.push(g); }
    g.items.push(st);
  });
  return groups;
}

function StylePicker({ styles, value, onChange }) {
  const ref = useRef(null);
  const groups = useMemo(() => groupStyles(styles), [styles]);
  const flat = useMemo(() => groups.flatMap((g) => g.items), [groups]);
  const focusId = flat.some((x) => x.id === value) ? value : (flat[0] || {}).id;

  // Radio-group keyboard model: arrows move the selection, Tab leaves the group.
  const onKeyDown = (e) => {
    const keys = ['ArrowRight', 'ArrowDown', 'ArrowLeft', 'ArrowUp', 'Home', 'End'];
    if (!keys.includes(e.key) || !flat.length) return;
    e.preventDefault();
    const cur = document.activeElement && document.activeElement.dataset ? document.activeElement.dataset.sid : null;
    const i = Math.max(0, flat.findIndex((x) => x.id === cur));
    let n = i;
    if (e.key === 'ArrowRight' || e.key === 'ArrowDown') n = (i + 1) % flat.length;
    else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') n = (i - 1 + flat.length) % flat.length;
    else if (e.key === 'Home') n = 0;
    else n = flat.length - 1;
    onChange(flat[n].id);
    const el = ref.current && Array.from(ref.current.querySelectorAll('[data-sid]')).find((b) => b.dataset.sid === flat[n].id);
    if (el) el.focus();
  };

  return (
    <div className="cx-styles" role="radiogroup" aria-labelledby="cx-style-l" ref={ref} onKeyDown={onKeyDown}>
      {groups.map((g) => (
        <div key={g.name || '_'} className="cx-style-group" role="presentation">
          {g.name && <span className="cx-style-gh mono" aria-hidden="true">{g.name}</span>}
          <div className="cx-style-grid" role="presentation">
            {g.items.map((st) => {
              const on = value === st.id;
              return (
                <button
                  key={st.id}
                  type="button"
                  role="radio"
                  aria-checked={on}
                  data-sid={st.id}
                  tabIndex={st.id === focusId ? 0 : -1}
                  className={'cx-style' + (on ? ' is-on' : '')}
                  onClick={() => onChange(st.id)}
                >
                  <StyleArt id={st.id} fallback={styleSwatch(st.id)} />
                  <span className="cx-style-name">{st.label || st.id}</span>
                  {st.description && <span className="cx-style-desc">{st.description}</span>}
                  {on && <span className="cx-style-mark" aria-hidden="true"><Icon name="check" size={12} /></span>}
                </button>
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
}

export default function OptionsStep({ onEdit, images }) {
  const {
    topic, lang, setLang, tier, setTier, tiers, tiersAllowed, pricing, pricingError, credits, generate, gen, clearGenError,
    setTopupOpen, go, style, setStyle, styleText, setStyleText, resolution, setResolution, resolutionsAllowed,
    providers, refreshProviders, captions, setCaptions,
  } = useStore();
  const headRef = useRef(null);
  const [theme] = useTheme();
  const gridColors = GRID_COLORS[theme] || GRID_COLORS.dark;

  // Re-check the image provider each time this step opens, so a used-up daily allowance is shown up front.
  useEffect(() => { refreshProviders(); }, [refreshProviders]);
  const quotaUntil = providers && providers.image && providers.image.quota_exhausted_until
    ? new Date(providers.image.quota_exhausted_until) : null;

  const styles = styleList(pricing);
  const resolutions = resolutionList(pricing);
  const pricingWait = !pricing && !pricingError;
  const customStyle = styles.length > 0 && style === 'custom';
  const customEmpty = customStyle && !styleText.trim();
  const isResAllowed = (id) => !resolutionsAllowed || resolutionsAllowed.includes(id);
  const surcharge = resolutions.length ? resolutionSurcharge(pricing, resolution) : 0;
  const resPicked = resolutionOf(pricing, resolution);

  const isAllowed = (t) => !tiersAllowed || tiersAllowed.includes(t);
  const firstAllowed = (tiers.find((t) => isAllowed(t.v)) || tiers[0] || { v: 'basic' }).v;
  const allowed = isAllowed(tier);
  const effTier = allowed ? tier : firstAllowed;
  const picked = tiers.find((t) => t.v === effTier) || tiers[0];
  const tierCost = picked ? picked.cost : null;
  const cost = tierCost == null ? null : tierCost + surcharge;
  const short = credits != null && cost != null && credits < cost;
  const empty = !topic.trim();
  const anyLocked = tiers.some((t) => !isAllowed(t.v));
  const langLabel = (LANGS.find((l) => l.v === lang) || LANGS[0]).label;
  const tierLabel = picked ? picked.label : effTier;
  const busy = gen.busy;

  // The chosen tier must always be one the plan can run.
  useEffect(() => {
    if (tiersAllowed && !tiersAllowed.includes(tier) && tiersAllowed.length) setTier(firstAllowed);
  }, [tiersAllowed, tier, setTier, firstAllowed]);

  useEffect(() => {
    if (headRef.current) headRef.current.focus({ preventScroll: true });
  }, []);

  const blocked = empty || short || !allowed || busy || customEmpty;
  const submit = () => {
    if (blocked) return;
    generate({ files: images.files.map((f) => f.file) });
  };

  const ins = gen.insufficient;
  const forb = gen.forbidden;

  return (
    <section className="cx-opts" aria-labelledby="cx-opts-title">
      <div className="cx-opts-bg" aria-hidden="true">
        <ShapeGrid
          direction="diagonal"
          speed={0.4}
          squareSize={40}
          shape="square"
          borderColor={gridColors.border}
          hoverFillColor={gridColors.fill}
          hoverTrailAmount={6}
        />
      </div>
      <header className="cx-opts-head">
        <h1 id="cx-opts-title" className="cx-opts-title" tabIndex={-1} ref={headRef}>Set up your video</h1>
      </header>

      {quotaUntil && (
        <div className="notice notice--bad" role="status">
          <Icon name="alert" size={18} />
          <div>
            <b>Today&apos;s AI image limit has been reached</b>
            <span>
              {providers.image.chain && providers.image.chain.includes('pollinations')
                ? 'New videos will use a lower-quality backup image service until the limit resets at '
                : 'New videos will use simple title cards instead of AI images until the limit resets at '}
              {quotaUntil.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}. Reference images you upload are still used.
            </span>
          </div>
        </div>
      )}

      <div className="cx-recap">
        <div className="cx-recap-body">
          <span className="cx-label">Your idea</span>
          <p className="cx-recap-text">{topic}</p>
        </div>
        <button type="button" className="btn2 btn2--ghost btn2--sm" onClick={onEdit} disabled={busy}>
          <Icon name="back" size={14} />
          Edit
        </button>
      </div>

      <section className="panel spot-card cx-panel">
        <div className="field2">
          <div className="field2-head"><label id="cx-lang-l">Language</label></div>
          <Seg label="Language" options={LANGS.map((l) => ({ v: l.v, label: l.label, sub: l.code }))} value={lang} onChange={setLang} />
        </div>
      </section>

      <section className="panel spot-card cx-panel">
        <div className="field2">
          <div className="field2-head">
            <label id="cx-tier-l">Motion effort</label>
            {anyLocked && (
              <button type="button" className="link-btn" onClick={() => go('credits')}>Upgrade to unlock more</button>
            )}
          </div>
          <div className="cx-tiers" role="radiogroup" aria-labelledby="cx-tier-l">
            {tiers.map((t) => {
              const ok = isAllowed(t.v);
              const on = ok && effTier === t.v;
              const need = !ok ? planFor(pricing, t.v) : null;
              return (
                <button
                  key={t.v}
                  type="button"
                  role="radio"
                  aria-checked={on}
                  disabled={!ok}
                  className={'cx-tier' + (on ? ' is-on' : '') + (ok ? '' : ' is-locked')}
                  onClick={() => setTier(t.v)}
                >
                  <span className="cx-tier-mark" aria-hidden="true">
                    {on ? <Icon name="check" size={12} /> : !ok ? <Icon name="lock" size={12} /> : null}
                  </span>
                  <span className="cx-tier-name">{t.label}</span>
                  <span className="cx-tier-cost"><b>{t.cost == null ? '–' : t.cost}</b> credits</span>
                  <span className="cx-tier-desc">{t.desc}</span>
                  {!ok && <span className="cx-tier-lock">Needs {need ? need.name : 'a paid plan'}</span>}
                </button>
              );
            })}
          </div>
        </div>
      </section>

      {pricingWait && (
        <section className="panel spot-card cx-panel" aria-busy="true" aria-label="Loading style and resolution options">
          <Skeleton h={14} w={80} />
          <div className="cx-style-grid">{[0, 1, 2, 3].map((i) => <Skeleton key={i} h={96} r={8} />)}</div>
        </section>
      )}

      {styles.length > 0 && (
        <section className="panel spot-card cx-panel">
          <div className="field2">
            <div className="field2-head">
              <label id="cx-style-l">Style</label>
              <span className="mono">{styleLabel(pricing, style)}</span>
            </div>
            <StylePicker styles={styles} value={style} onChange={setStyle} />
            {customStyle && (
              <div className="cx-custom">
                <label htmlFor="cx-style-text" className="cx-label">Describe your style</label>
                <textarea
                  id="cx-style-text"
                  className="textarea2 cx-custom-ta"
                  rows={3}
                  maxLength={STYLE_PROMPT_MAX}
                  placeholder="For example: hand-drawn paper cutouts, warm pastel palette, slow gentle camera moves"
                  value={styleText}
                  disabled={busy}
                  aria-describedby="cx-style-count"
                  onChange={(e) => setStyleText(e.target.value)}
                />
                <span id="cx-style-count" className={'cx-count mono' + (customEmpty ? ' is-warn' : '')}>
                  {customEmpty ? 'Required for the custom style · ' : ''}{styleText.length}/{STYLE_PROMPT_MAX}
                </span>
              </div>
            )}
          </div>
        </section>
      )}

      {resolutions.length > 0 && (
        <section className="panel spot-card cx-panel">
          <div className="field2">
            <div className="field2-head">
              <label id="cx-res-l">Resolution</label>
              {resolutions.some((r) => !isResAllowed(r.id)) && (
                <button type="button" className="link-btn" onClick={() => go('credits')}>Upgrade to unlock more</button>
              )}
            </div>
            <Seg
              label="Resolution"
              value={resolution}
              onChange={setResolution}
              options={resolutions.map((r) => {
                const ok = isResAllowed(r.id);
                const need = !ok ? planForResolution(pricing, r.id) : null;
                const extra = Number(r.credit_surcharge) > 0 ? `+${r.credit_surcharge} credits` : '';
                return {
                  v: r.id,
                  label: r.label || r.id,
                  sub: r.width && r.height ? `${r.width}×${r.height}` : '',
                  note: !ok ? `Needs ${need ? need.name : 'a paid plan'}` : extra,
                  disabled: !ok,
                };
              })}
            />
            {resPicked && (
              <p className="fine2">
                {resPicked.label || resPicked.id}{RES_NOTE[resPicked.id] ? ` · ${RES_NOTE[resPicked.id]}` : ''}
                {resPicked.width && resPicked.height ? ` · ${resPicked.width}×${resPicked.height}` : ''}
                {surcharge > 0 ? ` · adds ${surcharge} credits to each video` : ''}
              </p>
            )}
          </div>
        </section>
      )}

      <section className="panel spot-card cx-panel">
        <div className="field2">
          <CaptionControls value={captions} onChange={setCaptions} disabled={busy} />
        </div>
      </section>

      <section className="panel spot-card cx-panel">
        <div className="field2">
          <div className="field2-head">
            <label>Reference images</label>
            <span className="mono">optional</span>
          </div>
          <ImageDrop files={images.files} errors={images.errors} onAdd={images.add} onRemove={images.remove} />
          <p className="fine2">Your images become the visuals of the first scenes, in order; remaining scenes are AI-generated.</p>
        </div>
      </section>

      <section className="panel spot-card cx-panel cx-go">
        <dl className="cx-sum">
          <div><dt>Language</dt><dd>{langLabel}</dd></div>
          <div><dt>Motion</dt><dd>{tierLabel}</dd></div>
          {styles.length > 0 && <div><dt>Style</dt><dd>{styleLabel(pricing, style)}</dd></div>}
          {resolutions.length > 0 && (
            <div><dt>Resolution</dt><dd>{resPicked ? (resPicked.label || resPicked.id) : resolution}</dd></div>
          )}
          <div><dt>Captions</dt><dd>{captions.enabled ? `${captions.size}${captions.language !== 'same' ? ` · ${captions.language}` : ''}` : 'Off'}</dd></div>
          <div><dt>Images</dt><dd>{images.files.length === 0 ? 'None' : images.files.length}</dd></div>
          <div>
            <dt>Cost</dt>
            <dd className="mono">
              {cost == null ? '–' : `${cost} credits`}
              {cost != null && surcharge > 0 && <span className="cx-sum-sub">{tierCost} {tierLabel} + {surcharge} resolution</span>}
            </dd>
          </div>
          <div><dt>Balance after</dt><dd className="mono">{credits == null || cost == null || short ? '–' : `${credits - cost} credits`}</dd></div>
        </dl>

        {(short || ins) && (
          <div className="notice notice--bad" role="alert">
            <Icon name="alert" size={18} />
            <div>
              <b>Not enough credits</b>
              <span className="mono">
                needs {ins && ins.required != null ? ins.required : cost} · you have {ins && ins.available != null ? ins.available : credits}
              </span>
            </div>
            <button type="button" className="btn2 btn2--primary btn2--sm" onClick={() => { clearGenError(); setTopupOpen(true); }}>Top up</button>
          </div>
        )}

        {forb && (
          <div className="notice notice--bad" role="alert">
            <Icon name="lock" size={18} />
            <div>
              <b>{forb.message}</b>
              {forb.requiredPlan && <span className="mono">requires the {forb.requiredPlan} plan</span>}
            </div>
            <button type="button" className="btn2 btn2--primary btn2--sm" onClick={() => go('credits')}>See plans</button>
          </div>
        )}

        {gen.error && (
          <div className="notice notice--bad" role="alert">
            <Icon name="alert" size={18} />
            <div><b>Could not start the job</b><span>{gen.error}</span></div>
          </div>
        )}

        {customEmpty && <p className="fine2" role="status">Describe your custom style above, or pick another style, to continue.</p>}

        <button type="button" className="btn2 btn2--primary btn2--lg btn2--block" disabled={blocked} onClick={submit}>
          {busy
            ? <><i className="spin" />{gen.phase === 'uploading' ? 'Uploading images…' : 'Starting job…'}</>
            : <><Icon name="bolt" size={18} />Generate video{cost != null && <span className="btn2-tag">{cost} cr</span>}</>}
        </button>
      </section>
    </section>
  );
}
