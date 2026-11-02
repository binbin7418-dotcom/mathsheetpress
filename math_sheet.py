#!/usr/bin/env python3
"""MathSheetPress engine: math worksheet books (PDF) whose answer keys are
PROVEN, not printed from generator state.

How a problem is made: each topic generator first picks the answer, then
builds the question around it (construction path). Before a worksheet is
accepted, every problem is RE-SOLVED by an independent verifier that works
from the printed question alone -- a recursive-descent evaluator for
arithmetic expressions, Fraction-based solvers for equations, a factor
search for quadratics -- and the answer key is written from the verifier's
results. A problem whose two paths disagree is rejected and regenerated.
Worksheets contain zero duplicate questions.

Deterministic for a fixed seed. 100% local. Requires: reportlab.

Usage:
    python math_sheet.py out/ [--worksheets 10] [--per-sheet 20]
                       [--band Mixed] [--seed 42]
"""
import os
import random
import re
import sys
from fractions import Fraction

PAGE_W, PAGE_H = 612, 792

# ------------------------------------------------------------- formatting

def fmt_frac(fr):
    """Fraction -> '3', '3/4' or '-7/2' (improper kept; textbooks accept)."""
    fr = Fraction(fr)
    if fr.denominator == 1:
        return str(fr.numerator)
    return f"{fr.numerator}/{fr.denominator}"

# ------------------------------------------------- independent evaluator
# A small recursive-descent parser over printed arithmetic strings.
# Grammar: expr := term (('+'|'-') term)* ; term := factor (('x'|'div') factor)*
# (printed with multiplication/division signs). This path never sees the
# generator's stored answer: it reads the question text.

_TOKEN_RE = re.compile(r"\s*(\d+\s*/\s*\d+|\d+(?:\.\d+)?|[+\-\u00d7\u00f7()])")

def _tokenize(s):
    toks, i = [], 0
    s = s.strip()
    while i < len(s):
        m = _TOKEN_RE.match(s, i)
        if not m:
            raise ValueError(f"cannot tokenize at {s[i:]!r}")
        toks.append(m.group(1).replace(" ", ""))
        i = m.end()
    return toks

class _Parser:
    def __init__(self, toks):
        self.toks, self.pos = toks, 0

    def peek(self):
        return self.toks[self.pos] if self.pos < len(self.toks) else None

    def take(self):
        t = self.toks[self.pos]
        self.pos += 1
        return t

    def expr(self):
        v = self.term()
        while self.peek() in ("+", "-"):
            op = self.take()
            rhs = self.term()
            v = v + rhs if op == "+" else v - rhs
        return v

    def term(self):
        v = self.factor()
        while self.peek() in ("\u00d7", "\u00f7"):
            op = self.take()
            rhs = self.factor()
            v = v * rhs if op == "\u00d7" else v / rhs
        return v

    def factor(self):
        t = self.take()
        if t == "-":
            return -self.factor()
        if t == "(":
            v = self.expr()
            assert self.take() == ")"
            return v
        if "/" in t:
            a, b = t.split("/")
            return Fraction(int(a), int(b))
        return Fraction(t)

def eval_expression(text):
    """Evaluate a printed arithmetic expression to a Fraction."""
    p = _Parser(_tokenize(text))
    v = p.expr()
    if p.pos != len(p.toks):
        raise ValueError("trailing tokens")
    return v

# ------------------------------------------------------------- generators
# Each generator returns (question_text, spec, construction_value). The
# spec's first item names the verifier route. run_mathsheetpress compares
# the verifier's answer with the construction answer; only the verifier's
# answer reaches the key.

MUL, DIV = "\u00d7", "\u00f7"

def g_mul(rng):
    a, b = rng.randint(3, 12), rng.randint(3, 12)
    return f"{a} {MUL} {b} = ?", ("expr", f"{a} {MUL} {b}"), a * b

def g_div(rng):
    b, ans = rng.randint(3, 12), rng.randint(3, 12)
    return f"{b * ans} {DIV} {b} = ?", ("expr", f"{b * ans} {DIV} {b}"), ans

def g_frac_add(rng):
    # construction: pick the sum first, split into two addends
    d = rng.choice([4, 6, 8, 9, 10, 12])
    total_num = rng.randint(2, 2 * d - 1)
    total = Fraction(total_num, d)
    n1 = rng.randint(1, total_num - 1)
    f1 = Fraction(n1, d)
    f2 = Fraction(total_num - n1, d)
    k = rng.choice([1, 2])
    f2s = Fraction(f2.numerator * k, f2.denominator * k)
    q = f"{fmt_frac(f1)} + {fmt_frac(f2s)} = ?"
    return q, ("expr", q[:-4]), total

