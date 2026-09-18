# ⚡ Reach — Autonomous Job Outreach & Application Hub

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=flat&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-009688?style=flat&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Playwright](https://img.shields.io/badge/Playwright-Firefox-2EAD33?style=flat&logo=playwright&logoColor=white)](https://playwright.dev/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Database-336791?style=flat&logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![Responsive](https://img.shields.io/badge/UI-Mobile%20%26%20Desktop-6366F1?style=flat)](#mobile-access)
[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

**Reach** is a job discovery, AI-assisted screening, and automated cold outreach suite. It aggregates job opportunities from multiple platforms (LinkedIn and tech park portals like Infopark Kochi), uses custom ChatGPT models to craft tailored cold emails, screens out unsuitable criteria (e.g. strict demographic or gender requirements), and launches Gmail in visible, headed Firefox with your resume pre-attached for human review and 1-click sending.

---

## ✨ Core Highlights & Features

### 1. 🌐 Extensible Crawler Registry & Unified Source Selector
- **One Crawler Interface**: Instead of multiple disjointed buttons, a single **Source Dropdown** and **Crawl Button** (`[ 💼 LinkedIn Posts ▾ ] [ ⚡ Crawl ]`) controls all scraping operations.
- **Pluggable Registry (`SCRAPER_REGISTRY`)**: Add new website crawlers (e.g. Indeed, Technopark, Naukri, YC Jobs) in just one step on the backend without modifying frontend markup.
- **90-Second Inactivity Watchdog**: All crawlers are guarded by an automated watchdog. If scraping halts or hangs for 90 seconds, the task closes cleanly while safely preserving all discovered jobs in PostgreSQL.

### 2. 🗄️ Database-Backed Settings
- **PostgreSQL Persistence**: `chatgpt_url` (Custom GPT Chat Link) and `search_query` (Target Search Keywords) are stored directly in the `settings` database table.
- **Dynamic In-App Configuration**: Update your search keywords and Custom GPT link directly inside the web dashboard Settings modal with instant database synchronization.
- **Safe by Default**: Zero hardcoded personal URLs or file paths in tracked files.

### 3. 🛡️ Intelligent Anti-Spam & Fraud Protection
- **Exact Duplicate Auto-Rejection**: Automatically rejects incoming job posts sharing an exact contact email already in the database with the reason `"Spam: Duplicate email (<email>) already in database"`.
- **Corporate Domain Anomaly Flagging**: Detects when different prefixes use the same custom/corporate domain across multiple recruiters, flagging the post with a `⚠️ Potential Spam` badge.
- **Public Domain Whitelist**: Public email providers (`gmail.com`, `hotmail.com`, `yahoo.com`, `outlook.com`, `icloud.com`, `proton.me`, etc.) are exempted from domain-based spam grouping.
- **1-Click Spam Marking**: Instantly flag any job post as spam/scam directly from the Home page or Review workspace (`🚫 Spam`).

### 4. 🗂️ 3-Stage Application Lifecycle
- **Discovered Posts**: Raw incoming job descriptions with recruiter contact details, experience level pills, and multi-source badges (`LinkedIn`, `Infopark Kochi`, `Manual`).
- **Review & Drafts**: Side-by-side workspace displaying the original job post against the ChatGPT-generated email draft, with live editing and resume attachment validation.
- **Others / History**: Unified chronological archive of all `Sent` applications and `Cancelled` / `Discarded` posts. Clicking any card opens full details, cancellation reasons, and sent email bodies, with 1-click **Restore**.

### 5. ⚡ Pre-Made Cancellation Reasons
- 1-click chips for common rejection criteria:
  - `⚠️ Not enough experience`
  - `🚫 Not a job / Promotional`
  - `👩 Female candidates only`
  - `⚡ Irrelevant tech stack`
  - `💰 Unrealistic / Low budget`
  - `🗑️ Spam / Duplicate`
- Stored permanently in `posts.rejection_reason` and viewable across the application.

---

## 🏗️ Architecture

```mermaid
flowchart LR
    subgraph Sourcing ["1. Sourcing & Aggregation"]
        A["LinkedIn Posts Scraper"] --> REG{"Scraper Registry"}
        B["Infopark Kochi Scraper"] --> REG
        C["Manual JD Ingestion"] --> DB[("PostgreSQL Database\n(posts, settings)")]
        REG --> DB
    end

    subgraph Screening ["2. AI Screening & Outreach"]
        DB --> D["ChatGPT Automation (Custom GPT)"]
        D -- Tailored Draft --> DB
        D -- Unsuitable Criteria --> REJ["Auto-Reject & Tag"]
        REJ --> DB
    end

    subgraph Dashboard ["3. Application Management"]
        DB --> E["Discovered Feed"]
        DB --> F["Review & Drafts"]
        DB --> G["Others (Sent & Cancelled)"]
        F --> H["Headed Firefox (Gmail Compose)"]
        H -- 1-Click Send --> G
    end
```

---

## 🔒 Security & Privacy

This codebase is configured to be **safe to open-source**:
- **No Stored Passwords**: Reach uses your existing logged-in browser sessions stored locally in Firefox (`~/.playwright_firefox_profile`).
- **Zero Exposed Keys & Personal Paths**: No user home directories, personal resume files, or private ChatGPT conversation UUIDs are tracked in git.
- **Strictly Headed Automation**: All automated browser interactions execute visibly (`headless=False`), allowing real-time monitoring of every action.

---

## 🚀 Getting Started

### 1. Prerequisites
- **Python 3.10+**
- **PostgreSQL** installed and running locally
- **Firefox Browser** installed

### 2. Installation

```bash
# Clone repository
git clone https://github.com/your-username/reach-job-automation.git
cd reach-job-automation

# Set up virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies and Playwright Firefox
pip install -r requirements.txt
playwright install firefox
```

### 3. Database Initialization

```bash
# Create local PostgreSQL database
createdb linkedin_scrapper

# Copy environment template
cp .env.example .env
```

If your PostgreSQL user differs from your default OS user, update `DATABASE_URL` in `.env`:
```env
DATABASE_URL=postgresql://username:password@localhost:5432/linkedin_scrapper
PORT=8000
HOST=0.0.0.0
```

### 4. Application Configuration

Copy the template configuration file:
```bash
cp config.example.json config.json
```

On first launch, Reach automatically creates both the `posts` and `settings` tables and seeds your active search keywords and Custom GPT link. You can configure them either in `config.json` or through the dashboard **Settings** modal anytime.

---

## 🖥️ Running the Application

Start the local server:
```bash
python3 run.py
```

The terminal displays your access URLs:
```text
======================================================================
  Reach — Job Outreach Automation Hub
  Mac (Local):     http://localhost:8000
  Phone (Wi-Fi):   http://192.168.1.10:8000  <-- Open on Phone
  Automation Mode: Strictly Headed (headless=False)
======================================================================
```

- **Desktop**: Open [http://localhost:8000](http://localhost:8000)
- **Mobile / Smartphone**: Connect to the same local Wi-Fi and open the Phone URL to manage applications on mobile.

---

## 📱 Mobile Access

Reach features a dedicated mobile responsive design:
- **Rich Card Feed**: Table rows transform into touch-friendly cards displaying recruiter name, source badge, experience pills, contact email, and one-tap action buttons.
- **Touch Actions**: Review original job descriptions, edit drafts, mark spam, cancel with chips, and trigger Gmail compose directly from your phone.
- **Unified Others Tab**: Inspect sent outreach emails and reasons for cancelled posts with single-tap details and instant restoration.

---

## 📂 Project Structure

```text
reach-job-automation/
├── config.example.json       # Template configuration
├── config.json               # Local user configuration (git-ignored)
├── requirements.txt          # Python dependencies
├── run.py                    # Server startup & network binding
├── .env.example              # Environment variables template
├── .gitignore                # Open-source git-ignore rules
├── docs/
│   ├── file_architecture.md  # Detailed module & API registry
│   └── workflows.md          # Technical workflows & DOM selectors
├── resumes/                  # User resumes directory (git-ignored)
├── scripts/
│   ├── linkedin_posts_search.py  # Standalone LinkedIn posts scraper
│   ├── infopark_jobs_search.py   # Standalone Infopark portal scraper
│   ├── process_posts_with_chatgpt.py # Batch ChatGPT generator
│   └── prepare_gmail_draft.py    # Gmail compose launcher
└── src/
    ├── app.py                # FastAPI endpoints & REST API
    ├── automation_tasks.py   # Scraper registry & background task manager
    ├── chatgpt_service.py    # ChatGPT prompt & generation logic
    ├── db.py                 # PostgreSQL client, settings & spam filters
    ├── experience_extractor.py # YOE & seniority parsing
    ├── firefox_connector.py  # Headed Playwright Firefox context
    ├── gmail_service.py      # Gmail draft preparation
    ├── health_service.py     # Live session health checks
    └── static/
        ├── app.js            # Frontend client application logic
        ├── index.html        # UI dashboard & modals
        └── style.css         # Responsive dark-theme design system
```

---

## 🔌 API Overview

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/health` | Live connectivity status for LinkedIn, ChatGPT, Gmail, Infopark, and PostgreSQL |
| `GET` | `/api/stats` | Counters for Discovered, Pending, Drafts Ready, and Others |
| `GET` | `/api/scrapers` | List of registered website scrapers (`linkedin`, `infopark`, etc.) |
| `POST` | `/api/scrape` | Trigger scraper background task by source (`{"source": "linkedin"}`) |
| `GET` | `/api/posts` | Paginated & filtered job posts (`status`, `gen_status`, `source`, `min_exp`, etc.) |
| `POST` | `/api/posts/manual` | Manually ingest a raw job description |
| `POST` | `/api/posts/{id}/spam` | 1-click action to mark a post as Spam / Scam and move to Others |
| `POST` | `/api/posts/{id}/reject` | Cancel application with pre-made or custom reason comment |
| `POST` | `/api/posts/{id}/revert` | Restore a sent or cancelled post back to active drafts/discovered |
| `POST` | `/api/posts/{id}/mark-sent`| Mark application as sent with timestamp |
| `POST` | `/api/generate-batch` | Trigger ChatGPT email generation for selected post IDs |
| `POST` | `/api/open-gmail/{id}` | Launch headed Firefox with pre-filled Gmail compose & resume attached |
| `GET` | `/api/settings` | Retrieve active application configuration (DB + config.json) |
| `POST` | `/api/settings` | Update settings and persist `chatgpt_url` & `search_query` in PostgreSQL |

---

## 🤝 Adding New Website Scrapers

Adding a new scraper to Reach requires only 3 simple steps:
1. Create your scraper script in `scripts/your_scraper.py` using `src.db.upsert_post`.
2. Add a runner function in `src/automation_tasks.py`.
3. Register it in `SCRAPER_REGISTRY`:
   ```python
   SCRAPER_REGISTRY["indeed"] = {
       "id": "indeed",
       "name": "Indeed Jobs",
       "icon": "🌐",
       "description": "Scrapes today's software engineer postings on Indeed",
       "runner": run_indeed_scraper,
   }
   ```
The UI dropdown automatically discovers the new scraper and makes it available for 1-click crawling.

---

## 📄 License

Distributed under the MIT License.
