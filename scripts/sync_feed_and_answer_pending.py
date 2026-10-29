#!/usr/bin/env python3
"""
Sync Feed Approved Questions and Auto-Answer Pending Questions via ChatGPT
(scripts/sync_feed_and_answer_pending.py)

Orchestrates the complete review and answering lifecycle:
1. Feeds newly approved screening questions back to ChatGPT Custom GPT in batches of 50.
2. Sends the exact transition prompt instructing ChatGPT to resume answering.
3. Automatically queries ChatGPT for all genuine PENDING screening questions,
   saving responses into the Question Bank under 'AI_SUGGESTED'.
"""

import sys
import os
import time
import argparse
from typing import List, Tuple, Dict, Any, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from playwright.sync_api import sync_playwright
from src.db.connection import get_connection
from src.db.question_bank import normalize_question_key, remove_from_deleted_question_keys
from src.services.firefox_connector import launch_firefox_context
from src.services.chatgpt_service import (
    get_chatgpt_question_url,
    navigate_to_conversation,
    dismiss_chatgpt_overlays,
    send_question_and_get_answer,
    PROMPT_BOX_SELECTOR,
    SEND_BTN_SELECTOR,
)
from scripts.feed_approved_questions_to_chatgpt import (
    get_approved_qa_pairs,
    format_batch_prompt,
    send_prompt_to_chatgpt,
)


TRANSITION_PROMPT = (
    "Feeding is done now, lets start questionire again. I hope you know the 3 types of "
    "responses you should give and you'll follow the instrcutions which i gave you before "
    "like not to generate anything except the answer"
)


