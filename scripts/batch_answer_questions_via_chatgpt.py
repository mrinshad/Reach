#!/usr/bin/env python3
"""
Batch Screening Question Answering via ChatGPT
(scripts/batch_answer_questions_via_chatgpt.py)

Fetches all PENDING questions from PostgreSQL screening_questions table
and systematically queries the applicant's dedicated ChatGPT Question-Answering
custom GPT conversation.

Rules:
1. Pure questions (with options if multiple choice) are sent without wrapper fluff.
2. If ChatGPT returns 'WTF' -> Mark question as 'UNREASONABLE' in DB.
3. If ChatGPT returns 'DONT_KNOW' / 'user_response_needed' -> Kept as 'PENDING' for manual screening.
4. If ChatGPT returns a valid answer -> Saved to DB with status='ANSWERED'.
"""

import sys
import os
import time
import argparse
from typing import List, Dict, Any, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from playwright.sync_api import sync_playwright
from src.db.connection import get_connection
from src.db.question_bank import remove_from_deleted_question_keys
from src.services.firefox_connector import launch_firefox_context
from src.services.chatgpt_service import (
    get_chatgpt_question_url,
    navigate_to_conversation,
    dismiss_chatgpt_overlays,
    send_question_and_get_answer,
    PROMPT_BOX_SELECTOR,
)


def fetch_pending_questions(limit: Optional[int] = None) -> List[Dict[str, Any]]:
    """Retrieve pending screening questions that are genuine questions (not document files)."""
    conn = get_connection()
    cur = conn.cursor()

    query = """
        SELECT id, question_key, question_text, options, occurrences, sample_jobs
        FROM screening_questions
        WHERE status = 'PENDING'
          AND question_text NOT ILIKE '%.pdf%'
          AND question_text NOT ILIKE '%.docx%'
          AND question_text NOT ILIKE '%.doc%'
          AND question_text NOT ILIKE '%.rtf%'
          AND question_text NOT ILIKE '%.odt%'
          AND question_text NOT ILIKE '%.txt%'
        ORDER BY occurrences DESC, id ASC
    """
    if limit and limit > 0:
        query += f" LIMIT {int(limit)}"

    cur.execute(query)
    rows = cur.fetchall()
    cur.close()
    conn.close()

    questions = []
    for r in rows:
        q_id, q_key, q_text, options, occurrences, sample_jobs = r
        clean_text = (q_text or "").strip()
        if not clean_text or len(clean_text) < 3:
            continue
        # Safety guard against files
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


