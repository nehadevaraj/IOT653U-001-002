# CommuTech: README (IOT 653U Assessment 001 and 002)
 
> **Tagline:** *Live + near‑term Tube disruption made simple for commuters. API‑first insights and forecasting next.*
 
---
 
## Table of contents
- [What CommuTech is ](#what-commutech-is-for-001)
- [Repository layout](#repository-layout)
- [Quick start](#quick-start)
- [How the notebook runs (pipeline)](#how-the-notebook-runs-pipeline)
- [Figures I use in the 001 deck (with code highlights)](#figures-i-use-in-the-001-deck--with-code-highlights)
  - [#1 Tube status now](#1-tube-status-now)
  - [Hour×Day heatmap of event‑hours](#hourxday-heatmap-of-eventhours)
  - [AM vs PM commute‑risk by line](#am-vs-pm-commute-risk-by-line)
  - [Planned disruption hours by line (lollipop)](#planned-disruption-hours-by-line-lollipop)
  - [Upcoming timetable Top 30](#upcoming-timetable-top-30)
- [Tunable parameters](#tunable-parameters)
- [Data sources & methods](#data-sources--methods)
- [Assessment 001 alignment](#assessment-001-alignment)
- [Assessment 002 implementation: Streamlit app](#assessment-002-implementation--streamlit-app)
  - [Phase 1 offline reference layer](#phase-1-offline-reference-layer)
  - [Phase 2 live signal layer-commutech-cockpit](#phase-2-live-signal-layer-commutech-cockpit)
  - [Manual refresh governance](#manual-refresh-governance)
  - [Running the app locally](#running-the-app-locally)
- [Obstacles & mitigations](#obstacles--mitigations)
- [Business case snapshot](#business-case-snapshot)
- [Repo hygiene: `.env.example` and `.gitignore`](#repo-hygiene-envexample-and-gitignore)
- [Troubleshooting](#troubleshooting)
- [Security, privacy, attribution & licensing](#security-privacy-attribution--licensing)
- [Post-Assessment 002 pipeline from 13-jan](#post-assessment-002-pipeline-from-13-jan)
- [Appendix: Copy-paste snippets](#appendix--copy-paste-snippets)
 
---
 
## What CommuTech is
**Problem:** Unreliable service creates stress and productivity loss for London commuters, especially at peak times.
 
**My solution for 001:** I use TfL’s Unified API to surface **when** and **where** disruption is likely in the *next N days*, with visuals optimised for decision‑making at a glance:
- "**Now**" status overview (which lines are affected right now?)
- **Hour×day heatmap** of planned disruption (where time risk clusters)
- **AM/PM commute‑risk by line** (what a commuter will actually feel)
 
> I prioritise communication of value with interpretable analytics. In 002 I will extend this into forecasting and a small app back‑end.
 
---
 
## Repository layout
```
.
├── Datasets.ipynb                # main notebook – run end‑to‑end
├── figures/                      # exported images I use in slides
│   ├── #1 tube status now v2.png
│   ├── commutech_next14_heatmap_v2.png
│   ├── commutech_next14_commute_risk_v2.png
│   ├── commutech_next_hours_by_line_v2.png
│   ├── commutech_next_upcoming_top30_v2.png
│   └── ... (earlier figures kept for reference)
├── requirements.txt              # Python dependencies
├── Makefile                      # optional helpers (venv, install)
└── README.md                     # this file
```
 
---
 
## Quick start
### Prereqs
- Python **3.10+**
- A **TfL Unified API** key (Primary or Secondary)
 
### Setup
```bash
python -m venv .venv && source .venv/bin/activate   # macOS
pip install -r requirements.txt
 
# I set my key as an environment variable (never committed to Git)
# See the Appendix for several ways to do this securely.
export TFL_APP_KEY="<YOUR_TFL_KEY>"
```
 
### Run
I open **Datasets.ipynb** in VS Code and **Run All**. The notebook:
1. Pulls a live **snapshot** and a **look‑ahead** (from `validityPeriods`).
2. Builds tidy data for visuals.
3. Writes slide images to `figures/`.
 
> If a plot is blank, it usually means there are **no planned windows in the current horizon**. I increase the look‑ahead to 28–45 days and re‑run the look‑ahead + plotting cells.
 
---
 
## How the notebook runs (pipeline)
1. **Snapshot** → `GET /Line/Mode/tube/Status?detail=true` returns per‑line statuses and any `validityPeriods` (from‑to timestamps).
2. **Look‑ahead** → I normalise validity windows to **Europe/London** and split into hourly buckets with **true duration overlap**.
3. **Visuals** → The derived hour×day matrix and commute‑window overlaps are rendered as the figures listed below.
 
---
 
## Figures I use in the 001 slide deck (with code highlights)
 
### #1 Tube status now
**File:** `figures/#1 tube status now v2.png`
 
**What:** Donut of status categories + ranked lollipop of lines by **current worst severity** (10 = Good Service; lower = worse). Non‑good lines are annotated with TfL’s wording (Minor/Severe/Closures).
 
**Core code:**
```python
snap = get("/Line/Mode/tube/Status", {"detail": "true"})
rows = []
for line in snap:
    worst_sev, worst_desc = 10, "Good Service"
    for st in (line.get("lineStatuses") or []):
        sev  = st.get("statusSeverity", 10) or 10
        desc = (st.get("statusSeverityDescription") or "Good Service").strip()
        if sev < worst_sev: worst_sev, worst_desc = sev, desc
    rows.append({"line": line["name"], "severity": worst_sev, "status": worst_desc})
now_df = pd.DataFrame(rows)
```
**Why it’s in 001:** One‑glance answer to “how bad is it now?” with the exact TfL status wording.
 
---
 
### Hour×Day heatmap of event‑hours
**File:** `figures/commutech_next14_heatmap_v2.png`
 
**What:** For the next ~N days, each cell shows the **sum of disruption duration** overlapping that hour×day slot. **White = none**. Commute windows (Mon–Fri **07–10** & **16–19**) are outlined; top hotspots are labelled with `xh`.
 
**Core code (true overlap weighting):**
```python
Z = np.zeros((7,24), float)
for _, r in plan_df.iterrows():
    s = r["from_local"].floor("H"); e = r["to_local"].ceil("H")
    t = s
    while t < e:
        slot_end = t + pd.Timedelta(hours=1)
        overlap = (min(e, slot_end) - max(s, t)).total_seconds()/3600.0
        if overlap > 0:
            Z[int(t.dayofweek), int(t.hour)] += overlap
        t = slot_end
```
**Why it’s in 001:** It shows *when* pain clusters (e.g., Thu 18–22) and directly supports CommuTech’s alerting proposition.
 
---
 
### AM vs PM commute‑risk by line
**File:** `figures/commutech_next14_commute_risk_v2.png`
 
**What:** Stacked % bars per line. Risk = share of **weekday commute hours** (Mon–Fri, 07–10 & 16–19) that are planned to be disrupted in the horizon.
 
**Core code (AM/PM windows + denominator):**
```python
weekdays   = days[days.dayofweek < 5]
avail_am   = len(weekdays) * 3   # 07–10
avail_pm   = len(weekdays) * 3   # 16–19
 
acc = {}
for _, r in plan_df.iterrows():
    s, e, line = r["from_local"], r["to_local"], r["line"]
    day = s.floor("D")
    while day <= e.floor("D"):
        amh = overlap_hours(s, e, day+pd.Timedelta(hours=7),  day+pd.Timedelta(hours=10))
        pmh = overlap_hours(s, e, day+pd.Timedelta(hours=16), day+pd.Timedelta(hours=19))
        acc.setdefault(line, {"am":0.0, "pm":0.0})
        acc[line]["am"] += amh; acc[line]["pm"] += pmh
        day += pd.Timedelta(days=1)
 
risk = (pd.DataFrame.from_dict(acc, orient="index")
          .reset_index().rename(columns={"index":"line"}))
risk["risk_am_pct"] = (risk["am"] / max(1e-9, avail_am)) * 100
risk["risk_pm_pct"] = (risk["pm"] / max(1e-9, avail_pm)) * 100
```
**Why it’s in 001:** It prioritises lines where commuters will actually feel the pain at peak times, split AM vs PM.
 
---
 
### Planned disruption hours by line (lollipop)
**File:** `figures/commutech_next_hours_by_line_v2.png`
 
**What:** Ranked **lollipop** (stems + dots) with value labels. A clearer alternative to a dense bar wall.
 
**Core code:**
```python
plan_df["hours"] = (plan_df["to"] - plan_df["from"]).dt.total_seconds()/3600.0
by_line = (plan_df.groupby("line", as_index=False)["hours"].sum()
                    .sort_values("hours", ascending=False))
```
**Why it’s in 001:** It shows where disruption hours concentrate in the chosen horizon.
 
---
 
### Upcoming timetable Top 30
**File:** `figures/commutech_next_upcoming_top30_v2.png`
 
**What:** A clean table of the next 30 windows, with alternating row shading and a thin start‑hour tick. Slide‑ready, no raw DataFrame screenshots.
 
**Core code (format):**
```python
top = (plan_df.sort_values(["from_local","line"]).head(30)
        .assign(start=lambda d: d["from_local"].dt.strftime("%a %d %b %H:%M"),
                end=lambda d: d["to_local"].dt.strftime("%a %d %b %H:%M")))
# render as a matplotlib table and draw a small hour tick per row
```
**Why it’s in 001:** It communicates *what’s coming up and when* at a glance.
 
---
 
## Tunable parameters
- `LOOKAHEAD_DAYS` (default 14) → I set 28–45 for richer planned‑works patterns when needed.
- Commute windows → Mon–Fri **07–10** and **16–19** (editable in the commute‑risk & heatmap cells).
- Snapshot recency for the optional “worst now” helper → default **30 min** (I bump to 60–120 for noisier demos).
 
---
 
## Data sources & methods
- **TfL Unified API**
  - `GET /Line/Mode/tube/Status?detail=true` → live snapshot; I keep the *worst current* status and its `validityPeriods` per line.
  - `validityPeriods` → near‑term schedule (planned or ongoing) used to create the look‑ahead.
- **Event‑hours** → per hour×day cell, I sum planned duration overlapping that hour within the horizon.
- **Commute‑risk** → event‑hours during Mon–Fri 07–10 and 16–19 divided by available commute hours in the horizon.
 
> When validity periods are missing, a status may still apply “now”. The cells treat the snapshot as active over a short default window.
 
---
 
## Assessment 001 alignment
- **Societal relevance:** I quantify *time risk* where commuters feel it; supports wellbeing and productivity.
- **Proposed solution:** API‑powered insights → clear, non‑technical visuals.
- **Alternatives considered:**
  - **ARIMA/SARIMA** on historical indices (baseline forecasts).
  - **ML classifiers** with lags, time‑of‑day, planned‑works flags (richer, heavier).
  - For 001, an API‑first approach wins on clarity and immediacy; forecasting moves to 002.

---

## Assessment 002 implementation: CommuTech Streamlit app
 
In Assessment 001, CommuTech is a notebook-first analytics prototype: it uses TfL’s Unified API to produce interpretable, decision-ready visuals (status now, disruption clustering, and commute-window risk) and exports the exact figures used in the slide deck.
 
In Assessment 002, I implement the “operational layer” of CommuTech as an interactive Streamlit application (located in `CommuTech for 002/`). This turns the analysis into an end-user artefact: a commuter-facing interface that combines an offline reference layer (stations/zones/lines) with an optional live signal layer (TfL API), under explicit governance controls.
 
### Phase 1 (offline reference layer)
Phase 1 provides deterministic, non-networked functionality using public/static reference data:
- Station selection (“From” / “To”) from offline station metadata.
- Zones/line membership, direct-line intersection, and a simplified zones-based peak fare estimate.
- “Basic data checks” surfaced in-app to validate that offline reference mappings load and join cleanly.
 
This phase proves the end-to-end product workflow (UI → logic → outputs) without dependency on live services.
 
### Phase 2 (live signal layer: CommuTech Cockpit)
Phase 2 introduces live operational telemetry from the TfL Unified API and presents it in the CommuTech Cockpit:
- A network-wide pulse (headline summary of line status across the system).
- A journey “zoom-in” (filters the network view down to lines relevant to the selected journey).
- Live arrivals at the destination StopPoint (preview + full table where enabled in code).
 
The Phase 2 layer is explicitly optional: if no API key is available, the app continues to run in Phase 1 mode.
 
### Live data governance: manual refresh
The live layer is *not* pulled continuously. Instead, live calls occur only when the user clicks **Refresh live data**. This provides:
- predictable cost and rate-limit behaviour,
- traceable “last refreshed” timestamps,
- clear governance separation between static reference data and volatile operational signals.
 
### Running the app locally
1. Open a terminal in `CommuTech for 002/`
2. Ensure dependencies are installed (Streamlit + requests + python-dotenv alongside the repo requirements approach).
3. Set a TfL API key (Phase 2 only):
   - The app expects `TFL_API_KEY` (recommended).
   - If your Assessment 001 environment used `TFL_APP_KEY`, you can set both to the same value.
 
Example:
    export TFL_API_KEY="<YOUR_TFL_KEY>"
    export TFL_APP_KEY="<YOUR_TFL_KEY>"
 
4. Run Streamlit against the main app file (the script containing `st.set_page_config(...)`):
    streamlit run <your_streamlit_app>.py

---
 
## Obstacles & mitigations
- **Data sparsity** in short horizons → I widen to **28–45 days** and label that plans can change.
- **API rate limits/outages** → I use simple caching, retries, and back‑off; visuals surface “no planned windows”.
- **Key security** → I keep keys in env vars; never commit keys; rotate if exposed.
- **Timezone quirks** → I normalise to `Europe/London`; fallback to UTC if unavailable.
 
---
 
## Business case snapshot
- **Value:** Fewer missed connections; calmer commutes; better arrival predictability.
- **Audience:** Weekday commuters on highest‑risk lines/times.
- **Model:** Free tier + Pro (ad‑free, personalised alerts, calendar sync).
- **Differentiator:** *When‑focused* risk that non‑technical audiences grasp in seconds (AM/PM risk + heatmap hotspots).
 
---
 
## Repo hygiene: `.env.example` and `.gitignore`
I commit a **`.env.example`** to show required variables, and I **do not** commit my real `.env`.
> Note: the Streamlit app (002) reads `TFL_API_KEY`; the notebook workflow (001) examples use `TFL_APP_KEY`. You can safely set both to the same TfL key.
 
**`.env.example:`**
```dotenv
# Copy this file to .env and fill in the value below
TFL_APP_KEY=__REPLACE_WITH_YOUR_TFL_KEY__
```
 
**`.gitignore`** (key lines)
```gitignore
# Python
__pycache__/
*.pyc
.venv/
 
# Jupyter
.ipynb_checkpoints/
 
# macOS
.DS_Store
 
# Env files (never commit real secrets)
.env
.env.*
```
> I create **both** of these files in the repo - commit `.env.example` and `.gitignore`; do **not** commit `.env`.
 
---
 
## Troubleshooting
- **Blank heatmap / commute‑risk:** No planned windows → increase `LOOKAHEAD_DAYS` and re‑run look‑ahead + plots.
- **HTTP 401/403:** `TFL_APP_KEY` not set/valid → re‑export or rotate in TfL portal.
- **HTTP 429:** short‑term rate limit → add small sleeps between calls.
- **Figures cut off:** re‑run the plotting cell; all figures call `tight_layout()` and save at high DPI.
 
---
 
## Security, privacy, attribution & licensing
- **Privacy:** Only public TfL data, **no PII**.
- **Secrets:** I keep my TfL key in env vars / a git‑ignored `.env`. I never commit keys. If a key is exposed, I rotate it immediately in the TfL portal.
- **Attribution:** Data © Transport for London (TfL). Use complies with Unified API terms.
 
### Licensing (stance for 001)
> **For Assessment 001:** I apply **no licence**. This public repo remains *all‑rights‑reserved by default* and others can view the code/assets but do not have reuse rights.
>
> **EDIT for 002 (planned):** When I move to 002, I may adopt a permissive licence (e.g., MIT) to encourage reuse. If I do, I will add a `LICENSE` file and include a short note here:
>
> ```text
> [002 EDIT] Licensing update - MIT license added on <DATE>. Third‑party data remains © TfL; I comply with their terms. TBC
> ```
 
---

## Post-Assessment 002 pipeline (from 13 Jan)
 
Assessment 002 completes the core build of CommuTech as a two-layer system (offline reference + live signal). Future scope is therefore positioned as controlled extension rather than unfinished implementation.
 
Planned extensions after 13 Jan (pipeline-style), aligned to IoT/analytics marking themes (data engineering, governance, modelling, evaluation, and operationalisation):
 
  1. Routing layer (graph-backed): add a minimal station–line graph to generate route sequences and interchange hints, enabling route-aware (not just zone-aware) outputs.
  2. Fare intelligence: replace the zones-based estimator with TfL fare endpoints (where available) and compute best/worst-case by route + time band.
  3. Reliability modelling: derive per-line reliability scores using historical disruption windows; calibrate severity weights and evaluate against observed delay metrics.
  4. Forecasting: train a horizon-based disruption forecaster (e.g., probabilistic next-24h/next-7d risk by line) with feature sets including time-of-week, planned works, and event-hour density.
  5. Service observability: introduce structured logging of refresh events, API response metadata (counts, timestamps), and user journey selections for reproducibility and audit.
  6. Data QA expansion (“complex data checks”): automatic summaries of live payload completeness (coverage of lines returned, missing statuses, empty arrivals, StopPoint match confidence) surfaced as a concise UI expander alongside offline checks.
  7. Packaging & deployment: containerise the app (Docker) and/or deploy to a controlled-access hosting pattern (private link / assessor access window), with secrets management and environment isolation.
 
These improvements are deliberately scoped as modular increments so the system can be evaluated and extended without changing the Phase 1/Phase 2 architecture.
 
---
 
## Appendix
 
### API key setup (public README: no live key)
For security, I do **not** include a live API key in this public README. For assessors, I provide a **temporary key** (valid as of **12:30 BST, 21 Oct 2025**) via a private channel (e.g., OneDrive/submission notes). Locally, I set the key using one of the methods below.
 
**Session‑only (while testing):**
```bash
export TFL_APP_KEY="<YOUR_TFL_KEY>"   # lasts for the current terminal session
```
 
**Persistent (shell startup, zsh on macOS):**
```bash
echo 'export TFL_APP_KEY="<YOUR_TFL_KEY>"' >> ~/.zshrc
source ~/.zshrc
```
 
**.env file (git‑ignored):**
1. Create `.env` next to the notebook (ensure `.env` is in `.gitignore`).
2. Put the line:
```
TFL_APP_KEY=<YOUR_TFL_KEY>
```
3. In the notebook’s first cell, load it:
```python
from dotenv import load_dotenv; load_dotenv()
import os; assert os.getenv("TFL_APP_KEY"), "Set TFL_APP_KEY in environment or .env"
```
 
**Rotate a leaked key:** If a key was ever pasted publicly, I regenerate (rotate) the key in the TfL developer portal and update my environment.