def get_newly_approved_questions() -> List[Tuple[str, str]]:
    """Retrieve all approved questions updated today that were not in the first 98 batch."""
    already_fed = get_approved_qa_pairs()
    fed_keys = {normalize_question_key(q) for q, _ in already_fed}

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT question_text, answer, question_key, updated_at
        FROM screening_questions
        WHERE status = 'ANSWERED' AND answer IS NOT NULL AND answer != ''
        ORDER BY updated_at ASC;
    """)
    all_answered = cur.fetchall()
    cur.close()
    conn.close()

    newly_approved = []
    seen = set()
    for q_text, ans, q_key, updated_at in all_answered:
        if q_key not in fed_keys and q_key not in seen:
            if str(updated_at) >= "2026-10-28 00:00:00":
                newly_approved.append((q_text, ans))
                seen.add(q_key)

    return newly_approved


def get_pending_questions() -> List[Dict[str, Any]]:
    """Retrieve genuine pending questions (excluding uploaded document filenames)."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, question_key, question_text, options, occurrences, sample_jobs
        FROM screening_questions
        WHERE status = 'PENDING'
          AND question_text NOT ILIKE '%.pdf%'
          AND question_text NOT ILIKE '%.docx%'
          AND question_text NOT ILIKE '%.doc%'
          AND question_text NOT ILIKE '%.rtf%'
          AND question_text NOT ILIKE '%.odt%'
          AND question_text NOT ILIKE '%.txt%'
        ORDER BY occurrences DESC, id ASC;
    """)
    rows = cur.fetchall()
    cur.close()
    conn.close()

    questions = []
    for r in rows:
        q_id, q_key, q_text, options, occurrences, sample_jobs = r
        clean_text = (q_text or "").strip()
        if not clean_text or len(clean_text) < 3:
            continue
        if any(ext in clean_text.lower() for ext in [".pdf", ".docx", ".doc", ".rtf", ".odt", ".txt"]):
            continue
        questions.append({
            "id": q_id,
            "key": q_key,
            "question": clean_text,
            "options": options or [],
            "occurrences": occurrences,
            "sample_jobs": sample_jobs or [],
        })
    return questions


def ensure_browser_session(pw, ctx, page, url, headless=False):
    """Ensure Firefox context and page are open, loaded, and prompt box is available."""
    try:
        if page and not page.is_closed():
            dismiss_chatgpt_overlays(page)
            if page.locator(PROMPT_BOX_SELECTOR).count() > 0:
                return ctx, page
    except Exception:
        pass

    if ctx:
        try:
            ctx.close()
        except Exception:
            pass

    print("  🚀 Initializing fresh Firefox session...")
    ctx = launch_firefox_context(
        pw,
        headless=headless,
        sync_cookies_domains=["chatgpt.com", "openai.com"],
    )
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    navigate_to_conversation(page, url=url)
    dismiss_chatgpt_overlays(page)
    page.wait_for_selector(PROMPT_BOX_SELECTOR, timeout=25000)
    print("  ✓ Firefox session ready!")
    return ctx, page


def main():
    parser = argparse.ArgumentParser(description="Feed newly approved Q&A and answer pending questionnaires")
    parser.add_argument("--dry-run", action="store_true", help="Preview questions without sending to ChatGPT")
    parser.add_argument("--headless", action="store_true", help="Run browser headless")
    parser.add_argument("--skip-feeding", action="store_true", help="Skip feeding step and jump straight to transition prompt and pending questions")
    parser.add_argument("--delay", type=float, default=2.5, help="Seconds delay between pending questions")
    args = parser.parse_args()

    newly_approved = [] if args.skip_feeding else get_newly_approved_questions()
    pending_questions = get_pending_questions()

    print("=" * 70)
    print("🤖 Reach Screening Questionnaire Automation")
    print(f"  • Newly Approved Questions to Feed: {len(newly_approved)}")
    print(f"  • Pending Questions to Answer:     {len(pending_questions)}")
    print("=" * 70)

    if args.dry_run:
        print("\n[DRY RUN] Newly Approved:")
        for i, (q, a) in enumerate(newly_approved, 1):
            print(f"  {i}. Q: {q[:60]} -> A: {a}")
        print("\n[DRY RUN] Pending to Answer:")
        for i, q in enumerate(pending_questions[:10], 1):
            print(f"  {i}. Q: {q['question'][:60]}")
        print(f"  ... and {len(pending_questions) - 10} more.")
        return

    chatgpt_url = get_chatgpt_question_url()
    print(f"🔗 Target ChatGPT URL: {chatgpt_url}")

    with sync_playwright() as pw:
        ctx = None
        page = None
        ctx, page = ensure_browser_session(pw, ctx, page, chatgpt_url, headless=args.headless)

        try:
            # ----------------------------------------------------
            # STEP 1: Feed Newly Approved Questions (Batches of 50)
            # ----------------------------------------------------
            if newly_approved and not args.skip_feeding:
                batch_size = 50
                batches = [newly_approved[i : i + batch_size] for i in range(0, len(newly_approved), batch_size)]
                print(f"\nDivided {len(newly_approved)} newly approved questions into {len(batches)} batch(es).")

                for b_idx, batch in enumerate(batches):
                    batch_num = b_idx + 1
                    start_num = b_idx * batch_size + 1
                    print(f"\n[FEEDING BATCH {batch_num}/{len(batches)}] Sending {len(batch)} Q&A pairs (Q{start_num} to Q{start_num + len(batch) - 1})...")

                    ctx, page = ensure_browser_session(pw, ctx, page, chatgpt_url, headless=args.headless)
                    prompt_text = format_batch_prompt(batch, batch_num, len(batches), start_num)
                    reply = send_prompt_to_chatgpt(page, prompt_text)

                    print(f"✓ ChatGPT Response for Batch {batch_num}:")
                    print("-" * 50)
                    print(reply[:400] + ("..." if len(reply) > 400 else ""))
                    print("-" * 50)
                    time.sleep(4)
            else:
                print("\nℹ️ Skipping feeding step (already fed to active ChatGPT conversation).")

            # ----------------------------------------------------
            # STEP 2: Send Single Transition Prompt
            # ----------------------------------------------------
            print("\n" + "=" * 70)
            print("📤 Sending Transition Prompt to ChatGPT:")
            print(f"'{TRANSITION_PROMPT}'")
            print("=" * 70)

            ctx, page = ensure_browser_session(pw, ctx, page, chatgpt_url, headless=args.headless)
            transition_reply = send_prompt_to_chatgpt(page, TRANSITION_PROMPT)
            print("\n✓ ChatGPT Transition Response:")
            print("-" * 50)
            print(transition_reply[:400] + ("..." if len(transition_reply) > 400 else ""))
            print("-" * 50)
            time.sleep(4)

            # ----------------------------------------------------
            # STEP 3: Auto-Answer Pending Questions -> AI_SUGGESTED
            # ----------------------------------------------------
            # Refresh pending questions in case any were answered
            pending_questions = get_pending_questions()
            total_pending = len(pending_questions)
            print("\n" + "=" * 70)
            print(f"🎯 Beginning Auto-Answering for {total_pending} Pending Question(s)...")
            print("=" * 70)

            conn = get_connection()
            cur = conn.cursor()

            ai_suggested_count = 0
            unreasonable_count = 0
            pending_kept_count = 0
            failed_count = 0

            for idx, item in enumerate(pending_questions, 1):
                qid = item["id"]
                qkey = item["key"]
                qtext = item["question"]
                options = item["options"]

                print(f"\n[{idx}/{total_pending}] {qtext}")
                if options:
                    print(f"    Options: {options}")

                # Ensure browser session is active and healthy
                for attempt in range(2):
                    try:
                        ctx, page = ensure_browser_session(pw, ctx, page, chatgpt_url, headless=args.headless)
                        ans, status = send_question_and_get_answer(
                            page,
                            question_text=qtext,
                            options=options,
                            logger=print,
                        )
                        break
                    except Exception as e:
                        print(f"  ⚠️ Session glitch on attempt {attempt+1}: {e}")
                        time.sleep(2)
                        page = None
                else:
                    ans, status = None, "FAILED"

                if status == "WTF":
                    cur.execute("""
                        UPDATE screening_questions
                        SET status = 'UNREASONABLE', updated_at = CURRENT_TIMESTAMP
                        WHERE id = %s;
                    """, (qid,))
                    conn.commit()
                    unreasonable_count += 1
                    print(f"  🚫 [WTF] Marked as UNREASONABLE in database.")

                elif status == "DONT_KNOW":
                    pending_kept_count += 1
                    print(f"  ⚠️ [DONT_KNOW] Retained as PENDING for manual review.")

                elif status == "OK" and ans:
                    # Save as AI_SUGGESTED per user requirement
                    cur.execute("""
                        UPDATE screening_questions
                        SET answer = %s, status = 'AI_SUGGESTED', updated_at = CURRENT_TIMESTAMP
                        WHERE id = %s;
                    """, (ans, qid))
                    conn.commit()
                    remove_from_deleted_question_keys([qkey, qid, qtext])
                    ai_suggested_count += 1
                    print(f"  ✓ [AI_SUGGESTED] Saved suggested answer: '{ans}'")

                else:
                    failed_count += 1
                    print(f"  ✗ [FAILED] Status: {status}. Left as PENDING.")

                time.sleep(args.delay)

            cur.close()
            conn.close()

            print("\n" + "=" * 70)
            print("🏁 Questionnaire Processing Complete!")
            print(f"  • AI Suggestions Generated:  {ai_suggested_count}")
            print(f"  • Marked as Unreasonable:     {unreasonable_count}")
            print(f"  • Retained as Pending:        {pending_kept_count}")
            print(f"  • Failed / Timed Out:         {failed_count}")
            print("=" * 70)

        finally:
            if ctx:
                try:
                    ctx.close()
                except Exception:
                    pass


if __name__ == "__main__":
    main()