def run_batch_answering(
    limit: Optional[int] = None,
    headless: bool = False,
    delay: float = 2.0,
    dry_run: bool = False,
):
    print("=" * 70)
    print("🤖 Batch Screening Question Answering via ChatGPT")
    print("=" * 70)

    pending_questions = fetch_pending_questions(limit=limit)
    total_found = len(pending_questions)
    print(f"📋 Found {total_found} genuine PENDING question(s) in database.")

    if total_found == 0:
        print("✓ No pending questions found. Everything is already up to date!")
        return

    if dry_run:
        print("\n🔍 DRY RUN MODE (no browser launched):")
        for i, q in enumerate(pending_questions, 1):
            opts_str = f" [Options: {', '.join(q['options'])}]" if q['options'] else ""
            print(f"  {i}. {q['question']}{opts_str} (occurrences: {q['occurrences']})")
        print("\nDry run completed successfully.")
        return

    chatgpt_url = get_chatgpt_question_url()
    print(f"🔗 Target ChatGPT Conversation URL:\n   {chatgpt_url}\n")
    print(f"🌐 Headless: {headless} | Inter-question Delay: {delay}s\n")

    conn = get_connection()
    cur = conn.cursor()

    answered_count = 0
    dont_know_count = 0
    wtf_count = 0
    failed_count = 0

    with sync_playwright() as playwright:
        print("🚀 Launching Firefox session...")
        context = launch_firefox_context(
            playwright,
            headless=headless,
            sync_cookies_domains=["chatgpt.com", "openai.com"],
        )
        page = context.pages[0] if context.pages else context.new_page()

        try:
            print(f"Navigating to ChatGPT question answering page...")
            navigate_to_conversation(page, url=chatgpt_url)
            dismiss_chatgpt_overlays(page)
            page.wait_for_selector(PROMPT_BOX_SELECTOR, timeout=15000)
            print("✓ Ready to submit questions!\n")

            for idx, item in enumerate(pending_questions, 1):
                qid = item["id"]
                qkey = item["key"]
                qtext = item["question"]
                options = item["options"]

                print("-" * 60)
                opts_display = f" | Options: {options}" if options else ""
                print(f"[{idx}/{total_found}] '{qtext[:75]}'{opts_display}")

                if page.is_closed():
                    print("  🔄 Page was closed. Launching new tab and navigating to conversation...")
                    try:
                        page = context.new_page()
                        navigate_to_conversation(page, url=chatgpt_url)
                        dismiss_chatgpt_overlays(page)
                        page.wait_for_selector(PROMPT_BOX_SELECTOR, timeout=15000)
                    except Exception as e:
                        print(f"  ✗ Failed to recover browser tab: {e}")
                        failed_count += 1
                        continue

                ans, status = send_question_and_get_answer(
                    page,
                    question_text=qtext,
                    options=options,
                    logger=print,
                )

                if status == "WTF":
                    cur.execute("""
                        UPDATE screening_questions
                        SET status = 'UNREASONABLE', updated_at = CURRENT_TIMESTAMP
                        WHERE id = %s;
                    """, (qid,))
                    conn.commit()
                    wtf_count += 1
                    print(f"  🚫 [WTF] Marked as UNREASONABLE in database.")

                elif status == "DONT_KNOW":
                    # Keep as PENDING for human screening
                    dont_know_count += 1
                    print(f"  ⚠️ [DONT_KNOW] Left as PENDING for manual user screening.")

                elif status == "OK" and ans:
                    cur.execute("""
                        UPDATE screening_questions
                        SET answer = %s, status = 'AI_SUGGESTED', updated_at = CURRENT_TIMESTAMP
                        WHERE id = %s;
                    """, (ans, qid))
                    conn.commit()
                    remove_from_deleted_question_keys([qkey, qid, qtext])
                    answered_count += 1
                    print(f"  ✓ [AI_SUGGESTED] Saved suggestion: '{ans}'")

                else:
                    failed_count += 1
                    print(f"  ✗ [FAILED] Could not resolve answer (status: {status}). Kept PENDING.")
                    try:
                        page.wait_for_selector(PROMPT_BOX_SELECTOR, timeout=3000)
                    except Exception:
                        print("  🔄 Re-navigating to ChatGPT conversation to recover session...")
                        try:
                            navigate_to_conversation(page, url=chatgpt_url)
                            dismiss_chatgpt_overlays(page)
                        except Exception:
                            pass

                if idx < total_found:
                    time.sleep(delay)

        finally:
            cur.close()
            conn.close()
            context.close()

    print("\n" + "=" * 70)
    print("📊 Batch Answering Run Summary:")
    print(f"  • Total Processed:         {total_found}")
    print(f"  • Successfully Answered:   {answered_count}")
    print(f"  • Marked Unreasonable/WTF: {wtf_count}")
    print(f"  • ChatGPT Doesn't Know:    {dont_know_count} (left PENDING)")
    print(f"  • Failures / Timeouts:     {failed_count}")
    print("=" * 70)


def main():
    parser = argparse.ArgumentParser(description="Batch answer pending screening questions using custom ChatGPT.")
    parser.add_argument("--limit", type=int, default=None, help="Max number of pending questions to process")
    parser.add_argument("--headless", action="store_true", default=False, help="Run browser in headless mode")
    parser.add_argument("--delay", type=float, default=2.0, help="Delay in seconds between questions (default: 2.0)")
    parser.add_argument("--dry-run", action="store_true", default=False, help="List pending questions without running ChatGPT")
    args = parser.parse_args()

    run_batch_answering(
        limit=args.limit,
        headless=args.headless,
        delay=args.delay,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
