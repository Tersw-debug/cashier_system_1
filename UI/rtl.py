"""Compatibility shim.

Qt shapes and reorders Arabic correctly on its own (and mirrors layouts via
QApplication.setLayoutDirection), so the Tk word-reversal hack is gone.
``fix`` is kept as a no-op so legacy ``from UI.rtl import fix`` imports keep
working while the remaining screens are ported. Delete this file (and the
imports) once every module is on PySide6.
"""


def fix(text):
    return text


def install():
    """No-op: nothing to patch under Qt."""
    return None