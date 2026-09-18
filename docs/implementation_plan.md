# LinkedIn Posts Search & Job Application Automation Plan

## Account Safety & Human Pacing Guidelines

1. **Browser Visibility**: Always run in headed mode (`headless=False`) using the persistent Firefox context (`~/.playwright_firefox_profile`).
2. **Keystroke and Click Delays**:
   - Random delays between 2.0s and 4.5s before taking navigation actions.
   - Smooth, incremental scrolling (300–600px at a time) with brief 1–2s pauses to mimic reading.
3. **Session Volume**:
   - Small batches (15–25 posts per run) to stay well under rate limits.
   - Immediate termination and prompt to the user if any security challenge, CAPTCHA, or verification request is encountered.
4. **No Password Storage**: Uses existing browser session cookies persisted locally on the machine.

---

## Workflow Overview

```text
LinkedIn Posts Search ("Full stack developer" hiring)
  → Natural scroll & discovery
  → Filter hiring posts (exclude #OpenToWork / job-seekers)
  → Expand full post text ("...see more")
  → Extract post URL, author, date, text, email, link
  → Pass to ChatGPT custom GPT conversation (raw JD only)
  → Capture generated email response
  → Save to persistence (SQLite / JSON)
  → Prepare for Gmail draft review
```

---

## Discovered LinkedIn Posts Search Structure

- **Target URL**:
  `https://www.linkedin.com/search/results/content/?keywords={encoded_query}&origin=GLOBAL_SEARCH_HEADER&sortBy=%22date_posted%22`
- **Filter**: Posts (`content`), sorted by latest / past week.
- **Feed Card Selectors**:
  - Main container: `div.feed-shared-update-v2` or `div[data-urn*="urn:li:activity"]`
  - Author link: `.update-components-actor__container a.app-aware-link`
  - Post text: `.feed-shared-update-v2__description-wrapper`, `span.break-words`
  - "See more" button: `button.feed-shared-inline-show-more-text__see-more-less-toggle`
  - Post direct URL: menu button or timestamp link `.update-components-actor__sub-description a`
