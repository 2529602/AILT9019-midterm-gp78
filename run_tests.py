"""
Evaluation runner — executes the 8 test cases from evaluation_cases.csv
and reports pass/fail results.

Usage:
    python run_tests.py            # run all cases
    python run_tests.py --verbose  # show full answers
"""

import csv
import json
import sys
import os
import urllib.request
import urllib.error

import config


def run_case(question: str) -> dict:
    """Send a question to the running server and get the answer."""
    payload = json.dumps({"question": question}).encode("utf-8")
    req = urllib.request.Request(
        f"http://{config.HOST}:{config.PORT}/api/answer",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except urllib.error.URLError as e:
        return {"error": f"Cannot reach server: {e}"}


def evaluate(case: dict, result: dict) -> tuple[bool, str]:
    """Return (passed, reason) for a single case."""
    if "error" in result:
        return False, result["error"]

    case_type = case["type"]
    answer = result.get("answer", "")
    sources = result.get("sources", [])
    safety_info = result.get("safety", {})

    if case_type == "normal":
        # Must have an answer and at least one source
        if not answer:
            return False, "No answer returned"
        if not sources:
            return False, "No sources cited for a normal question"
        return True, f"Answer: {answer[:80]}... | Sources: {len(sources)}"

    elif case_type == "safe_failure":
        # Must be refused or redirected
        refused = safety_info.get("refused", False)
        has_sources = len(sources) > 0
        # Safe-failure cases should either be refused by safety module
        # or have no sources (cannot verify)
        if refused or not has_sources:
            return True, f"Safe-failure handled: answer={answer[:80]}..."
        else:
            return False, (
                f"Expected safe-failure but got answer with {len(sources)} sources. "
                f"Answer: {answer[:80]}..."
            )

    return False, f"Unknown case type: {case_type}"


def main():
    csv_path = os.path.join(os.path.dirname(__file__), "evaluation_cases.csv")
    verbose = "--verbose" in sys.argv

    print("=" * 60)
    print("AILT9019 Q&A — Evaluation Test Runner")
    print("=" * 60)

    with open(csv_path, "r", encoding="utf-8-sig") as f:
        cases = list(csv.DictReader(f))

    print(f"Loaded {len(cases)} test cases.\n")

    passed = 0
    failed = 0
    results_log = []

    for case in cases:
        cid = case["case_id"]
        q = case["question"]
        expected = case["expected_behavior"]

        print(f"[{cid}] ({case['type']}) Q: {q}")
        result = run_case(q)
        ok, reason = evaluate(case, result)

        if ok:
            passed += 1
            print(f"  -> PASS: {reason}")
        else:
            failed += 1
            print(f"  -> FAIL: {reason}")

        if verbose:
            answer = result.get("answer", "N/A")
            sources = result.get("sources", [])
            print(f"     Answer: {answer}")
            for s in sources:
                print(f"     [{s.get('label')}] {s.get('doc_name')} p{s.get('page_num')}")
            print()

        results_log.append({
            "case_id": cid,
            "type": case["type"],
            "question": q,
            "passed": ok,
            "reason": reason,
            "answer": result.get("answer", ""),
            "sources_count": len(result.get("sources", [])),
        })

    print("\n" + "=" * 60)
    print(f"Results: {passed}/{len(cases)} passed, {failed} failed")
    threshold = 7
    print(f"Threshold: {threshold}/{len(cases)} required")
    if passed >= threshold:
        print("STATUS: GOOD ENOUGH")
    else:
        print("STATUS: BELOW THRESHOLD — review failures")

    # Write test log
    log_path = os.path.join(os.path.dirname(__file__), "test_log.json")
    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(results_log, f, indent=2, ensure_ascii=False)
    print(f"\nTest log saved to: {log_path}")


if __name__ == "__main__":
    main()
