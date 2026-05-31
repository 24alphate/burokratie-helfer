# Deploy — prove the loop live (free tier, EU region)

Goal: a public URL where a real person can complete the KG1 flow. The KG1 path
is **stateless and needs no database, no OCR, and no AI key** — so the deploy is
just one FastAPI container + the existing Vercel frontend.

> Why this is cheap: `process-pdf` and `fill-pdf` never touch the DB; KG1
> fingerprints to Level 1 (verified template), so OCR is skipped and Groq is
> never called (`ai_calls_made=0`). Mocks are fine for everything except the
> actual fill, which uses PyMuPDF (already in `requirements.txt`).

---

## 1. Backend → Render (Frankfurt) or Fly.io (`fra`)

Both have an EU region (needed for DSGVO) and a usable free tier. The repo
already has [backend/Dockerfile](../burokratie-helfer/backend/Dockerfile) and
[backend/start.sh](../burokratie-helfer/backend/start.sh) (honors `$PORT`).

### Render (simplest)
1. New → **Web Service** → connect this repo → root directory `backend`.
2. Runtime **Docker**. Region **Frankfurt (EU Central)**.
3. Instance type **Free**.
4. Add the environment variables below.
5. Deploy. Note the URL, e.g. `https://burokratie-helfer.onrender.com`.

### Required environment variables

| Variable | Value | Why |
|---|---|---|
| `SECRET_KEY` | a fixed 32-byte hex string (generate once, keep it) | **Critical.** Signs the PDF token. If unset, [config.py](../burokratie-helfer/backend/app/config.py) regenerates it per process, so every cold start invalidates all 4 h tokens and users get "session expired". |
| `OCR_BACKEND` | `mock` | KG1 doesn't need OCR. |
| `TRANSLATION_BACKEND` | `mock` | KG1 is verified → no AI translation. |
| `GROQ_API_KEY` | *(optional)* free-tier key | Only needed so non-KG1 Level-2/3 forms also get translated. Not required to prove the KG1 loop. |

Generate a secret key: `python -c "import os; print(os.urandom(32).hex())"`.

> CORS: `main.py` currently allows all origins (`*`, no credentials), so the
> Vercel frontend works without extra config. Tighten to your Vercel URL later
> if you add credentialed requests.

> DB note: `start.sh` runs `alembic upgrade head` + a template seed on boot.
> Both target an ephemeral SQLite file inside the container (the default in
> `config.py`); they succeed without a managed DB. The verified templates
> (KG1/BuT) live in code, not the DB, so nothing about the KG1 flow depends on
> persistence.

---

## 2. Frontend → Vercel (already configured)

The project is already linked (`.vercel/project.json`).

1. In the Vercel project settings → **Environment Variables**, set
   `NEXT_PUBLIC_API_URL` = the backend URL from step 1 (no trailing slash).
2. Redeploy (push to the connected branch, or "Redeploy" in the dashboard).
3. Open the Vercel URL.

---

## 3. Live smoke test

From a fresh browser (no localStorage) on the Vercel URL:

1. Pick a language → **Start**.
2. Upload [familienkasse_kg1_v1.pdf](../burokratie-helfer/templates_source/familienkasse_kg1_v1.pdf).
3. Expect the **green Level-1 "Verified form"** banner.
4. As a **`ledig`** applicant: confirm you are NOT asked the partner questions,
   the "marital status since" date, or the abweichende-Person fields — and that
   the **Steuer-ID** is asked once (11 digits).
5. Fill the basics + Steuer-ID, go to review, **Generate & Download**.
6. Open the PDF: 5 pages, your answers in the right boxes, the Steuer-ID spread
   across its 4 comb boxes, umlauts intact, no error text.

If step 3 shows anything other than the green banner, the backend URL is wrong
or the backend is asleep (free tier cold start — wait ~50 s and retry).

---

## 4. Before broad promotion (not required to prove the loop)

- Complete the `«…»` placeholders in [impressum](../burokratie-helfer/frontend/src/app/[locale]/impressum/page.tsx)
  and [datenschutz](../burokratie-helfer/frontend/src/app/[locale]/datenschutz/page.tsx)
  with the operator's real identity + chosen hosting provider/region.
- Get one Beratungsstelle / Caritas / Diakonie volunteer to confirm a generated
  KG1 would be accepted by a real Familienkasse (the validation that proves the
  goal). See [QA_KG1_MANUAL.md](QA_KG1_MANUAL.md).
- Full RDG/DSGVO legal review + funding model — the next gate.
