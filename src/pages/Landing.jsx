import { useRef } from 'react';
import { useStore } from '../store.jsx';
import { LogoMark } from '../components/Logo.jsx';
import { useDeck } from '../components/deck/useDeck.js';
import { CountUp, TierChart, Words } from '../components/deck/parts.jsx';
import Globe from '../components/deck/Globe.jsx';

const SLIDE_COUNT = 5;

export default function Landing() {
  const { authed, go, tiers, pricing } = useStore();
  const { active, progress, wrapRef } = useDeck(SLIDE_COUNT);
  const start = () => go(authed ? 'create' : 'login');
  const cta = authed ? 'Open app' : 'Sign in to start';
  const costs = tiers.filter((t) => t.cost != null).map((t) => t.cost);
  const creditsHead = costs.length
    ? `Pay per video, by motion tier, from ${Math.min(...costs)} ${Math.min(...costs) === 1 ? 'credit' : 'credits'} to ${Math.max(...costs)} credits`
    : 'Pay per video, by motion tier';
  // Plan names come from the server; until they load the sentence just talks about credits.
  const planNames = ((pricing && pricing.plans) || []).map((p) => p.name);
  const plansBody = planNames.length > 1
    ? `Choose ${planNames.join(', ').replace(/, ([^,]*)$/, ' or $1')}: higher plans unlock every motion tier. Credits are charged when a job is submitted. Top up through Razorpay Checkout; card details never reach this app.`
    : 'Credits are charged when a job is submitted. Top up through Razorpay Checkout; card details never reach this app.';
  const cls = (i, extra = '') => `slide ${extra}${active === i ? ' is-active' : ''}`;

  const spot = useRef(null);
  const raf = useRef(0);
  const onMove = (e) => {
    const r = e.currentTarget.getBoundingClientRect();
    const x = e.clientX - r.left;
    const y = e.clientY - r.top;
    if (raf.current) return;
    raf.current = requestAnimationFrame(() => {
      raf.current = 0;
      if (spot.current) spot.current.style.transform = `translate3d(${x}px, ${y}px, 0)`;
    });
  };

  return (
    <div className="deck" ref={wrapRef} data-s={active}>
      <div className="stage">
        {/* light and reflection that bleed out of the card, one set per colour mood */}
        <div className="glow glow--cream"><i className="glow-top" /><i className="floor" /></div>
        <div className="glow glow--blue"><i className="glow-top" /><i className="floor" /></div>
        <div className="glow glow--lime"><i className="glow-top" /><i className="floor" /></div>

        <div className="card" onMouseMove={onMove}>
          <div className="backdrops" aria-hidden="true">
            <div className="bd bd--bars"><i /><i /></div>
            <div className="bd bd--slab"><i className="slab" /><i className="ridge-edge" /><i className="ridge" /></div>
            <div className="bd bd--ring"><i className="ring ring--a" /><i className="ring ring--b" /></div>
            <div className="bd bd--globe"><Globe active={active === 4} progress={progress} /></div>
          </div>
          <div className="scan" aria-hidden="true" />
          <div className="spot" ref={spot} aria-hidden="true" />

          <header className="card-head">
            <div className="logo"><LogoMark size={26} />IdeaFeed AI</div>
            <span className="num" key={active}>{String(active + 1).padStart(2, '0')}</span>
          </header>
          <div className="card-rule" />

          {/* 01 — intro */}
          <section className={cls(0, 'slide--hero')} style={{ '--idx': 0 }}>
            <div className="copy copy--hero">
              <div className="label">AI short-video pipeline</div>
              <h1 className="headline headline--hero"><Words text="One idea. One reviewed video." /></h1>
              <p className="body"><Words text="Type a topic in English, हिन्दी or Hinglish. Script, images, voice, captions and motion are produced in five stages, and you approve the result before it is handed off." start={6} /></p>
              <div className="cta-row">
                <button type="button" className="cta" onClick={start}>{cta}<span aria-hidden="true">→</span></button>
                <span className="hint">Scroll<i /></span>
              </div>
            </div>
          </section>

          {/* 02 — how it works */}
          <section className={cls(1)} style={{ '--idx': 1 }}>
            <div className="copy">
              <div className="label">How it works</div>
              <h2 className="headline"><Words text="From a single topic, IdeaFeed writes the script, creates images, voice and captions, and composes the video" /></h2>
            </div>
            <div className="stats3">
              <div><b><CountUp to={5} on={active === 1} /></b><span>Pipeline stages, tracked live</span></div>
              <div><b><CountUp to={3} on={active === 1} /></b><span>Languages: English, हिन्दी, Hinglish</span></div>
              <div><b><CountUp to={0} on={active === 1} /></b><span>Videos published without your approval</span></div>
            </div>
          </section>

          {/* 03 — credits by tier */}
          <section className={cls(2)} style={{ '--idx': 2 }}>
            <div className="copy copy--narrow">
              <div className="label">Plans and Credits</div>
              <h2 className="headline"><Words text={creditsHead} /></h2>
              <p className="body"><Words text={plansBody} start={11} /></p>
            </div>
            <TierChart on={active === 2} tiers={tiers} />
          </section>

          {/* 04 — provider chains */}
          <section className={cls(3)} style={{ '--idx': 3 }}>
            <div className="copy copy--mid">
              <div className="label">AI orchestra</div>
              <h2 className="headline"><Words text="Every stage tries its providers in order, and when one fails the next takes over" /></h2>
              <p className="body"><Words text="Script, image, voice, captions and motion each run a provider chain. A failed provider reroutes to the next one without restarting the job, so the work keeps going." start={14} /></p>
            </div>
          </section>

          {/* 05 — languages and handoff */}
          <section className={cls(4, 'slide--globe')} style={{ '--idx': 4 }}>
            <div className="copy copy--low">
              <div className="label">Review and handoff</div>
              <h2 className="headline"><Words text="One topic, three languages, ready to hand off" /></h2>
              <p className="body"><Words text="You approve with your name or email, and the handoff package carries the title, caption, language and tier. Nothing is published without approval." start={9} /></p>
            </div>
            <button type="button" className="cta cta--corner" onClick={start}>Start with one topic<span aria-hidden="true">→</span></button>
          </section>

        </div>
      </div>

    </div>
  );
}
