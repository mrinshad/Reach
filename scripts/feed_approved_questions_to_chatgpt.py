#!/usr/bin/env python3
"""
Feed Approved Screening Questions & Answers Back to ChatGPT Custom GPT
(scripts/feed_approved_questions_to_chatgpt.py)

Fetches all screening questions that were generated/flagged and have now been
verified and approved as ANSWERED in the PostgreSQL screening_questions table.
Sends them back to the active ChatGPT Custom GPT conversation in batches of 50.
"""

import sys
import os
import time
import argparse
from typing import List, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from playwright.sync_api import sync_playwright
from src.db.connection import get_connection
from src.db.question_bank import normalize_question_key
from src.services.firefox_connector import launch_firefox_context
from src.services.chatgpt_service import (
    get_chatgpt_question_url,
    navigate_to_conversation,
    dismiss_chatgpt_overlays,
    PROMPT_BOX_SELECTOR,
    SEND_BTN_SELECTOR,
)


def get_approved_qa_pairs() -> List[Tuple[str, str]]:
    """Retrieve all approved questions and answers that originated from the AI / review list."""
    # 1. Read artifact order if available
    artifact_path = os.path.expanduser("~/.gemini/antigravity-cli/brain/fbedb7c7-463d-42ec-8342-53e242bec788/chatgpt-batch-answered-questions.md")
    artifact_order = []
    if os.path.exists(artifact_path):
        with open(artifact_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("| **"):
                    parts = [p.strip() for p in line.split("|")]
                    if len(parts) >= 6:
                        artifact_order.append(parts[2])

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT question_text, answer, question_key, updated_at
        FROM screening_questions
        WHERE status = 'ANSWERED' AND answer IS NOT NULL AND answer != '';
    """)
    db_answered = {r[2]: (r[0], r[1], r[3]) for r in cur.fetchall()}

    matched = []
    seen_keys = set()
    for q in artifact_order:
        k = normalize_question_key(q)
        if k in db_answered and k not in seen_keys:
            q_text, ans, _ = db_answered[k]
            matched.append((q_text, ans))
            seen_keys.add(k)

    # Include any additional questions answered recently
    cur.execute("""
        SELECT question_text, answer, question_key
        FROM screening_questions
        WHERE status = 'ANSWERED' AND answer IS NOT NULL AND answer != ''
          AND updated_at >= '2026-10-28 16:00:00'
        ORDER BY updated_at ASC;
    """)
    for r in cur.fetchall():
        if r[2] not in seen_keys:
            matched.append((r[0], r[1]))
            seen_keys.add(r[2])

    cur.close()
    conn.close()
    return matched


def format_batch_prompt(pairs: List[Tuple[str, str]], batch_num: int, total_batches: int, start_idx: int) -> str:
    """Format a list of QA pairs into a structured instruction prompt for ChatGPT."""
    header = (
        f"Please learn, memorize, and update your profile memory and knowledge base with these verified screening questions and answers "
        f"(Batch {batch_num} of {total_batches}: Questions {start_idx} to {start_idx + len(pairs) - 1}).\n"
        f"Whenever you encounter any of these screening questions (or similar phrasing) in future job applications, always answer with the exact verified answer provided below:\n\n"
    )
    items = []
    for i, (q, a) in enumerate(pairs, start=start_idx):
        items.append(f"{i}. Q: {q}\nA: {a}")
    return header + "\n\n".join(items)


def send_prompt_to_chatgpt(page, prompt_text: str, max_wait: int = 90) -> str:
    """Send a large prompt to ChatGPT and wait for streaming completion."""
    dismiss_chatgpt_overlays(page)
    page.wait_for_selector(PROMPT_BOX_SELECTOR, timeout=15000)
    prompt_box = page.locator(PROMPT_BOX_SELECTOR).first

    # Count existing assistant messages to identify new response
    ASSISTANT_SELECTOR = "[data-markdown-text-style='assistant-message'], [data-message-author-role='assistant'], article"
    existing_count = page.locator(ASSISTANT_SELECTOR).count()

    # Fill prompt box
    try:
        page.evaluate(
            """({sel, text}) => {
                const el = document.querySelector(sel);
                if (!el) return false;
                el.focus();
                document.execCommand('selectAll', false, null);
                document.execCommand('insertText', false, text);
                el.dispatchEvent(new Event('input', { bubbles: true }));
                el.dispatchEvent(new Event('change', { bubbles: true }));
                return true;
            }""",
            {"sel": PROMPT_BOX_SELECTOR, "text": prompt_text.strip()}
        )
    except Exception as e:
        print(f"  Warning during execCommand: {e}")
        prompt_box.fill(prompt_text.strip())

    page.wait_for_timeout(1000)

    # Click send button
    sent = False
    start_btn = time.time()
    while time.time() - start_btn < 6:
        btn = page.locator(SEND_BTN_SELECTOR).first
        if btn.count() > 0 and btn.is_visible():
            try:
                disabled = btn.evaluate("el => el.disabled || el.getAttribute('aria-disabled') === 'true'")
                if not disabled:
                    btn.click(timeout=3000)
                    sent = True
                    break
            except Exception:
                pass
        time.sleep(0.4)

    if not sent:
        print("  Send button not ready, pressing Enter fallback...")
        prompt_box.focus()
        page.keyboard.press("Enter")

    print("  Prompt sent! Waiting for ChatGPT response streaming...")
    time.sleep(3)

    # Wait for response streaming to finish
    elapsed = 0
    while elapsed < max_wait:
        time.sleep(2)
        elapsed += 2

        if page.is_closed():
            return "(Page closed)"

        try:
            # Check if stop button is active
            stop_btn = page.locator("button[aria-label*='Stop' i], button[data-testid='stop-button']")
            if stop_btn.count() > 0 and stop_btn.first.is_visible():
                continue
        except Exception:
            pass

        try:
            # Check if new assistant message is present and non-empty
            new_msgs = page.locator(ASSISTANT_SELECTOR)
            if new_msgs.count() > existing_count or new_msgs.count() > 0:
                last_msg = new_msgs.last
                text = last_msg.inner_text().strip()
                if len(text) > 10:
                    time.sleep(2)
                    return last_msg.inner_text().strip()
        except Exception:
            pass

    return "(Response completed or timed out)"


def main():
    parser = argparse.ArgumentParser(description="Feed approved questions to ChatGPT")
    parser.add_argument("--dry-run", action="store_true", help="Print batches without sending to ChatGPT")
    parser.add_argument("--headless", action="store_true", help="Run browser in headless mode")
    parser.add_argument("--batch-size", type=int, default=50, help="Questions per batch (default: 50)")
    args = parser.parse_args()

    qa_pairs = get_approved_qa_pairs()
    total_q = len(qa_pairs)
    print(f"Loaded {total_q} approved screening question/answer pairs from database.")

    if total_q == 0:
        print("No approved screening questions found.")
        return

    # Split into batches of batch_size
    batches = []
    for i in range(0, total_q, args.batch_size):
        batches.append(qa_pairs[i : i + args.batch_size])

    print(f"Divided into {len(batches)} batches ({args.batch_size} questions each):")
    for i, b in enumerate(batches):
        print(f"  - Batch {i+1}: {len(b)} questions (Q{i * args.batch_size + 1} to Q{i * args.batch_size + len(b)})")

    if args.dry_run:
        print("\n--- DRY RUN: Showing Batch 1 Header ---")
        prompt1 = format_batch_prompt(batches[0], 1, len(batches), 1)
        print(prompt1[:600] + "\n... [truncated for preview] ...")
        return

    url = get_chatgpt_question_url()
    print(f"\nTarget ChatGPT Conversation: {url}")

    with sync_playwright() as pw:
        ctx = launch_firefox_context(pw, headless=args.headless)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()

        try:
            print(f"Opening ChatGPT Custom GPT conversation...")
            navigate_to_conversation(page, url)
            dismiss_chatgpt_overlays(page)

            for b_idx, batch in enumerate(batches):
                start_num = b_idx * args.batch_size + 1
                batch_num = b_idx + 1
                print(f"\n==================================================")
                print(f"Sending Batch {batch_num}/{len(batches)} ({len(batch)} questions, Q{start_num} to Q{start_num + len(batch) - 1})...")
                print(f"==================================================")

                prompt_text = format_batch_prompt(batch, batch_num, len(batches), start_num)
                reply = send_prompt_to_chatgpt(page, prompt_text)

                print(f"\n✓ ChatGPT Response for Batch {batch_num}:")
                print("-" * 50)
                print(reply[:500] + ("..." if len(reply) > 500 else ""))
                print("-" * 50)

                if b_idx < len(batches) - 1:
                    print("\nPausing 5 seconds before sending next batch...")
                    time.sleep(5)

            print(f"\n🎉 Successfully fed all {total_q} approved questions and answers to ChatGPT!")

        finally:
            ctx.close()


if __name__ == "__main__":
    main()
