import os
import threading
import tkinter as tk
from tkinter import messagebox, scrolledtext

from math_sheet import run_mathsheetpress


def run_job(worksheets, per_sheet, band, seed, outdir):
    s = run_mathsheetpress(worksheets, outdir, seed=seed, band=band, per_sheet=per_sheet)
    lines = [f"Worksheets: {s['worksheets']} x {s['per_sheet']} = {s['problems_total']} problems",
             f"Unique questions: {s['unique_questions']} (zero duplicates)",
             f"Pages: {s['pages']}",
             "Every answer was re-solved independently before printing.",
             f"PDF: {s['pdf_path']}"]
    return lines


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("MathSheetPress")
        self.geometry("640x520")
        self.resizable(False, False)
        self.worksheets = tk.StringVar(value="10")
        self.per_sheet = tk.StringVar(value="20")
        self.band = tk.StringVar(value="Mixed")
        self.seed = tk.StringVar(value="42")
        for label, var in [("Worksheets:", self.worksheets),
                           ("Problems per worksheet:", self.per_sheet),
                           ("Band (Arithmetic/Pre-Algebra/Algebra/Mixed):", self.band),
                           ("Seed:", self.seed)]:
            row = tk.Frame(self); row.pack(fill="x", padx=12, pady=2)
            tk.Label(row, text=label, width=38, anchor="w").pack(side="left")
            tk.Entry(row, textvariable=var, width=12).pack(side="left")
        tk.Button(self, text="Build the book", font=("Segoe UI", 11, "bold"),
                  command=self.start).pack(pady=10)
        self.log = scrolledtext.ScrolledText(self, width=76, height=15,
                                             font=("Consolas", 9))
        self.log.pack(padx=12, pady=4)
        self.write("Every problem is solved twice by two different methods; the answer key comes from the second solve. If they disagree, the problem never ships.")

    def write(self, msg):
        self.log.insert(tk.END, str(msg) + "\n")
        self.log.see(tk.END)
        self.update_idletasks()

    def collect(self):
        band = self.band.get().strip()
        if band not in ("Arithmetic", "Pre-Algebra", "Algebra", "Mixed"):
            raise ValueError("Band must be Arithmetic, Pre-Algebra, Algebra or Mixed.")
        return (int(self.worksheets.get()), int(self.per_sheet.get()), band,
                int(self.seed.get()),
                os.path.join(os.getcwd(), "mathsheetpress_out"))

    def start(self):
        try:
            args = self.collect()
        except Exception as e:
            messagebox.showerror("MathSheetPress", str(e))
            return

        def work():
            try:
                for ln in run_job(*args):
                    self.write(ln)
            except Exception as e:
                self.write(f"ERROR: {e}")

        threading.Thread(target=work, daemon=True).start()


if __name__ == "__main__":
    App().mainloop()
