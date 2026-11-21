#!/usr/bin/env python3
"""
Inspect and harvest screening questions & options for Indeed jobs requiring questionnaires.
(scripts/inspect_indeed_questionnaires.py)
"""

import sys
import os
import json
import re

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from playwright.sync_api import sync_playwright
from src.services.firefox_connector import launch_firefox_context
from src.db.posts import get_post_by_id
from src.db.connection import get_connection

def inspect_questions_from_page(page):
    """
    Carefully inspects questions on an Indeed SmartApply modal or page.
    Returns a list of structured question dicts:
    {
        'prompt': str,
        'type': 'radio' | 'select' | 'text' | 'number' | 'textarea' | 'checkbox',
        'options': List[str],
        'required': bool,
    }
    """
    questions = []

    # Indeed questions are typically organized as fieldsets or question-item divs
    # First, let's find all top-level question blocks (fieldsets or div.ia-Questions-item that are not inside another ia-Questions-item)
    top_blocks = page.locator("fieldset, div.ia-Questions-item, div[data-testid*='question-']").all()

    seen_prompts = set()

    for block in top_blocks:
        try:
            # Check if this block is nested inside another block we already or will process
            # E.g. a div.ia-Questions-item that is just a radio option wrapper
            is_child_option = block.evaluate("""(el) => {
                // If it's inside a fieldset, and it's not the fieldset itself, it's an option item
                if (el.tagName !== 'FIELDSET' && el.closest('fieldset')) {
                    return true;
                }
                // If it only contains 1 radio or checkbox and 1 label that matches all text
                const inputs = el.querySelectorAll('input[type=\"radio\"], input[type=\"checkbox\"]');
                const labels = el.querySelectorAll('label');
                if (inputs.length === 1 && labels.length === 1) {
                    const text = el.innerText.trim();
                    const labelText = labels[0].innerText.trim();
                    if (text === labelText) return true;
                }
                return false;
            }""")

            if is_child_option:
                continue

            # Extract Question Prompt
            # Prefer legend, then aria-labelledby, then label or header
            prompt_data = block.evaluate("""(el) => {
                let prompt = '';
                // 1. Legend
                const legend = el.querySelector('legend');
                if (legend) {
                    prompt = legend.innerText;
                }
                // 2. Element with role=heading or class containing 'header' or 'title'
                if (!prompt) {
                    const hdr = el.querySelector('[class*=\"header\"], [class*=\"title\"], [class*=\"label\"], h2, h3, h4');
                    if (hdr && hdr.innerText.trim().length > 2) {
                        prompt = hdr.innerText;
                    }
                }
                // 3. Label not associated with a single radio
                if (!prompt) {
                    const labels = el.querySelectorAll('label');
                    for (let l of labels) {
                        const forId = l.getAttribute('for');
                        if (forId) {
                            const inp = document.getElementById(forId);
                            if (inp && (inp.type === 'radio' || inp.type === 'checkbox')) continue;
                        }
                        if (l.innerText.trim().length > 2) {
                            prompt = l.innerText;
                            break;
                        }
                    }
                }
                // Clean up prompt
                prompt = (prompt || '').replace(/\\s*\\*\\s*required/gi, '').replace(/\\s*\\*/g, '').trim();
                return prompt;
            }""")

            prompt = (prompt_data or "").strip()
            if not prompt or len(prompt) < 3:
                continue

            # Skip common non-questions
            low_p = prompt.lower()
            if low_p in ("contact information", "resume", "review your application", "terms", "qualification", "qualifications you may be missing"):
                continue

            norm_p = re.sub(r"[^a-zA-Z0-9]+", "", low_p)
            if norm_p in seen_prompts:
                continue
            seen_prompts.add(norm_p)

            # Check input type & options
            # 1. Radio buttons
            radios = block.locator("input[type='radio']").all()
            if radios:
                options = []
                for r in radios:
                    r_id = r.get_attribute("id") or ""
                    r_lbl = block.locator(f"label[for='{r_id}']").first if r_id else None
                    val = (r_lbl.inner_text() if r_lbl and r_lbl.count() > 0 else r.get_attribute("value") or "").strip()
                    if val and val not in options:
                        options.append(val)
                questions.append({
                    "prompt": prompt,
                    "type": "radio",
                    "options": options,
                })
                continue

            # 2. Select dropdown
            sel = block.locator("select").first
            if sel.count() > 0:
                options = []
                for opt in sel.locator("option").all():
                    val = opt.inner_text().strip()
                    if val and val.lower() not in ("select an option", "select", "choose", "-- select --", ""):
                        options.append(val)
                questions.append({
                    "prompt": prompt,
                    "type": "select",
                    "options": options,
                })
                continue

            # 3. Checkboxes
            checkboxes = block.locator("input[type='checkbox']").all()
            if checkboxes:
                options = []
                for cb in checkboxes:
                    cb_id = cb.get_attribute("id") or ""
                    cb_lbl = block.locator(f"label[for='{cb_id}']").first if cb_id else None
                    val = (cb_lbl.inner_text() if cb_lbl and cb_lbl.count() > 0 else cb.get_attribute("value") or "").strip()
                    if val and val not in options:
                        options.append(val)
                questions.append({
                    "prompt": prompt,
                    "type": "checkbox",
                    "options": options,
                })
                continue

            # 4. Textarea
            ta = block.locator("textarea").first
            if ta.count() > 0:
                questions.append({
                    "prompt": prompt,
                    "type": "textarea",
                    "options": [],
                })
                continue

            # 5. Text / Number input
            inp = block.locator("input[type='text'], input[type='number']").first
            if inp.count() > 0:
                inp_type = inp.get_attribute("type") or "text"
                questions.append({
                    "prompt": prompt,
                    "type": inp_type,
                    "options": [],
                })
                continue

        except Exception as e:
            print(f"  Error inspecting block: {e}")

    return questions

