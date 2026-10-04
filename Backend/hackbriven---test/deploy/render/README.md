# Deploy to Render

This repo's existing `Dockerfile` (repo root) deploys to Render as-is — no
Render-specific files needed beyond this guide.

1. **New Web Service** on Render → connect this GitHub repo.
2. **Environment**: Render auto-detects the root `Dockerfile` (or select
   "Docker" explicitly if asked). No build/start command needed — the
   Dockerfile's `CMD ["python", "app.py"]` is used as-is.
3. **Instance type**: the free tier works for a demo (spins down after 15
   minutes idle, same tradeoff as a free HF Space — wake it before you
   present). A paid instance avoids the cold start and gives the pipeline
   more CPU for ffmpeg/image generation.
4. **Environment variables**: under the service's **Environment** tab, add
   whichever of these you have (see `DEPLOYMENT.md` §6 for the full table):
   `GEMINI_API_KEY`, `GROQ_API_KEY`, `NVIDIA_API_KEY`, `EIGHTSCALE_API_KEY`,
   `MAGIC_HOUR_API_KEY`, `MONGODB_URI`, `MONGODB_DB_NAME`, `RAZORPAY_KEY_ID`,
   `RAZORPAY_KEY_SECRET`, `BACKEND_API_KEY`. **None are required to boot** —
   every stage has a keyless fallback. Without `MONGODB_URI`, job state and
   the credits ledger reset on every redeploy (Render's filesystem is
   ephemeral by default, same as a free HF Space) — set it for anything
   beyond a quick demo.
5. Render injects its own `PORT` env var and routes traffic to whatever
   port the container listens on — `app.py` reads `$PORT` for the Gradio
   UI (falls back to 7860 if unset, e.g. for local Docker runs or HF
   Spaces). **Do not set `PORT` yourself** — Render manages it.
6. Deploy. First build installs `ffmpeg` (apt, via the Dockerfile) and all
   Python deps — expect a few minutes for the first build.

## Why Render instead of / in addition to Hugging Face Spaces

Both work from the same codebase with zero code forking — `app.py` already
bundles the FastAPI backend and the Gradio frontend into one process either
way. Render gives you a normal Docker deploy with your own domain and more
predictable resource limits; a free HF Space is simpler to spin up for a
pure demo but sleeps the same way. Pick whichever the judges will actually
visit, or run both — they don't conflict.
