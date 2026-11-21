"""
Experience Extractor Module

Parses natural language, unstructured LinkedIn post text to extract:
- Minimum years of experience (float)
- Maximum years of experience (float)
- Raw experience snippet for human review
- Fresher flag (boolean)
- Seniority classification (Fresher, Junior, Mid, Senior, Lead, Unspecified)
"""

import re
from typing import Optional, Dict, Any, List


def extract_experience(text: str) -> Dict[str, Any]:
    """
    Extract structured experience requirements from post text.

    Returns:
        {
            "min_years": Optional[float],
            "max_years": Optional[float],
            "raw_text": Optional[str],
            "is_fresher": bool,
            "seniority_level": str  # 'Fresher' | 'Junior' | 'Mid' | 'Senior' | 'Lead' | 'Unspecified'
        }
    """
    if not text:
        return _build_result(None, None, None, False, "Unspecified")

    lower = text.lower()

    # 1. Check for explicit Fresher / Entry level indicators
    fresher_match = re.search(
        r"\b(freshers?|entry\s+level|intern(?:ship)?|college\s+grad(?:uate)?|0\s*-\s*1\s*(?:years?|yrs?))\b",
        lower
    )
    if fresher_match and not re.search(r"(?:no|not\s+for)\s+freshers", lower):
        raw = fresher_match.group(0)
        # Check if there is also an explicit higher range before concluding pure fresher
        has_senior = re.search(r"\b([3-9]|\d{2})\+?\s*(?:years?|yrs?|yoe)\b", lower)
        if not has_senior:
            return _build_result(0.0, 1.0, raw, True, "Fresher")

    # 2. Pattern: Explicit range with label (e.g. "Experience: 5 to 9 years", "Exp: 4–8 Years", "YOE: 3-5")
    p1 = re.search(
        r"(?:exp(?:erience)?|yoe|relevant\s+exp(?:erience)?|work\s+exp)[\s:]*(\d+(?:\.\d+)?)\s*(?:[-–—]|to)\s*(\d+(?:\.\d+)?)\s*(?:years?|yrs?)?",
        lower
    )
    if p1:
        min_y = float(p1.group(1))
        max_y = float(p1.group(2))
        return _build_result(min_y, max_y, p1.group(0), False, _classify(min_y))

    # 3. Pattern: Range with units (e.g. "4–8 years of experience", "3 to 5 yrs", "4 - 8 YOE")
    p2 = re.search(
        r"\b(\d+(?:\.\d+)?)\s*(?:[-–—]|to)\s*(\d+(?:\.\d+)?)\s*(?:years?|yrs?|yoe)\b(?:\s+of\s+(?:relevant\s+)?exp(?:erience)?)?",
        lower
    )
    if p2:
        min_y = float(p2.group(1))
        max_y = float(p2.group(2))
        return _build_result(min_y, max_y, p2.group(0), False, _classify(min_y))

    # 4. Pattern: Plus pattern with label (e.g. "Experience: 5+ years", "YOE: 3+")
    p3 = re.search(
        r"(?:exp(?:erience)?|yoe|relevant\s+exp(?:erience)?)[\s:]*(\d+(?:\.\d+)?)\s*\+?\s*(?:years?|yrs?)?",
        lower
    )
    if p3:
        min_y = float(p3.group(1))
        return _build_result(min_y, None, p3.group(0), False, _classify(min_y))

    # 5. Pattern: Minimum / At least (e.g. "Minimum 4 years", "at least 3 yrs", "Min. 5 years of experience")
    p4 = re.search(
        r"(?:minimum|min\.?|at\s+least)\s*(\d+(?:\.\d+)?)\s*(?:years?|yrs?|yoe)\b(?:\s+of\s+(?:relevant\s+)?exp(?:erience)?)?",
        lower
    )
    if p4:
        min_y = float(p4.group(1))
        return _build_result(min_y, None, p4.group(0), False, _classify(min_y))

    # 6. Pattern: Simple "X+ years of experience" or "X+ yrs" (e.g. "8+ Years", "5+ YOE")
    p5 = re.search(
        r"\b(\d+(?:\.\d+)?)\s*\+\s*(?:years?|yrs?|yoe)\b(?:\s+of\s+(?:relevant\s+)?exp(?:erience)?)?",
        lower
    )
    if p5:
        min_y = float(p5.group(1))
        return _build_result(min_y, None, p5.group(0), False, _classify(min_y))

    # 7. Pattern: "Up to X years" or "Max X yrs"
    p6 = re.search(
        r"(?:up\s+to|max\.?|maximum)\s*(\d+(?:\.\d+)?)\s*(?:years?|yrs?|yoe)\b",
        lower
    )
    if p6:
        max_y = float(p6.group(1))
        return _build_result(0.0, max_y, p6.group(0), False, _classify(0.0))

    # 8. Check for Senior / Lead in title if no numbers were found
    if re.search(r"\b(lead|principal|architect|staff)\b", lower):
        return _build_result(7.0, None, "Title: Lead/Architect", False, "Lead")
    if re.search(r"\b(senior|sr\.?)\b", lower):
        return _build_result(5.0, None, "Title: Senior", False, "Senior")
    if re.search(r"\b(junior|jr\.?)\b", lower):
        return _build_result(1.0, 3.0, "Title: Junior", False, "Junior")

    return _build_result(None, None, None, False, "Unspecified")


