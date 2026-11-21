"""
Continuous Generate & Send Pipeline for Reach.
Processes pending email outreach posts in sequential chunks of 10:
1. Queries the most recently scraped pending outreach posts (limit 10).
2. Triggers batch email generation via POST /api/generate-batch.
3. Waits for task_manager to complete the ChatGPT generation task.
4. Rigorously verifies every generated draft (checks for legitimate email structure,
   greeting, body length, and completely rejects prompt echoes or meta-directives).
   If any draft fails, it triggers re-generation via POST /api/generate-email/{id}?force=true.
5. Triggers batch email sending for verified valid drafts via POST /api/send-batch.
6. Waits for task_manager to complete Gmail sending.
7. Repeats for the next chunk of 10 until all pending outreach posts are sent (capping at 480/day).
"""

import os
import sys
import time
import json
import urllib.request
import urllib.error

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.db.connection import get_connection
from src.services.chatgpt_service import is_valid_email_draft

API_BASE = "http://localhost:8000/api"
CHUNK_SIZE = 10
MAX_DAILY_SEND_LIMIT = 480  # Stay safely below Gmail's 500 emails/day rolling limit


def get_emails_sent_today() -> int:
    """Return count of emails successfully sent today."""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT count(*) FROM posts WHERE status = 'SENT' AND sent_at >= CURRENT_DATE;")
                return cur.fetchone()[0]
    except Exception:
        return 0


def get_next_batch_posts(limit: int = 10) -> tuple:
    """
    Returns (already_generated_ids, needs_generation_ids).
    Combines any ready drafts with new ungenerated posts up to limit.
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            # 1. Check if any valid drafts already exist in Review & Drafts
            cur.execute("""
                SELECT id, generated_subject, generated_body 
                FROM posts 
                WHERE category = 'EMAIL_OUTREACH' 
                  AND status = 'EMAIL_GENERATED' 
                  AND generated_body IS NOT NULL 
                  AND generated_body != ''
                ORDER BY created_at DESC 
                LIMIT %s;
            """, (limit,))
            existing_generated = cur.fetchall()
            
            ready_ids = []
            for pid, subj, body in existing_generated:
                is_valid, _ = is_valid_email_draft(subj or "", body or "")
                if is_valid:
                    ready_ids.append(pid)

            needed = limit - len(ready_ids)
            needs_gen_ids = []
            if needed > 0:
                cur.execute("""
                    SELECT id 
                    FROM posts 
                    WHERE category = 'EMAIL_OUTREACH' 
                      AND status IN ('DISCOVERED', 'SELECTED') 
                      AND (generated_body IS NULL OR generated_body = '')
                    ORDER BY created_at DESC 
                    LIMIT %s;
                """, (needed,))
                needs_gen_ids = [r[0] for r in cur.fetchall()]

            return ready_ids, needs_gen_ids


def get_verified_draft_posts(post_ids: list) -> list:
    """
    Inspect drafts for the given post IDs.
    Returns (valid_ids, invalid_ids).
    A valid draft must pass is_valid_email_draft (no prompt echoes, proper body).
    """
    if not post_ids:
        return [], []
    valid_ids = []
    invalid_ids = []

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, author_name, generated_subject, generated_body 
                FROM posts 
                WHERE id = ANY(%s) 
                  AND status = 'EMAIL_GENERATED';
            """, (list(post_ids),))
            rows = cur.fetchall()
            for pid, author, subj, body in rows:
                is_valid, err_msg = is_valid_email_draft(subj or "", body or "")
                if is_valid:
                    valid_ids.append(pid)
                else:
                    print(f"  ⚠️ Draft for {author} ({pid[:8]}) failed content verification: {err_msg}")
                    invalid_ids.append((pid, author, err_msg))

    return valid_ids, invalid_ids


def post_json(endpoint: str, payload: dict) -> dict:
    url = f"{API_BASE}/{endpoint.lstrip('/')}"
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"  [Error {e.code}] {endpoint}: {body}")
        raise


def wait_for_task_completion(poll_interval: int = 10):
    """Wait until task_manager has no active task and an empty queue."""
    consecutive_idle = 0
    time.sleep(3)  # Brief pause to let task start
    while True:
        try:
            req = urllib.request.Request(f"{API_BASE}/tasks/status")
            with urllib.request.urlopen(req) as resp:
                data = json.loads(resp.read().decode())
                active = data.get("active_task")
                queue = data.get("queue", [])

                if active:
                    consecutive_idle = 0
                    cur_name = active.get("name", "Task")
                    cur_prog = active.get("progress", "")
                    cur_snip = active.get("snippet", "")
                    print(f"  ⏳ [In Progress] {cur_name} | {cur_prog} {cur_snip} | Queue: {len(queue)}")
                else:
                    if len(queue) == 0:
                        consecutive_idle += 1
                        if consecutive_idle >= 2:
                            print("  ✓ Task queue is idle and finished.")
                            break
                    else:
                        consecutive_idle = 0
                        print(f"  ⏳ Waiting for next task in queue ({len(queue)} pending)...")
        except Exception as e:
            print(f"  ⚠️ Polling error: {e}")
        time.sleep(poll_interval)


