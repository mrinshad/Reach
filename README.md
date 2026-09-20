# ⚡ Reach — Autonomous Job Outreach & Application Hub

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=flat&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-009688?style=flat&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Playwright](https://img.shields.io/badge/Playwright-Firefox-2EAD33?style=flat&logo=playwright&logoColor=white)](https://playwright.dev/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Database-336791?style=flat&logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![Responsive](https://img.shields.io/badge/UI-Mobile%20%26%20Desktop-6366F1?style=flat)](#-mobile-access)
[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

**Reach** is a comprehensive, open-source job discovery, AI-assisted screening, and automated cold outreach suite. It aggregates job opportunities from multiple platforms (LinkedIn feed crawlers and tech park portals like Infopark Kochi), utilizes custom ChatGPT models to craft tailored cold emails, screens out unsuitable criteria (e.g. strict demographic or gender requirements), and automates Gmail dispatch with your resume pre-attached in either visible window or silent background mode.

---

## ✨ Core Highlights & Features

### 1. 🌐 Extensible Crawler Registry & Unified Source Selector
- **Unified Crawler Interface**: A single consolidated **Source Selector** and **Crawl Button** (`[ 💼 LinkedIn Posts ▾ ] [ Location ▾ ] [ ⚡ Crawl ]`) controls all crawling operations.
- **Pluggable Registry (`SCRAPER_REGISTRY`)**: Add new website crawlers (e.g. Indeed, Technopark, Naukri, YC Jobs) in one backend step without touching frontend markup.
- **Location-Targeted Scrapes**: Full support for geographic keyword targeting (e.g., Bengaluru, Kochi, Pune, Dubai, New York, London, Singapore).
- **90-Second Inactivity Watchdog**: All crawlers are monitored by an automated inactivity watchdog. If network or scraping halts for 90 seconds, the browser context closes cleanly while safely committing all discovered leads to PostgreSQL.
- **Opportunity-First Ingestion**: Crawlers preserve job postings across tech stacks rather than rejecting them outright, empowering candidates to pitch their versatile full-stack experience for upcoming or alternative roles.

### 2. 📋 Centralized Sequential FIFO Task Queue
- **Thread-Safe Task Engine**: Eliminates `409 Conflict` errors during concurrent triggers. Consecutive operations (e.g., scraping Bangalore, then Kochi, then Pune, followed by batch AI email generation) are enqueued in FIFO order and executed sequentially in the browser.
- **Live Queue Drawer**: Real-time queue manager displaying upcoming tasks with position badges (`#1`, `#2`), task titles, individual cancel buttons (`/api/tasks/queue/cancel/{id}`), and a 1-click **Clear Queue** option.
- **Grace Transition Pacing**: Polite 2.5-second cooldown delay between queued tasks to commit database transactions, register summary stats, and update dashboard counters.

### 3. 📬 Direct Opportunity Cold Outreach
- **Proactive Recruiter Outreach**: Send tailored opportunity pitches directly to hiring managers and recruiters even without an existing scraped post.
- **Automated Opportunity Template**: Pre-fills a professional Full-Stack Software Engineer template highlighting key technologies, problem-solving skills, and attached resume.
- **Full Database Tracking**: Dispatched cold emails are automatically ingested into PostgreSQL (`posts` table with source `'Direct Outreach'`) and archived under **Sent & History**.

### 4. 🔔 Multi-Channel Notification Center
- **In-App Activity Dropdown**: Persistent topbar bell button with unread counter badge and timestamped activity log.
- **Audio Chimes & Native Desktop Alerts**: Subtle Web Audio API chime sounds on task completion or failure, with optional native OS desktop notification permissions.

### 5. 🎨 Collapsible Icon-Only Sidebar & Fluid Canvas
- **Icon-Only Collapsed Mode (68px)**: Collapsed by default for maximum screen real estate with smooth cubic-bezier open/close animations.
- **Expandable Full Mode (270px)**: Click toggle button or logo to expand sidebar with full labels, system diagnostics, and quick controls.
- **Fluid Canvas Architecture**: Synchronized layout transitions (`calc(100% - 68px)` vs `calc(100% - 270px)`) preventing horizontal content shift or table distortion.
- **Crisp SVG Vector Icons**: 100% scalable vector SVGs replace legacy emojis and text icons across the entire platform.

### 6. 🎛️ Headless Browser Mode On/Off Switch
- **Flexible Automation Visibility**: Toggle seamlessly between **Headless Mode** (silent background automation with zero window popups) and **Headed Mode** (visible window for live monitoring and debugging).
- **Persistent Database Configuration**: Stored in PostgreSQL `settings.headless_mode` and respected across all Playwright contexts and scraper subprocesses.
- **1-Click Quick Toggle**: Instant toggle button in the sidebar footer and an iOS-style switch inside the **Settings** modal.

### 7. 🛡️ Intelligent Anti-Spam & Fraud Protection
- **Reported Scam Domain Auto-Rejection**: Automatically rejects incoming job posts whose contact email domains have previously been reported as scam/spam, with a clear rejection reason.
- **Reported Email Blacklist**: Rejects any incoming contact email explicitly flagged as scam/spam, regardless of provider.
- **Mainstream Provider Exemption**: Mainstream email providers (`gmail.com`, `yahoo.com`, `hotmail.com`, `outlook.com`, `icloud.com`, `proton.me`, etc.) are exempt from domain-level rejections to prevent false positives.
- **Scam & Potential Scam Badges with Tooltips**: Flagged posts display actionable hover tooltips explaining the reason, and detail cards when clicking "View".
- **1-Click Spam Marking**: Instantly flag any job post as spam/scam directly from the Discovered feed or Review workspace (`🚫 Spam`).

### 8. 🗂️ 3-Stage Application Lifecycle
- **Discovered Posts**: Raw incoming job descriptions with recruiter contact details, experience level pills, multi-column sorting, and multi-source badges (`LinkedIn`, `Infopark Kochi`, `Manual`, `Direct Outreach`).
- **Review & Drafts**: Side-by-side workspace displaying the original job post against the ChatGPT-generated email draft, with live editing and resume attachment validation.
- **Sent & History**: Unified chronological archive of all `Sent` applications and `Cancelled` / `Discarded` posts. Clicking any card opens full details, cancellation reasons, and sent email bodies, with 1-click **Restore**.

### 9. ⚡ Dynamic Cancellation Reasons & Header Sorting
- **1-Click Rejection Chips**: Rapidly reject posts with pre-made criteria chips (`⚠️ Not enough experience`, `🚫 Not a job / Promotional`, `👩 Female candidates only`, `⚡ Irrelevant tech stack`, `💰 Unrealistic / Low budget`, `🗑️ Spam / Duplicate`).
- **Database-Driven Reason Counts**: Dropdowns load dynamic rejection reasons with live post counts (`GET /api/reasons`).
- **Reason Truncation**: Rejection reasons are cleanly truncated (48 chars / 8 words + ellipsis) for clean presentation.
- **Interactive Header Sorting**: Neutral sort indicators (`↕`) on table columns turn into active directional indicators (`↑`, `↓`) on click.
- **Relative Time Formatting**: Timestamps display intuitive relative labels (`2 hrs`, `30 mins`).

### 10. 💎 Zero Token Wastage & Pure Crawling (No Third-Party APIs)
- **100% Free & Unlimited**: Zero OpenAI or Anthropic API token billing, zero proxy network bills, and zero third-party scraping subscriptions.
- **Pure Browser Crawling**: Uses Playwright Firefox for direct, high-fidelity crawling on LinkedIn, Infopark, and other job portals.
- **Automated Web ChatGPT**: Directly orchestrates your existing logged-in ChatGPT conversation or Custom GPT in the browser. You get state-of-the-art AI generation with custom conversational memory without paying a cent in API tokens.

### 11. 🚀 Direct & 1-Click Batch Email Outreach (No Manual Clicking)
- **Direct Dispatch**: Send email applications directly through Gmail in the browser without manual clicking — your active resume is automatically attached and the email is dispatched via Gmail keyboard shortcuts/buttons.
- **Multi-Draft Batch Sending**: Check multiple drafts in Review & Drafts or click "Select All" to dispatch emails across multiple candidates in a single browser session with polite randomized delays (4–8s) to safeguard email reputation.
- **Manual Review When Needed**: The `👁️ Open in Gmail` option remains available for interactive inspection.
- **1-Click Copy**: Built-in copy buttons on top-right corners of both the Job Description (JD) and Outreach Email Draft for instant clipboard copy.

### 12. 📊 Real-Time Analytics & Trends Dashboard (Default Home)
- **Analytics as Home**: Launch directly into rich visualizations of your outreach pipeline, lead conversion, and scraping activity.
- **Tab State Persistence**: Navigating between tabs or reloading the page preserves your exact active tab via `localStorage` and hash routing (`#analytics`, `#discovered`, `#review`, `#sent`).
- **Accurate Real-Time Metrics**: High-impact top summary bar tracking `🚀 Applied`, `✉️ Drafts Ready`, `🎯 Outreach Ready`, and `🕸️ Total Sourced`.
- **Jobs Applied Each Day**: Smooth interactive line graph tracking daily application velocity over time.
- **Scraping Inflow Activity**: Daily volume comparisons of newly discovered leads.
- **Application Status Distribution**: Donut charts detailing conversion stages (`Applied / Sent`, `Drafts Ready`, `Discovered`, `Screened Out`).
- **Scraping Sources Breakdown**: Relative performance of LinkedIn vs Infopark vs Manual entry vs Direct Outreach.
- **Cancellation & Spam Analysis**: Visual frequency ranking of rejection reasons (unsuitable criteria, scams, irrelevant tech stack).
- **Timeframe Filtering**: Instantly toggle between `7 Days`, `14 Days`, `30 Days`, and `All Time` with database-first aggregation.

---

## 🏗️ Architecture

```mermaid
flowchart TD
    subgraph Sourcing ["1. Sourcing & Aggregation"]
        A["LinkedIn Posts Crawler"]
        B["Infopark Kochi Scraper"]
        C["Manual JD Ingestion"]
        D["Direct Cold Outreach Modal"]
        A --> QUEUE{"FIFO Task Queue"}
        B --> QUEUE
        C --> DB[("PostgreSQL Database\n(posts, settings)")]
        D --> QUEUE
        QUEUE --> REG["Crawler Registry\n(90s Inactivity Watchdog)"]
        REG --> DB
    end

    subgraph Screening ["2. AI Screening & Outreach"]
        DB --> QUEUE
        QUEUE --> E["ChatGPT Automation (Custom GPT)"]
        E -- Tailored Draft --> DB
        E -- Unsuitable Criteria --> REJ["Auto-Reject & Tag"]
        REJ --> DB
    end

    subgraph BrowserEngine ["3. Playwright Automation Engine"]
        F["Playwright Firefox Context"]
        G{"Headless Switch\n(True / False)"}
        G --> F
    end

    subgraph Dispatch ["4. Application Outreach & Review"]
        DB --> H["Discovered Feed"]
        DB --> I["Review & Drafts"]
        DB --> J["Sent & History Archive"]
        I --> QUEUE
        QUEUE --> F
        F --> K["Gmail Automation (Direct Send / Compose)"]
        K -- Sent Confirmation --> DB
    end

    subgraph Intelligence ["5. Intelligence & UI"]
        DB --> L["Real-Time Analytics Dashboard"]
        QUEUE --> M["Multi-Channel Notification Center"]
    end
```

---

## 🔒 Security & Privacy

This codebase is configured to be **safe to open-source**:
- **No Stored Passwords**: Reach uses your existing logged-in browser sessions stored locally in Firefox (`~/.playwright_firefox_profile`).
- **Zero Exposed Keys & Personal Paths**: No user home directories, personal resume files, or private ChatGPT conversation UUIDs are tracked in git.
- **Flexible Headless / Headed Automation**: Toggle seamlessly between silent background execution (`headless=True`) for zero UI interruption and visible window mode (`headless=False`) for live monitoring and debugging.
- **Database Isolation**: Application configuration and settings are stored locally in your private PostgreSQL instance.

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

## 🔐 Session Authentication & ChatGPT Setup Guide

Reach operates through **pure browser session automation** without requiring paid third-party APIs or exposing personal tokens. Follow these two quick one-time setup steps:

### Step 1: One-Time Browser Authentication (LinkedIn & Gmail)

Reach stores persistent session cookies locally in your private Firefox profile at `~/.playwright_firefox_profile`. Log into your LinkedIn and Gmail accounts once:

```bash
# Launch headed Firefox to log into LinkedIn & Gmail
python3 -c "
from playwright.sync_api import sync_playwright
import os

profile_dir = os.path.expanduser('~/.playwright_firefox_profile')
with sync_playwright() as p:
    browser = p.firefox.launch_persistent_context(user_data_dir=profile_dir, headless=False)
    page = browser.new_page()
    page.goto('https://www.linkedin.com/login')
    print('👉 Please log into LinkedIn and Gmail in the opened browser window.')
    input('Press Enter in this terminal after you have logged in: ')
    browser.close()
    print('✓ Browser session saved successfully.')
"
```
Once authenticated, your session cookies remain cached in your local profile, enabling autonomous crawling and Gmail draft preparation.

---

### Step 2: Set Up & Train Your ChatGPT Chat / Custom GPT

To achieve high-quality cold email generation, automated suitability screening, and zero token costs, train a persistent ChatGPT conversation thread or Custom GPT.

#### 1. Open ChatGPT
Navigate to [chatgpt.com](https://chatgpt.com) and start a new chat (or create a Custom GPT).

#### 2. Provide the General-Purpose Behavior Prompt
Paste the following exact system instructions:

```text
Act as a job-application assistant. Whenever I send a job description or recruiter post, first determine whether it is relevant.

🟢 Suitable job → Write a concise application email directly, tailored to the role. Never invent experience. Handle skill/experience gaps honestly without making them the focus.

🟡 Unwanted role → If the role is in a category I’ve indicated I don’t want (e.g. QA, support, operations, etc.), don’t apply for that role. Instead, write a short email explaining that my background is better aligned with my preferred areas and ask whether they have relevant current/upcoming openings.

🔴 Clearly unsuitable → Output exactly:
UNSUITABLE_JD - ❌ Not suitable — {reason}

Keep the {reason} concise — maximum 5-7 words (e.g. "HR role, MBA required", "10+ years specialized HVAC", "Sales only role"). Do not write sentences or paragraphs.

Use this for hard eligibility/location/work-authorization restrictions, clearly excessive experience requirements, explicit eligibility restrictions, completely unrelated roles, or consultant/vendor hotlists that are marketing available consultants rather than actually hiring candidates.

For consultant/hotlist posts, distinguish between an actual job opening and a recruiter/vendor looking for clients or referrals. Treat the latter as unsuitable.

For international/US roles, never assume or invent work authorization, location, or eligibility. If the role has a possible remote/local alternative, mention that appropriately.

Email style: concise, natural, professional, confident, and human. Avoid generic/AI-sounding or overly corporate language, desperation, excessive flattery, and unnecessary detail. Tailor the email to the JD and highlight genuinely relevant experience.

Always include:
To:
Subject:
Email body

Regards,
[Candidate name]
[Phone]
[Email]

Use actual blank lines between paragraphs. By default, when a JD is provided, generate the email without asking what the user wants. Only generate a cover letter when explicitly requested.

For unwanted but potentially relevant companies, redirect toward the candidate’s preferred job categories rather than simply rejecting the company. For example, ask about Frontend, Backend, Full Stack, DevOps, Cloud, Software Engineering, or other preferred technical roles.

Do not add explanations outside the requested output unless the user asks for them.
```

#### 3. Provide Your Candidate Profile Details
Directly alongside or following the prompt above, supply your personal profile using this structured checklist:

```text
Candidate knowledge to learn:

- Professional background: current role, previous roles, total years of experience, and main areas of expertise.
- Technical skills: strongest/current technologies, frameworks, databases, cloud/DevOps tools, and any technologies with only previous/basic experience.
- Major projects: important projects, responsibilities, domains, and technologies actually used.
- Preferred roles: the types of jobs the candidate wants to apply for.
- Unwanted roles: roles the candidate does not want, such as QA, support, sales, etc.
- Location & relocation: current country/city and whether they are willing to relocate.
- Work authorization: visa/work authorization status, especially for international/US roles.
- Employment preferences: remote, hybrid, onsite, full-time, contract, etc.
- Career direction: what kind of work the candidate wants to move toward and what they want to avoid.
- Application writing preferences: preferred tone, length, structure, and anything they specifically dislike in application emails.
- Hard constraints: experience limits, location restrictions, salary expectations, notice period, education/eligibility requirements, or other conditions that can make a job unsuitable.
```

#### 4. Save the Conversation Link in Reach
1. Copy the full browser URL of this ChatGPT conversation thread (e.g., `https://chatgpt.com/c/your-chat-id` or `https://chatgpt.com/g/g-your-custom-gpt`).
2. In Reach, click the ⚙️ **Settings** icon in the sidebar or topbar.
3. Paste the URL into **ChatGPT Custom GPT Chat Link** and click **Save Settings**.
4. The URL is saved permanently in your PostgreSQL `settings` table and used automatically for all batch email generation.

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
  Automation Mode: Configurable (Headed / Headless Switch)
======================================================================
```

- **Desktop**: Open [http://localhost:8000](http://localhost:8000)
- **Mobile / Smartphone**: Connect to the same local Wi-Fi and open the Phone URL to manage applications on mobile.

---

## 📱 Mobile Access

Reach features a dedicated mobile responsive design tested across phone and tablet viewports (`<= 768px` and `<= 480px`):
- **Off-Canvas Navigation Drawer**: The sidebar transforms into a full-height slide-out drawer with a blurred backdrop overlay and auto-closes on tab selection.
- **Touch-Optimized Cards**: Table views transform into touch-friendly cards displaying recruiter name, source badge, experience pills, contact email, and one-tap action buttons.
- **Two-Tier Filter Toolbar**: Sticky, wrap-safe filter dropdowns and 1-tap Clear Filters button.
- **Single-Column Split Workspace**: Side-by-side Review & Drafts smoothly stacks on mobile for comfortable vertical scrolling and editing.
- **Mobile Modals**: Full-width touch dialogs for direct opportunity outreach, settings, and job details.

---

## 📂 Project Structure & Modular Architecture

Reach utilizes a component-based frontend architecture with modular CSS stylesheets, HTML partials, and hierarchical `AGENTS.md` routing maps designed for AI pair-programming efficiency:

```text
reach-job-automation/
├── AGENTS.md                 # Primary Agent navigation map & feature routing matrix
├── .agents/
│   └── rules/
│       └── codebase_map.md   # Antigravity hierarchical workspace rule
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
│   ├── linkedin_posts_search.py      # LinkedIn feed scraper with watchdog
│   ├── infopark_jobs_search.py       # Infopark Kochi portal scraper
│   ├── process_posts_with_chatgpt.py # Batch ChatGPT generator
│   └── prepare_gmail_draft.py        # Gmail compose launcher
└── src/
    ├── AGENTS.md             # Backend & automation navigation guide
    ├── app.py                # FastAPI endpoints, REST API & dynamic template assembly
    ├── automation_tasks.py   # FIFO task queue manager & scraper registry
    ├── chatgpt_service.py    # ChatGPT prompt & generation logic
    ├── config.py             # Database-backed configuration & headless helper
    ├── db.py                 # PostgreSQL client, settings, & anti-spam filters
    ├── experience_extractor.py # YOE & seniority parsing
    ├── firefox_connector.py  # Headed / Headless Playwright Firefox context
    ├── gmail_service.py      # Gmail draft preparation & direct send
    ├── health_service.py     # Live session health checks
    └── static/
        ├── AGENTS.md         # Frontend DOM elements & JS router
        ├── app.js            # Frontend client application logic & state
        ├── index_layout.html # Master layout with component include markers
        ├── index.html        # Auto-synchronized complete single-page HTML
        ├── sw.js             # Root-scoped Service Worker for web push alerts
        ├── style.css         # Master manifest importing modular stylesheets
        ├── css/
        │   ├── AGENTS.md     # CSS selector, tokens & class index
        │   ├── variables.css # Design tokens, colors, typography, border radii
        │   ├── base.css      # Resets, base typography, buttons, badges, skeleton
        │   ├── layout.css    # 100vh app shell, topbar, notification dropdown
        │   ├── sidebar.css   # Collapsible sidebar, 44x44 icons, crawler selector
        │   ├── dashboard.css # Analytics KPI cards, charts, headless toggle switch
        │   ├── discovered.css# 2-tier search toolbar, data table, pagination
        │   ├── review.css    # Review queue, candidate card, JD mail button, draft editor
        │   ├── history.css   # Sent/cancelled tables, cancellation pills
        │   ├── tasks.css     # Task drawer, progress bar, terminal stream log
        │   ├── modals.css    # Pinned modal dialogs, diagnostics & toasts
        │   └── responsive.css# Mobile drawer, compact headers & touch styles
        └── partials/
            ├── sidebar.html        # Left navigation sidebar component
            ├── topbar.html         # Header topbar component
            ├── task_drawer.html    # Live task drawer component
            ├── tab_analytics.html  # Dashboard overview tab component
            ├── tab_discovered.html # Discovered jobs tab component
            ├── tab_review.html     # Review & drafts workspace tab component
            ├── tab_sent.html       # Outreach history tab component
            └── modals.html         # All 7 dialog modals & alert dialogs
```

---

## 🔌 API Overview

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/health` | Live connectivity status for LinkedIn, ChatGPT, Gmail, Infopark, and PostgreSQL |
| `GET` | `/api/stats` | Top-bar summary counters (`applied`, `drafts_ready`, `pending`, `total_sourced`) |
| `GET` | `/api/analytics` | Aggregated metrics, velocity timeline, conversion stages, and rejection breakdown |
| `GET` | `/api/notifications` | Active in-app notification center activity feed |
| `GET` | `/api/scrapers` | List of registered website scrapers (`linkedin`, `infopark`, etc.) |
| `POST` | `/api/scrape` | Enqueue scraper background task by source with optional query and location |
| `POST` | `/api/scrape/linkedin` | Enqueue LinkedIn feed crawler with optional location |
| `POST` | `/api/scrape/infopark` | Enqueue Infopark Kochi crawler |
| `GET` | `/api/tasks/status` | Real-time task execution state, log stream, and pending FIFO queue summary |
| `POST` | `/api/tasks/clear` | Reset active task status to idle |
| `POST` | `/api/tasks/queue/cancel/{id}` | Cancel a specific pending task from the sequential queue |
| `POST` | `/api/tasks/queue/clear` | Clear all pending tasks from the sequential queue |
| `GET` | `/api/posts` | Paginated & filtered job posts (`status`, `gen_status`, `source`, `location`, `sort_by`, etc.) |
| `GET` | `/api/posts/{id}` | Retrieve full details of a single job post |
| `PUT` | `/api/posts/{id}` | Update job post attributes (subject, body, email, company, notes) |
| `POST` | `/api/posts/manual` | Manually ingest a raw job description |
| `POST` | `/api/direct-outreach` | Direct opportunity cold outreach with DB tracking and automated Gmail dispatch |
| `POST` | `/api/posts/{id}/move-to-review` | Move a post to Review & Drafts workspace |
| `POST` | `/api/posts/{id}/spam` | 1-click action to mark a post as Spam / Scam and archive in Sent & History |
| `POST` | `/api/posts/{id}/reject` | Cancel application with pre-made chip or custom reason |
| `POST` | `/api/posts/{id}/revert` | Restore a sent or cancelled post back to active drafts/discovered |
| `POST` | `/api/posts/{id}/mark-sent`| Mark application as sent with timestamp |
| `GET` | `/api/reasons` | Dynamic list of cancellation/rejection reasons with real-time post counts |
| `GET` | `/api/locations` | Distinct job locations present across discovered posts |
| `GET` | `/sw.js` | Root-scoped Service Worker for mobile browser notifications |
| `POST` | `/api/generate-email/{id}` | Enqueue ChatGPT email generation for a post (supports `?force=true` override) |
| `POST` | `/api/generate-batch` | Enqueue ChatGPT email generation for selected post IDs |
| `POST` | `/api/open-gmail/{id}` | Enqueue opening Gmail compose with resume attached in Playwright Firefox |
| `POST` | `/api/send-direct/{id}` | Enqueue direct email dispatch via Gmail without manual clicking |
| `POST` | `/api/send-batch` | Enqueue batch direct dispatch across selected drafts sequentially |
| `POST` | `/api/resume/upload` | Upload and activate replacement resume PDF |
| `GET` | `/api/settings` | Retrieve active application configuration (DB + config.json) |
| `POST` | `/api/settings` | Update configuration (`chatgpt_url`, `search_query`, `headless_mode`) |
| `POST` | `/api/settings/headless` | 1-click toggle between Headless Mode and Headed Mode |

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