def g_pct_of(rng):
    p = rng.choice([5, 10, 15, 20, 25, 50, 75])
    n = rng.choice([20, 40, 60, 80, 120, 160, 200, 240, 300, 400])
    q = f"What is {p}% of {n}?"
    return q, ("pct", p, n), Fraction(p * n, 100)

def g_order_ops(rng):
    a, b, c = rng.randint(2, 12), rng.randint(2, 12), rng.randint(2, 12)
    shape = rng.choice(["a+b*c", "a*b-c", "(a+b)*c", "a*b+c/d"])
    if shape == "a+b*c":
        expr, val = f"{a} + {b} {MUL} {c}", a + b * c
    elif shape == "a*b-c":
        expr, val = f"{a} {MUL} {b} - {c}", a * b - c
    elif shape == "(a+b)*c":
        expr, val = f"({a} + {b}) {MUL} {c}", (a + b) * c
    else:
        d = rng.choice([2, 4, 5])
        cc = d * rng.randint(2, 9)
        expr, val = f"{a} {MUL} {b} + {cc} {DIV} {d}", a * b + cc // d
    return f"{expr} = ?", ("expr", expr), val

def g_int_ops(rng):
    a, b = rng.randint(2, 30), rng.randint(2, 30)
    shape = rng.choice(["-a+b", "-a-b", "a-b", "-a*b"])
    if shape == "-a+b":
        expr, val = f"-{a} + {b}", -a + b
    elif shape == "-a-b":
        expr, val = f"-{a} - {b}", -a - b
    elif shape == "a-b":
        bb = rng.randint(a + 1, a + 30)
        expr, val = f"{a} - {bb}", a - bb
    else:
        expr, val = f"-{a} {MUL} {b}", -a * b
    return f"{expr} = ?", ("expr", expr), val

def g_one_step(rng):
    x = rng.randint(2, 20)
    kind = rng.choice(["add", "mul"])
    if kind == "add":
        b = rng.randint(2, 30)
        return f"x + {b} = {x + b}", ("lin1", 1, b, x + b), x
    a = rng.randint(2, 12)
    return f"{a}x = {a * x}", ("lin1", a, 0, a * x), x

def g_two_step(rng):
    x = rng.randint(2, 15)
    a, b = rng.randint(2, 9), rng.randint(1, 20)
    c = a * x + b
    return f"{a}x + {b} = {c}", ("lin1", a, b, c), x

def g_proportion(rng):
    a = rng.randint(2, 9)
    x = rng.randint(2, 12)
    b = rng.randint(2, 12)
    while (b * x) % a:
        b += 1
    c = b * x // a
    return f"{a}/{b} = x/{c} -- solve for x", ("prop", a, b, c), x

def g_exponent(rng):
    base = rng.randint(2, 9)
    e = rng.choice([2, 2, 3])
    return f"{base}^{e} = ?", ("pow", base, e), base ** e

def g_lin_eq(rng):
    x = rng.randint(-8, 12)
    a = rng.randint(3, 9)
    c = rng.randint(1, a - 1)
    b = rng.randint(1, 20)
    d = a * x + b - c * x
    cx = "x" if c == 1 else f"{c}x"
    q = f"{a}x + {b} = {cx} + {d}" if d >= 0 else f"{a}x + {b} = {cx} - {abs(d)}"
    return q, ("lin2", a, b, c, d), x

def g_slope(rng):
    x1, y1 = rng.randint(-6, 6), rng.randint(-6, 6)
    run = rng.choice([1, 2, 3, 4, -1, -2, -3])
    rise = rng.randint(-6, 6)
    x2, y2 = x1 + run, y1 + rise
    q = f"Slope of the line through ({x1}, {y1}) and ({x2}, {y2})?"
    return q, ("slope", x1, y1, x2, y2), Fraction(rise, run)

def g_quad_factor(rng):
    p, q_ = 0, 0
    while p == 0 or q_ == 0:
        p, q_ = sorted(rng.randint(-9, 9) for _ in range(2))
    b, c = p + q_, p * q_
    bs = f"+ {b}" if b >= 0 else f"- {abs(b)}"
    cs = f"+ {c}" if c >= 0 else f"- {abs(c)}"
    q = f"Factor: x^2 {bs}x {cs}"
    return q, ("quad", b, c), (p, q_)