def _classify(min_years: Optional[float]) -> str:
    """Classify seniority level based on minimum years of experience."""
    if min_years is None:
        return "Unspecified"
    if min_years < 1.0:
        return "Fresher"
    if min_years < 3.0:
        return "Junior"
    if min_years < 5.0:
        return "Mid"
    if min_years < 8.0:
        return "Senior"
    return "Lead"


def _build_result(
    min_years: Optional[float],
    max_years: Optional[float],
    raw_text: Optional[str],
    is_fresher: bool,
    seniority: str
) -> Dict[str, Any]:
    return {
        "min_years": min_years,
        "max_years": max_years,
        "raw_text": raw_text,
        "is_fresher": is_fresher,
        "seniority_level": seniority,
    }


def extract_phone_numbers(text: Optional[str]) -> List[str]:
    """
    Extract contact / WhatsApp phone numbers from unstructured post text.
    Handles international prefixes (+91, +1, etc.), labeled phone/WhatsApp numbers,
    and standard 10-digit mobile numbers with duplicate prevention by last 10 digits.
    """
    if not text:
        return []

    cleaned = text.replace("\xa0", " ").replace("\u200b", " ")
    results: List[str] = []
    seen_digits = set()

    # Pattern A: Explicit label (phone/mobile/whatsapp/call/contact/ph/tel/reach) followed by number
    pattern_labeled = re.compile(
        r"(?:(?:phone|mobile|mob|contact|call|whatsapp|tel|ph|reach)(?:\s*(?:no|number|us|at|on|me))?[\s:—–\-]+)"
        r"((\+?[0-9]{1,4}[\s\-.]?)?[0-9]{2,5}[\s\-.]?[0-9]{3,5}[\s\-.]?[0-9]{0,5})",
        re.IGNORECASE,
    )
    for m in pattern_labeled.finditer(cleaned):
        raw_num = m.group(1).strip()
        raw_num = re.sub(r"[\.,;:—–\-]+$", "", raw_num).strip()
        pure_digits = re.sub(r"\D", "", raw_num)
        if 8 <= len(pure_digits) <= 15:
            last10 = pure_digits[-10:]
            if last10 not in seen_digits:
                seen_digits.add(last10)
                results.append(raw_num)

    # Pattern B: Standard International (+91 ..., +1 ...)
    pattern_intl = re.compile(r"\+(?:91|1|44|971|65|60|61)[\s\-]?[6-9][0-9]{4}[\s\-]?[0-9]{5}\b")
    for m in pattern_intl.finditer(cleaned):
        s = m.group(0).strip()
        pure_digits = re.sub(r"\D", "", s)
        last10 = pure_digits[-10:]
        if last10 not in seen_digits:
            seen_digits.add(last10)
            results.append(s)

    # Pattern C: Indian 10-digit mobile standing alone (starts with 6-9)
    pattern_ind = re.compile(r"\b([6-9]\d{4}[\s\-]?\d{5})\b")
    for m in pattern_ind.finditer(cleaned):
        s = m.group(1).strip()
        pure_digits = re.sub(r"\D", "", s)
        if len(pure_digits) == 10:
            last10 = pure_digits
            if last10 not in seen_digits:
                seen_digits.add(last10)
                results.append(s)

    return results
