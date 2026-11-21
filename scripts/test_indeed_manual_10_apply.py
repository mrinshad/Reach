#!/usr/bin/env python3
"""
Test script: Manual Indeed Apply test across 10 jobs (3 roles x 3 jobs + 1 additional).
Verifies:
- Automated error bypass (Terms of Service, Tailoring resume, Not applicable / qualification warning)
- ChatGPT reason generation and clipboard copy when requested
- Question bank lookup & blocking on missing questions (REQUIRES_QUESTIONNAIRE)
- Successful submission (APPLIED) on review screen
"""

import sys
import os
import json
from datetime import datetime

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.services.indeed_apply_service import apply_to_single_indeed_post
from src.db.posts import get_post_by_id

TEST_JOBS = [
    # --- Role 1: Full Stack Developer (3 jobs) ---
    {
        "role_group": "Full Stack Developer",
        "id": "fa2ed1f1be02d81be1cab08148b203d3",
        "company": "Code Brew Labs",
        "title": "Full Stack Developer",
    },
    {
        "role_group": "Full Stack Developer",
        "id": "c307e35ad32d3572872a60da98942410",
        "company": "Diksha Technologies",
        "title": "Full Stack Developer",
    },
    {
        "role_group": "Full Stack Developer",
        "id": "1402fa7b7b1d3c44b48965a03832c9cf",
        "company": "Coducer Technologies Private Limited",
        "title": "Full Stack Developer",
    },

    # --- Role 2: Frontend / React / MERN Developer (3 jobs) ---
    {
        "role_group": "Frontend / React / MERN Developer",
        "id": "b2c53c1d2d827dd3ead5a07449672a6b",
        "company": "XO Health Inc.",
        "title": "Full Stack Engineer (Front-End)",
    },
    {
        "role_group": "Frontend / React / MERN Developer",
        "id": "efa14f5b0ae3ede60cdb58bcf811e497",
        "company": "QUESTHOSTIN SERVICES PVT LTD",
        "title": "Full Stack Developer – React & Node.js",
    },
    {
        "role_group": "Frontend / React / MERN Developer",
        "id": "cce65cac5086dcd2a41b302c72cc6890",
        "company": "Intelligent It hub Pvt Ltd",
        "title": "MERN Stack Developer",
    },

    # --- Role 3: Backend / Python / .NET Developer (3 jobs) ---
    {
        "role_group": "Backend / Python / .NET Developer",
        "id": "8b7d17f000766c976def11cb86cc1ef0",
        "company": "Vivify Healthcare Pvt. Ltd.",
        "title": "Full Stack Developer – Python",
    },
    {
        "role_group": "Backend / Python / .NET Developer",
        "id": "d3041ce7de9d63d78ab6bf86953ded52",
        "company": "INTELLINEZ SYSTEMS",
        "title": "Dot Net Developer (Project Engineer)",
    },
    {
        "role_group": "Backend / Python / .NET Developer",
        "id": "26d67a61b97c3b21fe8d27b73e9f9a4d",
        "company": "Your's Efficiently",
        "title": "Senior dot net developer",
    },

    # --- Job 10: Additional Software Engineer ---
    {
        "role_group": "Software Engineer",
        "id": "4688929bec2e84d32c2ee047e08f94a4",
        "company": "WhoFi India Pvt Ltd",
        "title": "Software Engineer",
    },
]

def main():
    print(f"\n=======================================================")
    print(f"🚀 STARTING INDEED MANUAL APPLY TEST MATRIX (10 JOBS)")
    print(f"=======================================================")
    print(f"Total jobs to test: {len(TEST_JOBS)}")
    print(f"Roles covered: Full Stack (3), Frontend/React (3), Backend/Python/.Net (3), Software Engineer (1)\n")

    results = []

    for idx, item in enumerate(TEST_JOBS, 1):
        job_id = item["id"]
        role_group = item["role_group"]
        company = item["company"]
        title = item["title"]

        print(f"\n-------------------------------------------------------")
        print(f"[{idx}/10] Testing [{role_group}]")
        print(f"       Job: {title} @ {company}")
        print(f"       ID:  {job_id}")
        print(f"-------------------------------------------------------")

        class SimpleTaskManager:
            def log(self, msg):
                print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

        try:
            res = apply_to_single_indeed_post(job_id, task_manager=SimpleTaskManager())
            status = res.get("status", "UNKNOWN")
            detail = res.get("detail", "")
            print(f"\n>> RESULT [{idx}/10]: Status = {status} | Detail = {detail}")

            # Verify in DB
            db_post = get_post_by_id(job_id)
            db_status = db_post.get("status") if db_post else "NOT_IN_DB"
            rejection_reason = db_post.get("rejection_reason") if db_post else None

            results.append({
                "index": idx,
                "role_group": role_group,
                "title": title,
                "company": company,
                "id": job_id,
                "result_status": status,
                "db_status": db_status,
                "rejection_reason": rejection_reason,
                "detail": detail,
            })
        except Exception as e:
            print(f"\n>> EXCEPTION on Job {job_id}: {e}")
            results.append({
                "index": idx,
                "role_group": role_group,
                "title": title,
                "company": company,
                "id": job_id,
                "result_status": "ERROR",
                "db_status": "ERROR",
                "detail": str(e),
            })

    print(f"\n=======================================================")
    print(f"📊 TEST MATRIX EXECUTION SUMMARY")
    print(f"=======================================================")
    for r in results:
        stat_icon = "✅" if r["result_status"] in ("APPLIED", "REQUIRES_QUESTIONNAIRE", "NOT_FOUND") else "❌"
        print(f"{stat_icon} [{r['index']}/10] {r['role_group']} | {r['title']} @ {r['company']}: Result={r['result_status']}, DB={r['db_status']}")
        if r.get("rejection_reason"):
            print(f"      Reason: {r['rejection_reason']}")

    # Save summary report to JSON
    out_path = "scripts/test_indeed_manual_10_results.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nFull results saved to {out_path}")

if __name__ == "__main__":
    main()