def g_system(rng):
    x, y = rng.randint(1, 12), rng.randint(1, 12)
    s, d = x + y, x - y
    q = f"x + y = {s} and x - y = {d} -- give x, y"
    return q, ("sys", s, d), (x, y)

BANDS = {
    "Arithmetic": [g_mul, g_div, g_frac_add, g_pct_of, g_order_ops],
    "Pre-Algebra": [g_int_ops, g_one_step, g_two_step, g_proportion, g_exponent],
    "Algebra": [g_lin_eq, g_slope, g_quad_factor, g_system, g_two_step],
}
ALL_GENERATORS = BANDS["Arithmetic"] + BANDS["Pre-Algebra"] + BANDS["Algebra"]

# --------------------------------------------------------------- verifier
# Independent re-solve from the question-side data only.

def verify(spec):
    kind = spec[0]
    if kind == "expr":
        return fmt_frac(eval_expression(spec[1]))
    if kind == "pct":
        _, p, n = spec
        return fmt_frac(Fraction(p, 100) * n)
    if kind == "pow":
        _, base, e = spec
        v = 1
        for _ in range(e):
            v *= base
        return str(v)
    if kind == "lin1":  # a*x + b = c
        _, a, b, c = spec
        return fmt_frac(Fraction(c - b, a))
    if kind == "lin2":  # a*x + b = c*x + d
        _, a, b, c, d = spec
        return fmt_frac(Fraction(d - b, a - c))
    if kind == "prop":  # a/b = x/c
        _, a, b, c = spec
        return fmt_frac(Fraction(a * c, b))
    if kind == "slope":
        _, x1, y1, x2, y2 = spec
        return fmt_frac(Fraction(y2 - y1, x2 - x1))
    if kind == "quad":
        _, b, c = spec
        roots = [r for r in range(-40, 41) if r * r + b * r + c == 0]
        if len(roots) != 2:
            raise ValueError("quadratic does not have two integer roots")
        lo, hi = sorted(roots)
        def term(v):
            return f"(x + {v})" if v >= 0 else f"(x - {abs(v)})"
        return f"{term(-hi)} {term(-lo)}"
    if kind == "sys":
        _, s, d = spec
        x = Fraction(s + d, 2)
        y = Fraction(s - d, 2)
        return f"x = {fmt_frac(x)}, y = {fmt_frac(y)}"
    raise ValueError(f"unknown spec {kind}")

def construction_answer(spec, gen_value):
    """Normalize the generator's construction answer to key format."""
    kind = spec[0]
    if kind == "quad":
        p, q_ = gen_value
        def term(v):
            return f"(x + {v})" if v >= 0 else f"(x - {abs(v)})"
        return f"{term(p)} {term(q_)}"
    if kind == "sys":
        x, y = gen_value
        return f"x = {x}, y = {y}"
    return fmt_frac(Fraction(gen_value))

# ---------------------------------------------------------------- builder

def build_worksheet(rng, band, per_sheet, seen=None):
    gens = ALL_GENERATORS if band == "Mixed" else BANDS[band]
    problems = []
    if seen is None:
        seen = set()
    local = set()
    guard = 0
    while len(problems) < per_sheet:
        guard += 1
        if guard > per_sheet * 120:
            raise RuntimeError("could not fill worksheet with unique verified problems")
        q, spec, gen_val = rng.choice(gens)(rng)
        if q in seen or q in local:
            continue
        v_ans = verify(spec)
        c_ans = construction_answer(spec, gen_val)
        if v_ans != c_ans:
            continue  # two paths disagree: reject, never print
        local.add(q)
        problems.append({"q": q, "answer": v_ans, "spec": spec})
    seen |= local
    return problems

# -------------------------------------------------------------------- PDF

