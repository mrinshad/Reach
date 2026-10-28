# Reach — Product Strategy & Architecture (PRODUCT.md)

This document outlines Reach's product mission, target audience, core capabilities, and brand voice.

---

## 1. Product Mission & Vision

**Reach** is an autonomous, open-source job discovery, screening, and outreach workstation. It bridges the gap between active job discovery and effective communication by automating tedious job searches, filtering out unsuitable roles, preparing customized application drafts via generative AI, and managing LinkedIn Easy Apply applications while maintaining strict safety, human pacing, and user oversight.

---

## 2. Target Audience

1. **Software Engineers & Technical Candidates**: Full-stack, backend, frontend, and systems engineers seeking high-efficiency discovery and outreach across multiple job boards and regional tech hubs.
2. **Proactive Job Seekers**: Candidates who want tailored, high-signal cold outreach to recruiters and engineering managers, avoiding generic mass-blasting.
3. **Power Users & Developers**: Users who value local-first privacy, persistent browser sessions without third-party credential storage, and total visibility over automated browser actions.

---

## 3. Core Feature Pillars

### A. Extensible Job Discovery Crawlers
- **Unified Crawler Registry**: Pluggable architecture allowing seamless addition of new crawlers (LinkedIn Posts, LinkedIn Easy Apply, Infopark Kochi, etc.).
- **Location-Targeted Scrapes**: Support for arbitrary city/region targeting (e.g., Bengaluru, Kochi, Pune, Dubai, London, New York).
- **Inactivity Watchdog**: 90-second safety watchdog terminating stuck sessions safely while preserving discovered records.

### B. Sequential FIFO Task Queue
- **Concurrency Protection**: Eliminates browser conflicts and 409 errors by serializing all automation tasks (scrapes, batch AI generations, Easy Apply cycles).
- **Real-Time Task Drawer**: Live terminal log streaming, position badges (`#1`, `#2`), and task cancellation controls.

### C. Generative AI Screening & Personalization
- **Web ChatGPT Custom GPT Integration**: Crafts personalized cold email pitches highlighting candidate tech stack, relevant experience, and problem-solving skills.
- **Automated Suitability Screening**: Identifies non-matching requirements (e.g. strict demographic or gender filters) and flags posts with clear explanations.

### D. Human Oversight & Review Workspace
- **Review Tab**: Natural-scroll candidate view for inspecting job descriptions side-by-side with generated email drafts.
- **On-Demand Generation**: `[ ✨ Generate Mail from JD ]` override allowing instant re-generation of outreach pitches.
- **Gmail Automation**: Automatic resume PDF attachment with 1-click headed review or background silent dispatch.

### E. LinkedIn Easy Apply Automation & Question Bank
- **Dedicated Easy Apply Workspace**: Automated multi-step application handling with 5-KPI ribbon (Ready, Screening, Applied, Failed, Not Found).
- **Screening Questionnaire Parser**: Detects and extracts custom modal questions (radios, dropdowns, text inputs, checkboxes).
- **Centralized Question & Answer Bank**: Persistent repository of candidate answers for recurring application questions.
- **Safe Pacing & Rate Limit Safeguard**: Automatic cooldown triggers when LinkedIn rate-limit warnings appear.

---

## 4. Voice & Communication Standards

- **Signal Over Noise**: Replace corporate marketing clichés with precise, factual information.
- **Safety-First**: Never compromise user account standing. Always respect platform limits and enforce polite human pacing delays.
- **Transparency**: Every automation step logs terminal output in real time so the user always understands what the system is executing.
