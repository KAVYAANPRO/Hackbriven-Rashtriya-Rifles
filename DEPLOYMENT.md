# DEPLOYMENT.md - IdeaFeed AI

Two parts deploy separately:

| Part | Location | Runs on | Port |
|------|----------|---------|------|
| Frontend (React + Vite) | repo root | any static host (Vercel, Netlify, Cloudflare Pages) | static |
| Backend (FastAPI) | `Backend/hackbriven---test` | Docker (Render, Railway, Fly.io, any VPS) | 8000 |

## 1. Backend (Docker)

The root `Dockerfile` builds the API image (Python 3.11 + ffmpeg).

```bash
docker build -t ideafeed-api .
docker run -p 8000:8000 --env-file Backend/hackbriven---test/.env ideafeed-api
```

Check it: `GET http://localhost:8000/health` returns `{"status":"ok"}`.

On a hosting platform, point it at this repo, choose "Docker", use the root
`Dockerfile`, and set the environment variables below in the platform's
dashboard. `.env` is not in git; never commit it.

### Environment variables

Every provider has a fallback, so the app boots with none of these set, but
quality is lower. Full list: `Backend/hackbriven---test/.env.example`.

- `CLOUDFLARE_ACCOUNT_ID`, `CLOUDFLARE_API_TOKEN` - primary image provider.
- `IMAGE_PROVIDERS` - image order, default `cloudflare,openrouter,nvidia,pollinations`.
- `GEMINI_API_KEY`, `GROQ_API_KEY`, `NVIDIA_API_KEY`, `OPENROUTER_API_KEY` - script, captions, boosts.
- `EIGHTSCALE_API_KEYS`, `MAGIC_HOUR_API_KEYS` - AI motion (comma-separated key pools).
- `MONGODB_URI` - persistent users, jobs and credits (otherwise local SQLite/memory).
- `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET` - credit top-ups.
- `SESSION_SECRET` - set a long random value in production.
- `CORS_ORIGINS` - **must include your deployed frontend URL**, e.g. `https://your-app.vercel.app`.

### Fallback chains

- Images: Cloudflare (account pool) -> OpenRouter -> NVIDIA -> Pollinations -> local placeholder.
- Motion: 8scale (key pool) -> Magic Hour (key pool) -> local Ken Burns zoom.
- Script / prompt boost: Gemini -> Groq -> NVIDIA -> local template.
- Voice: edge-tts -> gTTS. Captions: Groq Whisper -> local Whisper.

## 2. Frontend (static)

```bash
npm install
npm run build        # outputs dist/
```

Set `VITE_API_URL` to the deployed backend URL **at build time**:

```bash
VITE_API_URL=https://your-backend.example.com npm run build
```

On Vercel/Netlify: build command `npm run build`, output directory `dist`,
and add `VITE_API_URL` under environment variables. For client-side routing,
add a rewrite of all paths to `/index.html`.

## 3. Local development

```bash
npm install
npm run api:local    # backend on :8000, no database needed
npm run dev          # frontend on :5173, proxies /api to :8000
```

## 4. Checklist before going live

1. Backend `/health` returns ok.
2. `CORS_ORIGINS` contains the frontend URL.
3. `VITE_API_URL` was set before building the frontend.
4. `SESSION_SECRET` is set and secrets are only in the host's env settings.
5. Storage is persistent (mount a volume at `/app/storage/jobs`) or `MONGODB_URI` is set, otherwise generated videos disappear on restart.
