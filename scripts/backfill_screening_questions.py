#!/usr/bin/env python3
"""
Backfill Screening Questions from Activity Logs into Posts Table
(scripts/backfill_screening_questions.py)

Scans historical activity_logs execution outputs for LinkedIn Easy Apply
questionnaire captures and updates matching posts whose status is
REQUIRES_QUESTIONNAIRE and whose rejection_reason was previously overwritten.
"""

import sys
import os
import re

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.db.connection import get_connection


def run_backfill():
    print("=" * 60)
    print("🔄 Running Screening Questions Backfill from Activity Logs...")
    print("=" * 60)

    conn = get_connection()
    cur = conn.cursor()

    # 1. Fetch all activity logs containing logs
    cur.execute("SELECT id, logs FROM activity_logs WHERE logs IS NOT NULL ORDER BY created_at ASC;")
    rows = cur.fetchall()

    job_id_to_questions = {}
    url_to_questions = {}

    for log_id, lines in rows:
        current_job_id = None
        current_url = None
        for line in lines:
            # Check URL or job ID
            url_match = re.search(r"URL:\s*(https?://[^\s]+)", line)
            if url_match:
                clean_url = url_match.group(1).split("?")[0].rstrip("/")
                current_url = clean_url
                jid_match = re.search(r"/view/(\d+)", clean_url)
                if jid_match:
                    current_job_id = jid_match.group(1)

            q_match = re.search(r"Saved for Screening.*?:\s*(Questions:\s*.+)", line)
            if q_match:
                q_text = q_match.group(1).strip()
                if current_job_id:
                    job_id_to_questions[current_job_id] = q_text
                if current_url:
                    url_to_questions[current_url] = q_text

    print(f"Extracted questions for {len(job_id_to_questions)} unique job IDs from activity logs.")

    # 2. Update matching posts where status = 'REQUIRES_QUESTIONNAIRE'
    cur.execute("""
        SELECT id, post_url, rejection_reason 
        FROM posts 
        WHERE status = 'REQUIRES_QUESTIONNAIRE';
    """)
    screened_posts = cur.fetchall()
    print(f"Found {len(screened_posts)} posts with status 'REQUIRES_QUESTIONNAIRE'.")

    updated_count = 0
    for pid, purl, reason in screened_posts:
        clean_purl = (purl or "").split("?")[0].rstrip("/")
        jid_match = re.search(r"/view/(\d+)", clean_purl)
        jid = jid_match.group(1) if jid_match else None

        matched_q = None
        if jid and jid in job_id_to_questions:
            matched_q = job_id_to_questions[jid]
        elif clean_purl in url_to_questions:
            matched_q = url_to_questions[clean_purl]

        if matched_q:
            # Check if reason needs update
            if not reason or reason in ("Requires Screening Questions", "Multi-step Questionnaire (Saved for Screening)", "Multi-step Form Required Manual Input") or not reason.startswith("Questions:"):
                cur.execute("""
                    UPDATE posts 
                    SET rejection_reason = %s, updated_at = CURRENT_TIMESTAMP 
                    WHERE id = %s;
                """, (matched_q, pid))
                updated_count += 1

    conn.commit()
    cur.close()
    conn.close()

    print(f"✓ Backfilled questions for {updated_count} posts successfully.")
    print("=" * 60)


if __name__ == "__main__":
    run_backfill()
