"""
Safety module — detects safe-failure / refusal cases.

Implements the four safe-failure scenarios from the proposal:
  1. Question not covered by indexed materials  → cannot verify, direct to Moodle
  2. Possible stale deadline                     → direct to Moodle
  3. Extension / grading decision request         → decline, refer to staff
  4. Off-topic request                            → decline, steer back

Each check returns a dict with:
  {refused: bool, reason: str, redirect: str}
"""

import re


# --- keyword lists --------------------------------------------------

EXTENSION_PATTERNS = [
    r"\bextension\b",
    r"\bextend\s+(the\s+)?deadline\b",
    r"\blate\s+submission\b",
    r"\bgrant\s+(me\s+)?(an?\s+)?extension\b",
    r"\bextra\s+time\b",
    r"\bdefer\b",
]

GRADING_PATTERNS = [
    r"\bgrade\s+(me\b|my\b|this\b)?",
    r"\bgrading\b",
    r"\bmark\s+(my\b|this\b)?",
    r"\bresubmit",
    r"\bappeal",
    r"\bremark\b",
    r"\bexception\b",
    r"\bwaive\b",
    r"\boverride\b",
]

OFFTOPIC_PATTERNS = [
    # medical / diagnosis
    r"\bdiagnos",
    r"\bsymptom",
    r"\bprescription\b",
    r"\bmedication\b",
    r"\bdisease\b",
    r"\bmental\s+health\b",
    r"\bchest\s+pain\b",
    # weather / forecast
    r"\bweather\b",
    r"\bforecast\b",
    r"\btemperature\b",
    # unrelated personal advice
    r"\binvest\b",
    r"\bstock\s+market\b",
    r"\brecipe\b",
    r"\btravel\s+plan",
    r"\bcook",
    r"\bsports\s+score",
    r"\bmovie\s+recommend",
]

STALE_DEADLINE_PATTERNS = [
    r"\bcurrent\s+deadline\b",
    r"\blatest\s+deadline\b",
    r"\bhas\s+the\s+deadline\s+changed\b",
    r"\bupdated\s+deadline\b",
    r"\bnew\s+deadline\b",
    r"\bdeadline\s+changed\b",
    r"\bdeadline\s+moved\b",
]


# --- check functions ------------------------------------------------

def _match_any(patterns, text):
    text_lower = text.lower()
    for p in patterns:
        if re.search(p, text_lower):
            return True
    return False


def check_safety(question: str, has_results: bool) -> dict:
    """
    Run all safety checks. Returns the first match or a pass-through.

    Parameters:
      question     — the user's natural-language question
      has_results   — whether the retriever found any relevant passages
    """
    # Case 3: extension or grading decision → decline
    if _match_any(EXTENSION_PATTERNS, question) or _match_any(GRADING_PATTERNS, question):
        return {
            "refused": True,
            "reason": "This is an extension or grading decision request.",
            "redirect": (
                "I cannot make grading, extension, or exception decisions. "
                "Please contact your course staff or teaching team directly."
            ),
        }

    # Case 4: off-topic → decline and steer back
    if _match_any(OFFTOPIC_PATTERNS, question):
        return {
            "refused": True,
            "reason": "This question is off-topic for AILT9019 course materials.",
            "redirect": (
                "This appears to be outside the scope of AILT9019 course materials. "
                "I can help with course concepts, project requirements, procedures, "
                "and deadlines. Please ask a course-related question."
            ),
        }

    # Case 2: possible stale deadline → direct to Moodle
    if _match_any(STALE_DEADLINE_PATTERNS, question):
        return {
            "refused": True,
            "reason": "Possible stale deadline information.",
            "redirect": (
                "Deadlines may have changed. For the most current and official "
                "deadline, please check the AILT9019 Moodle page or contact course "
                "staff rather than relying on indexed materials that may be outdated."
            ),
        }

    # Case 1: no relevant passages found → cannot verify
    if not has_results:
        return {
            "refused": True,
            "reason": "No relevant passages found in indexed materials.",
            "redirect": (
                "I could not find information about this in the indexed course "
                "materials. This question may not be covered, or the materials "
                "may not contain the answer. Please check Moodle or contact "
                "course staff."
            ),
        }

    # All checks passed — proceed with answering
    return {"refused": False, "reason": "", "redirect": ""}
