#!/usr/bin/env python3
"""MathSheetPress acceptance test.

Seeded-defect method: the engine's claim is 'the answer key is proven'.
We (1) build a real book, (2) re-solve every problem a THIRD way (Python
eval on the translated expression for arithmetic items; the engine's
independent verifier for the rest), (3) corrupt one printed answer and
confirm the gate flags exactly that one (a checker that cannot fail is
not a checker), (4) confirm zero duplicate questions book-wide,
(5) confirm PDF geometry, (6) confirm determinism.
"""
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from math_sheet import run_mathsheetpress, verify, eval_expression  # noqa: E402

OUT = os.path.join(os.path.dirname(__file__), "out")
results = []

def check(name, ok, detail=""):
    results.append((name, ok, detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {name} {detail}")

def third_path_answer(p):
    """Re-solve expression problems with Python's own evaluator on a
    translated string -- a path that shares no code with the engine."""
    q = p["q"]
    m = re.match(r"^(.*) = \?$", q)
    if m and p["spec"][0] == "expr":
        expr = m.group(1).replace("\u00d7", "*").replace("\u00f7", "/")
        from fractions import Fraction
        v = eval(expr, {"__builtins__": {}}, {})
        fr = Fraction(v).limit_denominator(1000)
        return str(fr.numerator) if fr.denominator == 1 else f"{fr.numerator}/{fr.denominator}"
    return None

def main():
    s = run_mathsheetpress(4, OUT, seed=42, band="Mixed", per_sheet=12)
    check("counts", s["worksheets"] == 4 and s["problems_total"] == 48,
          f"({s['worksheets']} sheets, {s['problems_total']} problems)")
    check("book-wide zero duplicates", s["unique_questions"] == s["problems_total"],
          f"({s['unique_questions']} unique of {s['problems_total']})")

    all_p = [p for sh in s["sheets_data"] for p in sh]
    bad = [p for p in all_p if verify(p["spec"]) != p["answer"]]
    check("verifier agrees with every printed answer", not bad,
          f"({len(all_p) - len(bad)}/{len(all_p)})")

    third, third_bad = 0, 0
    for p in all_p:
        t = third_path_answer(p)
        if t is not None:
            third += 1
            if t != p["answer"]:
                third_bad += 1
    check("third-path eval agrees on expression problems", third > 10 and third_bad == 0,
          f"({third} expression problems re-evaluated, {third_bad} disagreements)")

    # negative control: corrupt exactly one answer; the gate must flag 1
    victim = all_p[0]
    orig = victim["answer"]
    victim["answer"] = orig + " (corrupted)"
    flagged = [p for p in all_p if verify(p["spec"]) != p["answer"]]
    check("gate flags exactly the corrupted answer", len(flagged) == 1 and flagged[0] is victim,
          f"({len(flagged)} flagged)")
    victim["answer"] = orig

    with open(s["pdf_path"], "rb") as f:
        data = f.read()
    check("PDF is 612x792pt", b"612 792" in data, "")
    pages = data.count(b"/Type /Page") - data.count(b"/Type /Pages")
    check("PDF pages = title + 4 sheets + key (>=6)", pages >= 6 and pages == s["pages"],
          f"({pages} pages)")

    s2 = run_mathsheetpress(4, OUT, seed=42, band="Mixed", per_sheet=12)
    same = [p["q"] for sh in s["sheets_data"] for p in sh] == \
           [p["q"] for sh in s2["sheets_data"] for p in sh]
    check("deterministic for fixed seed", same, "")

    sa = run_mathsheetpress(2, OUT, seed=7, band="Arithmetic", per_sheet=10)
    kinds = {p["spec"][0] for sh in sa["sheets_data"] for p in sh}
    check("Arithmetic band stays in-band", kinds <= {"expr", "pct"},
          f"(kinds: {sorted(kinds)})")

    npass = sum(1 for _, ok, _ in results if ok)
    print(f"\n{npass}/{len(results)} PASS")
    with open(os.path.join(os.path.dirname(__file__), "acceptance_results.txt"), "w") as f:
        for name, ok, detail in results:
            f.write(f"[{'PASS' if ok else 'FAIL'}] {name} {detail}\n")
        f.write(f"\n{npass}/{len(results)} PASS\n")
    return 0 if npass == len(results) else 1

if __name__ == "__main__":
    sys.exit(main())
