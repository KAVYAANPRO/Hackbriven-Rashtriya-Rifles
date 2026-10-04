// Maps a raw API job (see INTEGRATION.md "Job object") to the shape the UI pages use.
import { LANGS } from '../data.js';

// Backend timestamps may be timezone-naive ISO strings (UTC). Date.parse would read those as local time.
export function toMs(v) {
  if (v == null || v === '') return null;
  if (typeof v === 'number') return v;
  const s = String(v);
  const hasZone = /([zZ]|[+-]\d{2}:?\d{2})$/.test(s);
  const t = Date.parse(hasZone || !/\d{2}:\d{2}/.test(s) ? s : s + 'Z');
  return Number.isNaN(t) ? null : t;
}

const STAGE_PREFIX = [
  ['intelligence', 'running_intelligence'],
  ['generation', 'running_generation'],
  ['composition', 'running_composition'],
  ['validation', 'running_validation'],
];

function mapErrorStage(raw, history) {
  if (!raw) return null;
  const s = String(raw).toLowerCase();
  const hit = STAGE_PREFIX.find(([p]) => s === p || s.startsWith(p + '.') || s.startsWith(p + '_'));
  if (hit) return hit[1];
  // Anything else ("pipeline", ...) is blamed on the last stage the job actually entered.
  for (let i = history.length - 1; i >= 0; i -= 1) {
    if (history[i].status.indexOf('running_') === 0) return history[i].status;
  }
  return null;
}

function adaptHistory(list) {
  return (Array.isArray(list) ? list : []).map((h) => {
    const stage = h.stage || '';
    const raw = typeof h.status === 'string' ? h.status : '';
    let status = stage;
    let note = null;
    if (stage === 'input') {
      status = 'queued';
      note = raw && raw !== 'accepted' ? raw : null;
    } else if (/^failed\b/i.test(raw)) {
      status = 'failed';
      note = raw.replace(/^failed:?\s*/i, '') || null;
    } else if (raw && raw !== 'entered') {
      note = raw;
    }
    return { status, at: toMs(h.at), stage, note };
  });
}

export function adaptQuality(q) {
  if (!q || typeof q !== 'object') return null;
  const dur = Number(q.duration_seconds);
  return {
    passed: !!q.passed,
    resolution: q.width && q.height ? `${q.width} × ${q.height}` : '—',
    duration: Number.isFinite(dur) ? `${dur.toFixed(1)} s` : '—',
    audio: q.has_audio_track ? 'Present' : 'Missing',
    reasons: Array.isArray(q.reasons) ? q.reasons : [],
  };
}

const cap = (s) => (s ? s[0].toUpperCase() + s.slice(1) : s);

function adaptNote(api) {
  const n = api.manual_handoff_note;
  if (!n) return null;
  const hook = (api.script && api.script.hook) || (api.scene_plan && api.scene_plan.hook) || '';
  const lang = LANGS.find((l) => l.v === api.language);
  let title = hook.slice(0, 100) || api.topic;
  let caption = hook || api.topic;
  let text = '';
  if (typeof n === 'string') {
    text = n;
  } else if (typeof n === 'object') {
    title = n.title || title;
    caption = n.caption || caption;
    text = typeof n.text === 'string' ? n.text : JSON.stringify(n, null, 2);
  }
  return { title, caption, language: lang ? lang.label : api.language, tier: cap(api.motion_tier), text };
}

export function adaptJob(api) {
  const history = adaptHistory(api.history);
  const status = api.status;
  const planScenes = (api.scene_plan && Array.isArray(api.scene_plan.scenes)) ? api.scene_plan.scenes : [];
  const scriptScenes = (api.script && Array.isArray(api.script.scenes)) ? api.script.scenes : [];
  const quality = adaptQuality(api.quality_report);
  const created = toMs(api.created_at);
  return {
    id: api.id,
    topic: api.topic || '',
    language: api.language,
    tier: api.motion_tier,
    status,
    created,
    updated: toMs(api.updated_at) ?? created,
    history,
    hook: (api.script && api.script.hook) || (api.scene_plan && api.scene_plan.hook) || '',
    mood: (api.script && api.script.mood) || '',
    scenes: planScenes.length,
    planScenes,
    sceneList: scriptScenes.length ? scriptScenes : planScenes,
    live: status === 'queued' || String(status).indexOf('running_') === 0,
    approvedBy: api.approved_by || null,
    approvedAt: toMs(api.approved_at),
    publishedAt: toMs(api.published_at),
    publishError: api.publish_error || null,
    errorStage: status === 'failed' || api.error_stage ? mapErrorStage(api.error_stage, history) : null,
    errorStageRaw: api.error_stage || null,
    errorReason: api.error_reason || null,
    quality,
    note: adaptNote(api),
    hasVideo: !!api.has_video,
    readyScenes: Array.isArray(api.ready_scene_images) ? api.ready_scene_images : [],
    mediaSig: api.media_sig || null,
    style: api.style || null,
    styleText: api.style_prompt || '',
    resolution: api.resolution || null,
    captions: api.captions || null,
    referenceCount: Array.isArray(api.reference_images) ? api.reference_images.length : 0,
    providerEvents: (Array.isArray(api.provider_events) ? api.provider_events : []).map((e) => ({
      stage: e.stage,
      provider: e.provider,
      ok: !!e.ok,
      error: e.error || null,
      at: toMs(e.at),
    })),
    raw: api,
  };
}

export const isTerminalStatus = (s) => !(s === 'queued' || String(s).indexOf('running_') === 0 || s === 'publishing');
