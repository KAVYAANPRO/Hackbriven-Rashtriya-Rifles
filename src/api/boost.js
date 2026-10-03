// Prompt boost with the user's OWN Gemini key, called straight from the browser (the key never goes to our backend).
// Without a personal key the Create screen uses POST /prompt/boost instead (see api/client.js).

const GEMINI_URL = 'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent';

const INSTRUCTION = [
  'You rewrite rough ideas into prompts for an AI short-video generator.',
  'Rewrite the idea below into a vivid, specific prompt for a vertical short video.',
  'Cover the hook, the subject, the mood, the visual style and the pacing.',
  'Write 2 to 4 sentences, in the SAME language as the idea (keep Hindi in Hindi, Hinglish in Hinglish).',
  'Do not add headings, bullet points, quotes or any commentary.',
  'Return ONLY the rewritten prompt text.',
  '',
  'Idea:',
].join('\n');

function cleanOutput(text) {
  return text
    .trim()
    .replace(/^```[a-z]*\n?|```$/gi, '')
    .trim()
    .replace(/^["“”']+|["“”']+$/g, '')
    .trim();
}

async function boostWithGemini(prompt, apiKey, signal) {
  let res;
  try {
    res = await fetch(GEMINI_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'x-goog-api-key': apiKey },
      body: JSON.stringify({ contents: [{ parts: [{ text: `${INSTRUCTION}\n${prompt}` }] }] }),
      signal,
    });
  } catch (e) {
    if (e && e.name === 'AbortError') throw e;
    throw new Error('Could not reach Gemini. Check your connection and try again.');
  }

  if (!res.ok) {
    if (res.status === 400 || res.status === 403) throw new Error(`Gemini rejected the API key (${res.status}).`);
    if (res.status === 429) throw new Error('Gemini rate limit reached (429). Try again in a minute.');
    throw new Error(`Gemini request failed (${res.status}).`);
  }

  let data;
  try {
    data = await res.json();
  } catch {
    throw new Error('Gemini sent a reply that could not be read.');
  }
  const raw = data?.candidates?.[0]?.content?.parts?.[0]?.text;
  const text = typeof raw === 'string' ? cleanOutput(raw) : '';
  if (!text) throw new Error('Gemini returned an empty answer. Try rephrasing the idea.');
  return text;
}

export async function boostWithKey(prompt, apiKey, { signal } = {}) {
  const clean = (prompt || '').trim();
  if (!clean) throw new Error('Write an idea first.');
  const text = await boostWithGemini(clean, (apiKey || '').trim(), signal);
  return { text, source: 'gemini' };
}
