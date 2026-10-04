---
title: Qoneqt Content Engine
emoji: 🎬
colorFrom: indigo
colorTo: pink
sdk: gradio
sdk_version: 6.29.0
app_file: app.py
pinned: false
---

# Qoneqt Content Engine — From Idea to Feed

Deploy this repository as-is to a Hugging Face Space using the native
**Gradio SDK** — no Docker required:

1. Create a new Space, choose SDK = Gradio.
2. Push this repository's contents to the Space's git remote. HF Spaces reads
   three files automatically, no container build needed:
   - `requirements.txt` — Python dependencies (pip installed for you)
   - `packages.txt` — system packages (`ffmpeg`, apt-installed for you)
   - `app.py` — the entrypoint (starts the FastAPI backend on a background
     thread, then launches the Gradio UI in the foreground)
   Copy this file's frontmatter into the Space's own root `README.md` (the
   Space card) if the Space needs it there rather than here.
3. In the Space's **Settings → Repository secrets**, set whichever env vars
   from `.env.example` you have (`GEMINI_API_KEY`, `GROQ_API_KEY`,
   `NVIDIA_API_KEY`, `EIGHTSCALE_API_KEY`, `MAGIC_HOUR_API_KEY`,
   `MONGODB_URI`, `RAZORPAY_KEY_ID`/`RAZORPAY_KEY_SECRET`,
   `BACKEND_API_KEY`, etc. — see `DEPLOYMENT.md` §6 for the full table).
   **None are required to boot** — every stage has a keyless fallback
   (Pollinations images, edge-tts/gTTS voice, local Whisper captions, a
   local template script, Ken Burns motion, SQLite credits). Without
   `MONGODB_URI`, job state and the credits ledger reset on every Space
   restart/redeploy (free Spaces have ephemeral storage) — set it for
   anything beyond a quick demo.
4. Free Spaces sleep when idle — wake it before a live demo.

## Alternative: any plain VM / VPS (also no Docker)

```bash
git clone <this repo>
cd HACKBRIVEN-1
pip install -r requirements.txt
sudo apt-get install -y ffmpeg   # or: brew install ffmpeg / choco install ffmpeg
cp .env.example .env             # fill in keys as available, or leave blank
python app.py                    # backend + Gradio UI, one process, port 7860
```

The `Dockerfile` in the repo root is kept as an optional third path (e.g. for
Render/Fly.io/a container registry) — it is not required for either option
above.

Measured in the original prototype on 1 CPU: ~45s to produce a ~23s video.
