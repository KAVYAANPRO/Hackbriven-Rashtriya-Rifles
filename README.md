# IdeaFeed AI — Presentation Intelligence Platform

> **Transform any idea into a polished, data-driven deck in seconds.**  
> Built for Hackbriven × Rashtriya Rifles Innovation Challenge

[![React](https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=white)](https://react.dev)
[![Vite](https://img.shields.io/badge/Vite-8-646CFF?logo=vite&logoColor=white)](https://vitejs.dev)
[![FastAPI](https://img.shields.io/badge/FastAPI-Python-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

---

## What is IdeaFeed AI?

IdeaFeed AI is an intelligent presentation generation platform that converts raw ideas, brief descriptions, or reference documents into structured, visually compelling slide decks — powered by a custom FastAPI backend with LLM-driven generation pipelines.

Users can:
- **Generate** — Describe an idea in plain language; the AI produces a full slide deck.
- **Adapt** — Upload a reference document; the AI restructures it into a presentation.
- **Boost** — Enrich an existing draft with data, statistics, and visual suggestions.
- **Export** — Download as PDF, PPTX, PNG sheets, or share via a public link.

---

## Live Demo

> *Demo available at:* [ideafeed.ai](https://ideafeed.ai) *(coming soon)*

---

## Screenshots

### Landing Page
![IdeaFeed AI Landing](design/uploads/palette%20(2).png)

### AI Deck Generation Flow
The three-step wizard walks users through prompt input → style selection → preview & export.

### Analytics Dashboard
Real-time credit usage, generation history, and deck performance metrics.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Frontend** | React 19, Vite 8, CSS custom properties |
| **State** | React Context API + custom hooks |
| **Backend** | FastAPI (Python), async REST API |
| **Payments** | Razorpay (INR, UPI, cards) |
| **Deployment** | Vercel (frontend), Railway (backend) |

---

## Project Structure

```
src/
├── api/               # Backend API adapters (adapt, boost, client, razorpay)
├── components/
│   ├── ui/            # Reusable UI components (Button, Modal, Toast, ...)
│   ├── create/        # Deck creation wizard steps
│   └── deck/          # Slide viewer and globe visualization
├── context/           # React context providers (Auth, Theme, Jobs, Credits)
├── constants/         # App-wide constants (API, routes, plans, jobs)
├── hooks/             # Custom React hooks (30+ hooks)
├── pages/             # Route-level page components
├── styles/            # CSS design system (variables, components, animations)
└── utils/             # Utility functions (format, validate, download, ...)
```

---

## Getting Started

### Prerequisites

- Node.js 20+
- Python 3.11+

### Frontend Setup

```bash
# Clone the repository
git clone https://github.com/KAVYAANPRO/Hackbriven-Rashtriya-Rifles.git
cd Hackbriven-Rashtriya-Rifles

# Install dependencies
npm install

# Copy environment variables
cp .env.example .env
# Edit .env with your values

# Start the development server
npm run dev
```

### Backend Setup

```bash
# The backend lives in a separate repository
# Clone and set up the FastAPI backend, then:
npm run api
```

The frontend dev server runs on `http://localhost:5173` and proxies `/api` requests to the FastAPI backend at `http://localhost:8000`.

---

## Environment Variables

| Variable | Description |
|----------|-------------|
| `VITE_API_BASE` | FastAPI backend URL |
| `VITE_RAZORPAY_KEY` | Razorpay public key (test or live) |
| `VITE_ENABLE_ORCHESTRA` | Feature flag for multi-agent mode |
| `VITE_ENABLE_ANALYTICS` | Feature flag for analytics page |

---

## Features

### Core Generation Modes

| Mode | Credits | Description |
|------|---------|-------------|
| Generate | 2 | Plain-text prompt → full deck |
| Adapt | 3 | PDF/DOCX input → restructured deck |
| Boost | 1 | Add data + stats to an existing draft |

### Credit System

IdeaFeed uses a credit-based model. Credits are consumed per generation. Plans available:

- **Free** — 5 credits/month
- **Starter** — 50 credits/month (₹299)
- **Pro** — 200 credits/month (₹799)
- **Enterprise** — Unlimited (custom pricing)

### Export Formats

- PDF (print-ready, A4 or 16:9)
- PPTX (editable PowerPoint)
- PNG sheet (all slides as a single image)
- Public share link

---

## Architecture Overview

```
Browser
  │
  └── React App (Vite)
        ├── Context Providers (Auth, Theme, Credits, Jobs, Notifications)
        ├── Pages (Landing, Create, Jobs, Analytics, Settings, Credits)
        ├── UI Components (30+ reusable components)
        └── API Layer
              │
              └── FastAPI Backend
                    ├── /auth  — JWT-based login
                    ├── /generate — LLM deck pipeline
                    ├── /jobs — async job queue
                    ├── /analytics — usage metrics
                    └── /credits — billing + Razorpay
```

---

## Custom Hooks

30+ custom hooks including:

| Hook | Purpose |
|------|---------|
| `useAsync` | Loading/error state for async ops |
| `usePolling` | Auto-poll job status |
| `useCredits` | Credit balance management |
| `useLocalStorage` | Persistent state |
| `useDebounce` | Debounced inputs |
| `useMediaQuery` | Responsive breakpoints |
| `useFocusTrap` | Accessible modal trapping |
| `useSearch` | Client-side filtering |
| `usePagination` | Page navigation |
| `useIntersection` | Lazy-load triggers |

---

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feat/your-feature`
3. Commit your changes following the existing message style
4. Push and open a Pull Request

---

## Team

Built by **KAVYAANPRO** for the **Hackbriven × Rashtriya Rifles Innovation Challenge**.

---

## License

MIT © 2024 KAVYAANPRO
