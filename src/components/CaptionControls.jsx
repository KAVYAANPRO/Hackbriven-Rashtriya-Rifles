import { Seg } from './common.jsx';

export const DEFAULT_CAPTIONS = { enabled: true, size: 'medium', color: '#FFFFFF', highlight: '#FFFF00', language: 'same' };

const TEXT_COLORS = ['#FFFFFF', '#FFE14D', '#00E5FF', '#B8F36B', '#FF8FB1', '#111111'];
const HIGHLIGHT_COLORS = ['#FFFF00', '#FF3B30', '#00E5FF', '#B8F36B', '#FF9500', '#FFFFFF'];
const SIZES = [{ v: 'small', label: 'Small' }, { v: 'medium', label: 'Medium' }, { v: 'large', label: 'Large' }];
const LANGS = [
  { v: 'same', label: 'Same as voice' },
  { v: 'en', label: 'English' },
  { v: 'hi', label: 'हिन्दी' },
  { v: 'hinglish', label: 'Hinglish' },
];
const SAMPLE = {
  same: ['Your', 'caption', 'looks', 'like', 'this'],
  en: ['Your', 'caption', 'looks', 'like', 'this'],
  hi: ['आपका', 'कैप्शन', 'ऐसा', 'दिखेगा'],
  hinglish: ['Aapka', 'caption', 'aisa', 'dikhega'],
};
const PREVIEW_PX = { small: 15, medium: 19, large: 24 };

export function normalizeCaptions(c) {
  return { ...DEFAULT_CAPTIONS, ...(c && typeof c === 'object' ? c : {}) };
}

function Swatches({ label, colors, value, onChange, disabled }) {
  return (
    <div className="capx-sw" role="radiogroup" aria-label={label}>
      {colors.map((c) => (
        <button
          key={c}
          type="button"
          role="radio"
          aria-checked={value.toUpperCase() === c}
          aria-label={c}
          title={c}
          disabled={disabled}
          className={'capx-dot' + (value.toUpperCase() === c ? ' is-on' : '')}
          style={{ '--c': c }}
          onClick={() => onChange(c)}
        />
      ))}
      <label className="capx-dot capx-dot--pick" title="Custom colour">
        <input type="color" value={value} disabled={disabled} aria-label={`${label}: custom`} onChange={(e) => onChange(e.target.value.toUpperCase())} />
      </label>
    </div>
  );
}

export default function CaptionControls({ value, onChange, disabled = false }) {
  const v = normalizeCaptions(value);
  const set = (patch) => onChange({ ...v, ...patch });
  const words = SAMPLE[v.language] || SAMPLE.same;
  const off = !v.enabled;

  return (
    <div className="capx">
      <div className="capx-row">
        <span className="cx-label">Captions</span>
        <Seg label="Captions" size="sm" options={[{ v: 'on', label: 'On' }, { v: 'off', label: 'Off' }]} value={off ? 'off' : 'on'} onChange={(x) => set({ enabled: x === 'on' })} />
      </div>

      <fieldset className="capx-body" disabled={disabled || off} aria-disabled={off}>
        <div className="capx-preview" aria-hidden="true" style={{ '--fs': `${PREVIEW_PX[v.size]}px`, color: v.color }}>
          {words.map((w, i) => (
            <span key={i} style={i === 1 ? { color: v.highlight } : undefined}>{w}</span>
          ))}
        </div>
        <div className="capx-row">
          <span className="cx-label">Size</span>
          <Seg label="Caption size" size="sm" options={SIZES} value={v.size} onChange={(size) => set({ size })} />
        </div>
        <div className="capx-row">
          <span className="cx-label">Text colour</span>
          <Swatches label="Caption text colour" colors={TEXT_COLORS} value={v.color} onChange={(color) => set({ color })} disabled={disabled || off} />
        </div>
        <div className="capx-row">
          <span className="cx-label">Highlight</span>
          <Swatches label="Spoken word highlight colour" colors={HIGHLIGHT_COLORS} value={v.highlight} onChange={(highlight) => set({ highlight })} disabled={disabled || off} />
        </div>
        <div className="capx-row capx-row--wrap">
          <span className="cx-label">Language</span>
          <Seg label="Caption language" size="sm" options={LANGS} value={v.language} onChange={(language) => set({ language })} />
        </div>
        <p className="fine2">
          {v.language === 'same'
            ? 'Captions show the exact spoken words, timed word by word.'
            : 'Captions are translated; the voice stays in the video’s language.'}
        </p>
      </fieldset>
    </div>
  );
}
