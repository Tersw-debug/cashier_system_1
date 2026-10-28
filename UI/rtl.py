"""Makes Arabic render correctly in Tk (which has no bidi support). v2: patches Tk itself."""
import re
import tkinter as tk
from tkinter import ttk, messagebox
import customtkinter as ctk

# "words": reverse word order only (letters already look fine)
# "full":  arabic_reshaper + python-bidi (letters are disconnected/reversed too)
MODE = "words"

_AR = re.compile(r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]")


def _fix_line(line: str) -> str:
    if MODE == "full":
        import arabic_reshaper
        from bidi.algorithm import get_display
        return get_display(arabic_reshaper.reshape(line))
    return " ".join(reversed(line.split(" ")))


def fix(text):
    """Logical Arabic -> what Tk should draw. Non-Arabic text is returned untouched."""
    if not isinstance(text, str) or not _AR.search(text):
        return text
    return "\n".join(_fix_line(line) for line in text.split("\n"))


_installed = False


def install():
    """Call once in main.py, before creating any window."""
    global _installed
    if _installed:
        return
    _installed = True

    # 1) Every widget option named "text" (CTk labels/buttons/checkboxes, tk, ttk, canvas)
    orig_options = tk.Misc._options

    def _options(self, cnf, kw=None):
        merged = dict(tk._cnfmerge((cnf, kw)) if kw else tk._cnfmerge(cnf))
        if "text" in merged:
            merged["text"] = fix(merged["text"])
        return orig_options(self, merged)

    tk.Misc._options = _options

    # 2) Entry placeholders (CTk inserts these directly, not via options)
    for name in ("__init__", "configure"):
        orig = getattr(ctk.CTkEntry, name)

        def wrapper(self, *a, _orig=orig, **kw):
            if "placeholder_text" in kw:
                kw["placeholder_text"] = fix(kw["placeholder_text"])
            return _orig(self, *a, **kw)

        setattr(ctk.CTkEntry, name, wrapper)

    # 3) Window titles
    for cls in (ctk.CTk, ctk.CTkToplevel):
        orig_title = cls.title
        cls.title = (lambda self, string=None, _o=orig_title:
                     _o(self, fix(string)) if string is not None else _o(self))

    # 4) Treeview headings
    orig_heading = ttk.Treeview.heading

    def heading(self, column, option=None, **kw):
        if "text" in kw:
            kw["text"] = fix(kw["text"])
        return orig_heading(self, column, option, **kw)

    ttk.Treeview.heading = heading

    # 5) Message boxes
    for name in ("showinfo", "showwarning", "showerror", "askyesno", "askokcancel", "askquestion"):
        def make(orig):
            def wrapper(title=None, message=None, **kw):
                return orig(fix(title), fix(message), **kw)
            return wrapper
        setattr(messagebox, name, make(getattr(messagebox, name)))