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

from retriever import cited_sources


MONTH = (r"jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|"
         r"jul(?:y)?|aug(?:ust)?|sep(?:tember|t)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?")
MONTH_NAMES = "January February March April May June July August September October November December".split()


def proposal_move_month(question):
    """Identify the proposed destination month, scoped to the proposal."""
    match = re.search(
        rf"\bproposal(?:\s+(?:submission\s+)?(?:deadline|due\s+date))?\s+"
        rf"(?:(?:has|had|is|was|been|got)\s+)*(?:move[d]?|chang(?:ed|e)|postponed|extended|pushed\s+back)"
        rf"\s+(?:from\s+(?:\d{{1,2}}\s+)?(?:{MONTH})\s+)?(?:to|until)\s+(?:the\s+)?"
        rf"(?:\d{{1,2}}(?:st|nd|rd|th)?\s+(?:of\s+)?)?({MONTH})\b", question, re.I,
    )
    if match:
        return next(name for name in MONTH_NAMES if name[:3].lower() == match[1][:3].lower())
    match = re.search(r"(?:proposal|提案)\s*(?:的)?(?:截止日期|截止时间)?(?:已经|已|被)?"
                      r"(?:延期|推迟|延后|延迟|改)(?:了)?[到至]\s*(1[0-2]|[1-9])\s*月", question, re.I)
    return MONTH_NAMES[int(match[1]) - 1] if match else None


# PDF extraction can remove every space, including those inside a date.
_CHANGE_RECORD = re.compile(
    rf"proposal(?:submission)?(?:deadline|duedate)(?:was|hasbeen)?(?:moved|changed|extended|postponed)"
    rf"from\d{{1,2}}(?:{MONTH})(?:inweek\d+)?to(\d{{1,2}})({MONTH})(?:inweek(\d+))?", re.I,
)


def answer_proposal_move(month, passages):
    """Report the documented change without treating it as a live Moodle deadline."""
    dates = {}
    for page in passages:
        for match in _CHANGE_RECORD.finditer(re.sub(r"\s+", "", page["text"])):
            date = f"{int(match[1])} {match[2][:3].title()}"
            dates.setdefault(date, (page, match[3]))

    guidance = "Please check Moodle for the official deadline."
    if len(dates) != 1:
        return {"answer": f"I cannot verify a move to {month} from the indexed materials. {guidance}",
                "sources": [], "used_llm": False}

    date, (page, week) = next(iter(dates.items()))
    record = f"The Week {week} record" if week else "The indexed record"
    answer = f"[S1] {record} lists {date} as the revised proposal deadline."
    if date.split()[1] != month[:3]:
        answer += f" That record does not support a move to {month}."
    return {"answer": f"{answer} {guidance}", "sources": cited_sources([page]), "used_llm": False}


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


def check_safety(question: str, has_results: bool, *, proposed_month=None) -> dict:
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
    if not proposed_month and _match_any(STALE_DEADLINE_PATTERNS, question):
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