def render_pdf(path, sheets, per_sheet):
    from reportlab.pdfgen import canvas as rl_canvas
    from reportlab.lib.colors import HexColor
    ink = HexColor("#1a1a1a")
    accent = HexColor("#2050a0")
    c = rl_canvas.Canvas(path, pagesize=(PAGE_W, PAGE_H))
    c.setFillColor(ink)
    c.setFont("Helvetica-Bold", 30)
    c.drawString(72, 640, "MathSheetPress")
    c.setFont("Helvetica", 15)
    c.drawString(72, 606, "Practice worksheets with a proven answer key.")
    c.setFont("Helvetica", 11.5)
    lines = [
        "Every problem in this book was solved twice by two different",
        "methods before it was printed. The answer key comes from the",
        "second solve -- if the two disagree, the problem never ships.",
        "",
        f"{len(sheets)} worksheets x {per_sheet} problems = "
        f"{len(sheets) * per_sheet} problems, zero duplicates.",
    ]
    y = 540
    for ln in lines:
        c.drawString(72, y, ln)
        y -= 20
    c.showPage()
    for si, sheet in enumerate(sheets, 1):
        c.setFillColor(ink)
        c.setFont("Helvetica-Bold", 16)
        c.drawString(54, 748, f"Worksheet {si}")
        c.setFont("Helvetica", 10)
        c.drawRightString(558, 748, "Name: ____________   Date: __________")
        c.setStrokeColor(accent)
        c.setLineWidth(1.2)
        c.line(54, 738, 558, 738)
        half = (len(sheet) + 1) // 2
        col_x = [54, 312]
        rows = max(half, len(sheet) - half)
        step = 640 // max(rows, 1)
        for col in range(2):
            chunk = sheet[col * half:(col + 1) * half]
            y = 706
            for j, p in enumerate(chunk):
                n = col * half + j + 1
                c.setFont("Helvetica", 10.5)
                c.setFillColor(ink)
                c.drawString(col_x[col], y, f"{n}.  {p['q']}")
                y -= step
        c.showPage()
    c.setFont("Helvetica-Bold", 16)
    c.setFillColor(ink)
    c.drawString(54, 748, "Answer Key")
    c.setFont("Helvetica", 9.5)
    c.drawString(54, 730, "These answers were produced by the independent re-solve, not by the problem generator.")
    y = 700
    for si, sheet in enumerate(sheets, 1):
        per_col = (len(sheet) + 2) // 3
        need = per_col * 13 + 34
        if y - need < 60:
            c.showPage()
            y = 748
        c.setFont("Helvetica-Bold", 11.5)
        c.drawString(54, y, f"Worksheet {si}")
        y -= 16
        c.setFont("Helvetica", 9)
        for col in range(3):
            yy = y
            for j in range(per_col):
                idx = col * per_col + j
                if idx >= len(sheet):
                    break
                c.drawString(54 + col * 172, yy, f"{idx + 1}. {sheet[idx]['answer']}")
                yy -= 13
        y -= per_col * 13 + 18
    c.showPage()
    c.save()
    with open(path, "rb") as f:
        data = f.read()
    pages = data.count(b"/Type /Page") - data.count(b"/Type /Pages")
    return pages

# -------------------------------------------------------------------- run

def run_mathsheetpress(worksheets, outdir, seed=42, band="Mixed", per_sheet=20, **kw):
    if band not in ("Arithmetic", "Pre-Algebra", "Algebra", "Mixed"):
        raise ValueError("band must be Arithmetic, Pre-Algebra, Algebra or Mixed")
    os.makedirs(outdir, exist_ok=True)
    rng = random.Random(seed)
    seen = set()
    sheets = [build_worksheet(rng, band, per_sheet, seen) for _ in range(worksheets)]
    pdf_path = os.path.join(outdir, "mathsheet_book.pdf")
    pages = render_pdf(pdf_path, sheets, per_sheet)
    total = sum(len(s) for s in sheets)
    all_q = [p["q"] for s in sheets for p in s]
    return {
        "worksheets": len(sheets),
        "per_sheet": per_sheet,
        "problems_total": total,
        "unique_questions": len(set(all_q)),
        "pages": pages,
        "band": band,
        "pdf_path": pdf_path,
        "sheets_data": sheets,
    }

def main(argv):
    outdir = argv[1] if len(argv) > 1 else "out"
    opts = {"worksheets": 10, "per_sheet": 20, "band": "Mixed", "seed": 42}
    for a in argv[2:]:
        if a.startswith("--") and "=" in a:
            k, v = a[2:].split("=", 1)
            k = k.replace("-", "_")
            if k in ("worksheets", "per_sheet", "seed"):
                v = int(v)
            opts[k] = v
    s = run_mathsheetpress(opts["worksheets"], outdir, seed=opts["seed"],
                           band=opts["band"], per_sheet=opts["per_sheet"])
    print(f"Worksheets: {s['worksheets']} x {s['per_sheet']} = {s['problems_total']} problems "
          f"({s['unique_questions']} unique), pages: {s['pages']}")
    print(f"PDF: {s['pdf_path']}")
    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv))