def inspect_job_wizard(context, post_id, post_url, company, title):
    print(f"\n=======================================================")
    print(f"Inspecting Questionnaire: {title} @ {company}")
    print(f"URL: {post_url}")
    print(f"=======================================================")

    page = context.new_page()
    all_discovered_questions = []

    try:
        page.goto(post_url, timeout=30000, wait_until="domcontentloaded")
        page.wait_for_timeout(3000)

        # Check for Apply button
        apply_btn = page.locator("button[id*='indeedApplyButton'], button:has-text('Apply now'), a:has-text('Apply now')").first
        if apply_btn.count() == 0 or not apply_btn.is_visible():
            print("  ✕ 'Apply now' button not found or already applied.")
            page.close()
            return []

        # Click apply
        try:
            with page.expect_popup(timeout=8000) as popup_info:
                apply_btn.click(force=True)
            target_page = popup_info.value
            target_page.wait_for_load_state("domcontentloaded", timeout=15000)
        except Exception:
            target_page = page

        # Step through wizard until review or submit
        for step in range(1, 8):
            target_page.wait_for_timeout(3000)
            url = target_page.url.lower()

            # Bypass tailoring
            tailor_btn = target_page.locator("button:has-text('Continue without tailoring'), button:text-is('Skip'), button:has-text('No thanks')").first
            if tailor_btn.count() > 0 and tailor_btn.is_visible() and "skip to main" not in tailor_btn.inner_text().lower():
                print("  [Wizard] Bypassing tailoring suggestion...")
                tailor_btn.click(force=True)
                target_page.wait_for_timeout(3000)
                continue

            # Bypass qualification warning
            cont_anyway_btn = target_page.locator("button:has-text('Continue anyway'), button:has-text('Apply anyway')").first
            if cont_anyway_btn.count() > 0 and cont_anyway_btn.is_visible():
                print("  [Wizard] Bypassing qualification warning ('Continue anyway')...")
                cont_anyway_btn.click(force=True)
                target_page.wait_for_timeout(3000)
                continue

            # Inspect questions on this screen
            qs = inspect_questions_from_page(target_page)
            if qs:
                print(f"  [Step {step}] Found {len(qs)} questions:")
                for q in qs:
                    print(f"    • Prompt: {q['prompt']}")
                    print(f"      Type:   {q['type']}")
                    print(f"      Options: {q['options']}")
                    all_discovered_questions.append(q)

            if "review-module" in url or target_page.locator("button[data-testid*='submit']:visible").count() > 0:
                print("  [Step] Reached Review screen.")
                break

            # Advance
            adv_btn = target_page.locator("button[data-testid='continue-button']:visible, button:not([data-testid*='hp']):has-text('Continue'):visible").first
            if adv_btn.count() > 0 and adv_btn.is_visible():
                print("  Advancing wizard...")
                adv_btn.click(force=True)
                target_page.wait_for_timeout(3000)
            else:
                break

    except Exception as e:
        print(f"  Error during wizard inspection: {e}")
    finally:
        try:
            page.close()
        except Exception:
            pass

    return all_discovered_questions

def main():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, author_name, author_headline, post_url
        FROM posts
        WHERE category = 'INDEED_APPLY' AND status = 'REQUIRES_QUESTIONNAIRE'
        ORDER BY id;
    """)
    jobs = cur.fetchall()
    conn.close()

    print(f"Loaded {len(jobs)} Indeed jobs requiring questionnaires.")

    all_results = {}
    with sync_playwright() as playwright:
        context = launch_firefox_context(playwright, headless=True, sync_cookies_domains=["indeed.com"])

        for j in jobs:
            post_id, company, title, post_url = j
            qs = inspect_job_wizard(context, post_id, post_url, company, title)
            all_results[post_id] = {
                "company": company,
                "title": title,
                "url": post_url,
                "questions": qs,
            }

        try:
            context.close()
        except Exception:
            pass

    with open("scripts/indeed_questionnaires_inspected.json", "w") as f:
        json.dump(all_results, f, indent=2)

    print("\nSaved all inspected questions to scripts/indeed_questionnaires_inspected.json")

if __name__ == "__main__":
    main()
