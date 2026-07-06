# AI Resume Optimizer & Auto Job Apply Bot — Production Build Guide

A practical, step-by-step path from empty repo to deployed system, following the architecture you provided (Telegram → FastAPI → Nemotron → Supabase → GitHub Actions/Playwright → LinkedIn/Naukri).

---

## 0. Before You Start — Read This

**Legal/ToS note (important, not a blocker, just plan for it):** LinkedIn's and most job boards' Terms of Service prohibit automated scraping and automated form submission, even when using a user's own session cookies. This doesn't mean you can't build the project — plenty of people build personal/internal tools like this — but at production scale it carries real account-ban risk for your users, and "Auto Apply" specifically is the highest-risk phase. Practical mitigations baked into the plan below:
- Keep Playwright automation slow, human-paced (randomized delays, no parallel sessions per account).
- Never store raw passwords — only user-provided session cookies/tokens, encrypted at rest.
- Make the final "Submit" click always require the explicit per-job "Yes" from the user (which your design already does — keep it that way, don't let anyone talk you into batching it).
- Consider defaulting new users to "fill form, stop before final submit, let user click Submit manually" until you've validated stability.

With that noted, here's the build.

---

## 1. Tech Stack (concrete choices)

| Layer | Choice |
|---|---|
| Bot framework | `aiogram` 3.x (async, webhook-friendly) |
| Backend | FastAPI + `uvicorn` |
| DB | Supabase (Postgres + Storage) |
| LLM | Nemotron via NVIDIA NIM API (or OpenRouter proxy) |
| Automation | Playwright (Python) run inside GitHub Actions |
| PDF generation | WeasyPrint (Markdown → HTML → PDF) |
| Hosting (backend) | Hugging Face Spaces (Docker SDK) or Railway/Fly.io if you outgrow HF Spaces |
| Secrets | GitHub Actions secrets + HF Spaces secrets, never in code |
| Scheduling | GitHub Actions `schedule` cron trigger (daily job search) |
| Monitoring | Sentry (errors) + a simple `/health` endpoint + Telegram admin alerts |

---

## 2. Project Structure

```
resume-bot/
├── app/
│   ├── main.py                 # FastAPI entrypoint
│   ├── bot/
│   │   ├── handlers.py         # aiogram handlers
│   │   ├── keyboards.py
│   │   └── states.py           # FSM states for the conversation flow
│   ├── db/
│   │   ├── models.py           # SQLAlchemy models
│   │   ├── schema.sql          # raw SQL for Supabase
│   │   └── crud.py
│   ├── services/
│   │   ├── nemotron.py         # LLM calls
│   │   ├── resume_parser.py    # PDF/DOCX -> text
│   │   ├── pdf_generator.py    # Markdown -> PDF (WeasyPrint)
│   │   ├── ats_scorer.py
│   │   └── storage.py          # Supabase storage wrapper
│   ├── config.py               # pydantic-settings
│   └── security.py             # encryption for session cookies
├── automation/
│   ├── search_jobs.py          # Playwright: search
│   ├── apply_job.py            # Playwright: apply
│   └── utils.py
├── .github/workflows/
│   ├── search-jobs.yml
│   ├── daily-search.yml
│   └── apply-job.yml
├── Dockerfile
├── requirements.txt
└── tests/
```

---

## 3. Step-by-Step Build

### Step 1 — Repo, env, and secrets skeleton
```bash
git init resume-bot && cd resume-bot
python -m venv venv && source venv/bin/activate
pip install fastapi uvicorn aiogram sqlalchemy asyncpg supabase \
  weasyprint pypdf python-docx httpx pydantic-settings cryptography \
  playwright sentry-sdk
playwright install --with-deps chromium
```
Create `.env` (never commit it):
```
BOT_TOKEN=...
SUPABASE_URL=...
SUPABASE_SERVICE_KEY=...
NEMOTRON_API_KEY=...
ENCRYPTION_KEY=...           # for encrypting stored session cookies
GITHUB_PAT=...               # to trigger workflow_dispatch from FastAPI
SENTRY_DSN=...
```
Add `.env`, `venv/`, `*.pdf` to `.gitignore` immediately — resumes and cookies must never land in git history.

### Step 2 — Database schema (Supabase)
Run this in the Supabase SQL editor:
```sql
create table users (
  id bigint primary key generated always as identity,
  telegram_id bigint unique not null,
  preferred_role text,
  experience_years numeric,
  locations text[],
  created_at timestamptz default now()
);

create table resumes (
  id bigint primary key generated always as identity,
  user_id bigint references users(id),
  version int not null,
  storage_path text not null,
  ats_score numeric,
  approved_keywords text[],
  created_at timestamptz default now()
);

create table jobs (
  id bigint primary key generated always as identity,
  source text,               -- linkedin/naukri/indeed
  title text, company text,
  description text, apply_link text,
  requirements jsonb,
  found_at timestamptz default now()
);

create table applications (
  id bigint primary key generated always as identity,
  user_id bigint references users(id),
  job_id bigint references jobs(id),
  resume_id bigint references resumes(id),
  status text,                -- applied/pending/rejected/failed
  applied_at timestamptz
);

create table user_sessions (
  user_id bigint references users(id),
  platform text,               -- linkedin/naukri
  encrypted_cookie text,
  updated_at timestamptz default now()
);
```
Enable Row Level Security and restrict access to the service role only — the bot backend is the sole writer.

### Step 3 — FastAPI skeleton + health check
```python
# app/main.py
from fastapi import FastAPI
import sentry_sdk
from app.config import settings

sentry_sdk.init(dsn=settings.SENTRY_DSN, traces_sample_rate=0.2)
app = FastAPI()

@app.get("/health")
def health():
    return {"status": "ok"}
```
Deploy this bare-bones version first. Confirm HF Spaces / Railway serves `/health` before adding complexity — catching deployment issues early saves days later.

### Step 4 — Telegram bot with FSM (aiogram)
Use aiogram's `FSMContext` to drive Phases 1, 6, 7, 10, 13 (the multi-turn conversations). Sketch:
```python
class Onboarding(StatesGroup):
    waiting_resume = State()
    waiting_role = State()
    waiting_experience = State()
    waiting_locations = State()

@router.message(Onboarding.waiting_resume, F.document)
async def handle_resume(msg: Message, state: FSMContext):
    file = await bot.get_file(msg.document.file_id)
    # download, upload to Supabase storage, save path in state
    await state.update_data(resume_path=path)
    await state.set_state(Onboarding.waiting_role)
    await msg.answer("Preferred Role?")
```
Run the bot via **webhook**, not long-polling, in production — set the webhook to your FastAPI `/telegram/webhook` route so one process serves both bot and API. This avoids running a second always-on worker.

### Step 5 — Nemotron integration
Centralize all LLM calls in one module so you can add retries/timeouts once:
```python
# app/services/nemotron.py
import httpx

async def call_nemotron(system_prompt: str, user_prompt: str, json_mode=False) -> str:
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(
            "https://integrate.api.nvidia.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {settings.NEMOTRON_API_KEY}"},
            json={
                "model": "nvidia/nemotron-4-340b-instruct",  # confirm current model id
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0.2,
            },
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]
```
For Phase 4 (JD extraction) and Phase 9 (ATS scoring), force strict JSON output and validate with a Pydantic model before trusting it — LLMs occasionally return malformed JSON, and you don't want that crashing the bot mid-conversation.

For Phase 8 (resume rewrite), hard-code the constraint prompt exactly as you specified — never modify Objective/Education, only use approved keywords — and **also enforce it in code**: diff the returned Objective/Education sections against the original and reject the LLM output if they changed. Don't rely on the prompt alone.

### Step 6 — Resume parsing & PDF generation
- Parsing: `pypdf` for text-based PDFs, `python-docx` for Word uploads. If a resume is a scanned image PDF, you'll need OCR (e.g., `pytesseract`) as a fallback — flag this to the user rather than silently failing.
- Generation: build a Jinja2 resume template (HTML+CSS), inject the Nemotron-rewritten sections, render with WeasyPrint:
```python
from weasyprint import HTML
html_str = render_template("resume_template.html", **resume_data)
HTML(string=html_str).write_pdf("/tmp/resume_v2.pdf")
```
Keep 2–3 template styles (e.g., modern, ATS-safe minimal) since some ATS systems parse simple layouts far better than fancy ones.

### Step 7 — Job search automation (Playwright + GitHub Actions)
Don't run Playwright inside your always-on FastAPI process — it's heavy and fragile for long-lived services. Instead, trigger a GitHub Actions workflow from FastAPI via the GitHub API (`workflow_dispatch`), passing user_id/search params as inputs:
```python
async def trigger_job_search(user_id: int, role: str, locations: list[str]):
    async with httpx.AsyncClient() as client:
        await client.post(
            f"https://api.github.com/repos/{OWNER}/{REPO}/actions/workflows/search-jobs.yml/dispatches",
            headers={"Authorization": f"Bearer {settings.GITHUB_PAT}"},
            json={"ref": "main", "inputs": {"user_id": str(user_id), "role": role}},
        )
```
`.github/workflows/search-jobs.yml`:
```yaml
name: search-jobs
on:
  workflow_dispatch:
    inputs:
      user_id: {required: true}
      role: {required: true}
jobs:
  search:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: {python-version: '3.11'}
      - run: pip install -r requirements.txt && playwright install --with-deps chromium
      - run: python automation/search_jobs.py --user_id ${{ inputs.user_id }} --role "${{ inputs.role }}"
        env:
          SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
          SUPABASE_SERVICE_KEY: ${{ secrets.SUPABASE_SERVICE_KEY }}
```
The script writes results directly to Supabase — GitHub Actions doesn't need to call your API back. Then either poll from the bot or use Supabase Realtime/webhooks to notify FastAPI when a run finishes.

Playwright reliability tips that matter in production:
- Use `page.wait_for_selector` with real timeouts, never `sleep`-only waits.
- Randomize delays between actions (500–2000ms) to look human and reduce detection/rate-limit risk.
- Wrap every selector interaction in try/except with screenshots-on-failure uploaded as workflow artifacts, so you can debug selector drift when LinkedIn changes its DOM (it will, repeatedly).
- Rotate/refresh session cookies gracefully — detect logged-out state and prompt the user to re-auth via Telegram rather than silently failing.

### Step 8 — Auto-apply automation (Phase 14)
Same pattern as Step 7, separate workflow (`apply-job.yml`), triggered only after the user's explicit per-job "Yes." Decrypt the stored session cookie just-in-time inside the Action (never persist it in workflow logs — mask it), inject into Playwright's browser context, perform Easy Apply, then re-encrypt and rotate the cookie if it's changed.

### Step 9 — ATS scoring (Phase 9)
Two components:
1. **LLM-based** (Nemotron): qualitative suggestions, missing keywords, action-verb strength.
2. **Deterministic** keyword-overlap score you compute in Python (not just the LLM's opinion) — e.g., `matched_keywords / total_required_keywords * 100` — so the score is reproducible and auditable, not just an LLM guess. Blend both into the number you show the user.

### Step 10 — Wire the full conversation flow
Go phase by phase (1→16) exactly as you outlined, using aiogram FSM states for each decision point (Phase 6 approval, Phase 10 improve-further, Phase 13 apply-yes/no). Store all intermediate state in Postgres, not just in-memory FSM, so a bot restart doesn't lose a user mid-flow.

---

## 4. Deployment

1. **Backend**: Dockerize FastAPI, deploy to Hugging Face Spaces (Docker SDK) — set all secrets in the Space's settings, not in the Dockerfile.
2. **Bot webhook**: after deploy, call `setWebhook` once with your HF Spaces public URL + `/telegram/webhook`.
3. **GitHub Actions**: store `SUPABASE_*`, cookie encryption key, etc. as repo secrets. Add `daily-search.yml` with a `schedule: cron` trigger for Phase "Daily Job Search."
4. **Supabase**: enable RLS, restrict storage bucket policies so resumes are only readable via signed URLs you generate server-side, not public.

---

## 5. Production Hardening Checklist

- [ ] All secrets via env vars / platform secret stores — zero secrets in git history (run `git-secrets` or `trufflehog` before first push).
- [ ] Encrypt session cookies at rest (Fernet symmetric encryption is enough for this scale).
- [ ] Rate-limit Telegram handlers per user (avoid spam-triggering GitHub Actions runs — GitHub free tier has monthly minute caps).
- [ ] Retry + timeout wrapper around every external call (Nemotron, Supabase, GitHub API) — use `tenacity` for exponential backoff.
- [ ] Validate all LLM JSON outputs against Pydantic schemas before using them; fall back gracefully with a Telegram message ("couldn't parse that, retrying...") rather than crashing.
- [ ] Sentry (or similar) wired into FastAPI, the bot, and the Playwright scripts (log failures + screenshots as artifacts).
- [ ] Structured logging (`structlog` or plain JSON logs) so you can trace a single user's flow across bot → API → GitHub Action.
- [ ] Automated tests: unit tests for `resume_parser`, `ats_scorer`, and the Objective/Education-lock enforcement; integration test that mocks Nemotron and Supabase.
- [ ] A staging Supabase project + staging bot token, separate from production, so you can test Playwright changes without touching real user data.
- [ ] Alembic migrations for schema changes instead of hand-editing the Supabase SQL editor once you have real users.
- [ ] Admin Telegram channel that gets pinged on any Auto Apply failure, so a broken selector doesn't fail silently for days.

---

## 6. Suggested Build Order (so you always have something working)

1. FastAPI `/health` deployed → confirms hosting works.
2. Telegram bot echoing messages via webhook → confirms bot↔backend wiring.
3. Resume upload → Supabase storage → confirms DB/storage.
4. Nemotron JD extraction on a hardcoded JD → confirms LLM integration.
5. Full Phase 1–12 (search → optimize → PDF) with **manual** job data (skip Playwright at first) → confirms the core value loop end-to-end.
6. Add Playwright job search (Phase 3) via GitHub Actions.
7. Add Playwright auto-apply (Phase 14) last, behind a feature flag, tested only on your own account first.
8. Add optional features (cover letters, interview questions, `/history`, daily search) once the core loop is stable.

Building auto-apply last is deliberate — it's the highest-risk, most fragile part (dependent on external site DOM structure), and you want the rest of the pipeline proven stable before you're debugging live form submissions.

---

If you want, I can now generate actual starter code for any specific step above (e.g., the full aiogram FSM handlers, the Supabase schema as a runnable migration, or the WeasyPrint resume template) — just say which piece to start with.
