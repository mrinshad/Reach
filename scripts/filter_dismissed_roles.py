import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from typing import Tuple, Optional, Set
from src.db.connection import get_connection
from src.db.posts import normalize_job_title, get_dismissed_role_titles


def is_semantic_dismiss(title: str) -> Tuple[bool, Optional[str]]:
    """Determine if a job title represents an out-of-scope domain or non-developer role."""
    if not title:
        return False, None

    t = title.lower()

    # 1. Non-engineering / out-of-scope business domains
    non_tech = [
        r'\b(sales|b2c|b2b sales|commercial|procurement|accountant|accounting|finance|financial|billing|recruiter|recruitment|hr|talent acquisition|psychologist|electrician|mechanical engineer|civil engineer)\b',
        r'\b(business development|account executive|relationship manager|operations manager|store manager)\b'
    ]
    for pat in non_tech:
        m = re.search(pat, t, re.I)
        if m:
            return True, f"Non-engineering / out of domain role ({m.group(0)})"

    # 2. Pure IT infrastructure, DevOps, SRE, SysAdmin (not developer)
    infra_pure = [
        r'^(azure\s+)?(cloud|devops|devsecops|sre|site reliability|cloud ops|infrastructure|platform|systems|network|db)\s+(engineer|architect|administrator|lead|manager|specialist)',
        r'\b(devops engineer|devsecops engineer|site reliability engineer|cloud engineer|cloud ops engineer|systems engineer|support and deployment engineer|database reliability engineer)\b',
        r'\b(azure cloud engineer|aws administrator|cloud specialist|mlops lead|platform, cloud & mlops engineer)\b',
        r'\bsre/devops engineer\b',
        r'\bdevops and mlops engineer\b',
    ]
    for pat in infra_pure:
        if re.search(pat, t, re.I):
            # If primarily developer role, don't dismiss (e.g. Full-Stack Developer with devops)
            if not re.search(r'\b(full[- ]?stack|software engineer|software developer|backend developer|frontend developer|web developer)\b', t, re.I):
                return True, "Pure Infrastructure/DevOps/SRE role"
            elif re.search(r'^(devops|cloud|sre)', t, re.I):
                return True, "DevOps/Cloud primary title"

    # 3. Third-party platforms / proprietary CMS / CRM specialists
    proprietary = [
        r'\b(servicenow|service now|sharepoint|salesforce consultant|sap consultant|netsuite|bigcommerce|shopify developer)\b',
        r'\b(solutions architect|solutions specialist|solution engineer|field application engineer|fae)\b',
        r'\b(seo specialist)\b',
    ]
    for pat in proprietary:
        m = re.search(pat, t, re.I)
        if m:
            return True, f"Proprietary platform / specialist ({m.group(0)})"

    # 4. Pure AI/ML research / modeling (not fullstack / AI software dev)
    pure_ai = [
        r'\b(ai and automation analyst|ai/ml engineering \(delivery\)|machine learning engineer)\b',
    ]
    for pat in pure_ai:
        if re.search(pat, t, re.I):
            return True, "AI Analyst / ML modeling role"

    # 5. Non-job listings (e.g. company names parsed as titles)
    if t.strip() in ['skylark labs']:
        return True, "Invalid job title / company name placeholder"

    return False, None


def run_cleanup():
    print("=" * 70)
    print("  Reach Job Database — Retroactive Clean-Up & Auto-Dismissal")
    print("=" * 70)

    dismissed_set = get_dismissed_role_titles()
    print(f"Loaded {len(dismissed_set)} unique normalized previously dismissed roles.")

    with get_connection() as conn:
        with conn.cursor() as cur:
            # Step 1: Exact matches against previously dismissed roles
            cur.execute("""
                SELECT id, author_headline, author_name, category
                FROM posts
                WHERE status = 'DISCOVERED' AND author_headline IS NOT NULL;
            """)
            ready_posts = cur.fetchall()
            print(f"Found {len(ready_posts)} posts currently in DISCOVERED status.")

            exact_dismissed = []
            for pid, headline, company, cat in ready_posts:
                norm = normalize_job_title(headline)
                if norm in dismissed_set:
                    reason = f"Auto-dismissed: Matches previously dismissed role '{headline}'"
                    exact_dismissed.append((pid, headline, company, cat, reason))

            print(f"\n[Step 1] Exact Matches to Previously Dismissed Roles: {len(exact_dismissed)}")
            for pid, headline, company, cat, reason in exact_dismissed:
                cur.execute(
                    "UPDATE posts SET status = 'REJECTED', rejection_reason = %s WHERE id = %s;",
                    (reason, pid)
                )
                print(f"  ✓ [{cat}] Dismissed '{headline}' @ {company}")

            # Commit Step 1
            conn.commit()

            # Refresh dismissed_set with newly rejected titles
            dismissed_set = get_dismissed_role_titles()

            # Step 2: Semantic check on remaining EASY_APPLY DISCOVERED posts
            cur.execute("""
                SELECT id, author_headline, author_name, category
                FROM posts
                WHERE status = 'DISCOVERED' AND category = 'EASY_APPLY' AND author_headline IS NOT NULL;
            """)
            remaining_easy = cur.fetchall()
            print(f"\n[Step 2] Evaluating {len(remaining_easy)} remaining EASY_APPLY posts for semantic mismatch...")

            semantic_dismissed = []
            for pid, headline, company, cat in remaining_easy:
                is_d, sub_reason = is_semantic_dismiss(headline)
                if is_d:
                    reason = f"Auto-dismissed (Semantic Out-of-Domain Filter): {sub_reason}"
                    semantic_dismissed.append((pid, headline, company, cat, reason))

            print(f"Found {len(semantic_dismissed)} semantic matches to dismiss:")
            for pid, headline, company, cat, reason in semantic_dismissed:
                cur.execute(
                    "UPDATE posts SET status = 'REJECTED', rejection_reason = %s WHERE id = %s;",
                    (reason, pid)
                )
                print(f"  ✓ Dismissed '{headline}' @ {company} -> {reason}")

            conn.commit()

            # Final summary
            cur.execute("SELECT status, count(*) FROM posts WHERE category = 'EASY_APPLY' GROUP BY status;")
            ea_counts = dict(cur.fetchall())
            print("\n" + "=" * 70)
            print("  CLEANUP COMPLETE — EASY_APPLY STATUS BREAKDOWN:")
            print("=" * 70)
            for s, c in sorted(ea_counts.items()):
                print(f"  • {s:<25}: {c}")
            print("=" * 70)


if __name__ == "__main__":
    run_cleanup()