def main():
    print("=" * 70)
    print("🚀 Continuous Generate & Send Pipeline (10 Posts Per Chunk with Quality Checks)")
    print("=" * 70)

    chunk_num = 1
    total_processed = 0
    total_sent = 0

    while True:
        sent_today = get_emails_sent_today()
        remaining_quota = MAX_DAILY_SEND_LIMIT - sent_today
        if remaining_quota <= 0:
            print("\n" + "=" * 70)
            print(f"🛑 Daily Gmail limit reached ({sent_today}/{MAX_DAILY_SEND_LIMIT} sent today).")
            print("   Halting further dispatches until tomorrow to protect account standing.")
            print("=" * 70)
            break

        chunk_limit = min(CHUNK_SIZE, remaining_quota)
        ready_ids, needs_gen_ids = get_next_batch_posts(limit=chunk_limit)
        all_chunk_ids = ready_ids + needs_gen_ids
        if not all_chunk_ids:
            print("\n" + "=" * 70)
            print(f"🎉 All pending email outreach posts have been completed!")
            print(f"   Total Processed: {total_processed} | Total Sent Today: {sent_today}")
            print("=" * 70)
            break

        count = len(all_chunk_ids)
        print(f"\n=======================================================")
        print(f"📦 [Chunk #{chunk_num}] Processing {count} Posts ({len(ready_ids)} already drafted, {len(needs_gen_ids)} to generate | Sent today: {sent_today}/{MAX_DAILY_SEND_LIMIT})")
        print(f"=======================================================")

        # Step 1: Enqueue ChatGPT batch email generation for posts needing it
        if needs_gen_ids:
            print(f"\n[Step 1/3] Generating emails with Custom GPT for {len(needs_gen_ids)} posts...")
            try:
                gen_res = post_json("generate-batch", {"post_ids": needs_gen_ids})
                print(f"  ✓ {gen_res.get('message')}")
            except Exception as e:
                print(f"  ❌ Failed to enqueue generate-batch: {e}")
                break

            # Wait for ChatGPT generation to complete
            wait_for_task_completion(poll_interval=10)
        else:
            print(f"\n[Step 1/3] All {len(ready_ids)} posts in this chunk already have drafts. Skipping generation.")

        # Step 2: Verify and quality-check generated drafts
        print(f"\n[Step 2/3] Verifying generated email drafts...")
        valid_ids, invalid_items = get_verified_draft_posts(all_chunk_ids)

        # Re-generate any invalid drafts
        if invalid_items:
            print(f"  Found {len(invalid_items)} draft(s) needing re-generation:")
            for pid, author, err in invalid_items:
                print(f"    -> Re-generating for {author} ({err})...")
                try:
                    post_json(f"generate-email/{pid}?force=true", {})
                except Exception as regen_err:
                    print(f"       Failed to re-generate for {pid}: {regen_err}")
            
            # Wait for re-generation to finish
            wait_for_task_completion(poll_interval=10)
            valid_ids, _ = get_verified_draft_posts(all_chunk_ids)

        print(f"  ✓ {len(valid_ids)} / {count} verified drafts ready for sending.")

        if valid_ids:
            # Step 3: Enqueue Gmail batch send
            print(f"\n[Step 3/3] Sending {len(valid_ids)} verified applications directly via Gmail...")
            try:
                send_res = post_json("send-batch", {"post_ids": valid_ids})
                print(f"  ✓ {send_res.get('message')}")
                # Wait for Gmail sending to complete
                wait_for_task_completion(poll_interval=10)
                total_sent += len(valid_ids)
                print(f"  ✓ Chunk #{chunk_num} ({len(valid_ids)} emails) sent successfully!")
            except Exception as e:
                print(f"  ⚠️ Error queueing send-batch: {e}")
        else:
            print(f"  ⚠️ No posts in Chunk #{chunk_num} passed quality verification to send.")

        total_processed += count
        chunk_num += 1
        print(f"\n--- Progress so far: {total_processed} processed, {total_sent} sent ---")
        time.sleep(4)


if __name__ == "__main__":
    main()
