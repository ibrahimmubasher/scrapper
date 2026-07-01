"""
scraper/services/logger.py

FIXED VERSION — forces UTF-8 output so any Unicode character
(arrows ->, em-dashes, accented characters, etc.) never crashes
print() on Windows, where the default console encoding is
cp1252/charmap and can't represent many Unicode characters.

This replaces ad-hoc per-character replacement with a robust
approach: reconfigure stdout to UTF-8 once, then just print
normally everywhere.
"""

import sys
import io


def _ensure_utf8_stdout():
    """
    Reconfigures sys.stdout to use UTF-8 encoding.
    Safe to call multiple times. Works on Windows and
    other local development environments without breaking anything.
    """

    try:
        # Python 3.7+ supports reconfigure()
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        # Fallback for older Python or unusual stream types
        sys.stdout = io.TextIOWrapper(
            sys.stdout.buffer,
            encoding="utf-8",
            errors="replace",
            line_buffering=True
        )
        sys.stderr = io.TextIOWrapper(
            sys.stderr.buffer,
            encoding="utf-8",
            errors="replace",
            line_buffering=True
        )


# Run once on import
_ensure_utf8_stdout()


def safe_print(text):
    """
    Prints text safely. With UTF-8 stdout now configured,
    this just prints normally — no more character-by-character
    replacement needed. Kept as a function for backward
    compatibility with existing `print = safe_print` usage.
    """

    text = str(text)

    try:
        print(text)
    except UnicodeEncodeError:
        # Extremely defensive fallback — should rarely trigger
        # now that stdout is UTF-8, but just in case
        print(text.encode("utf-8", "replace").decode("utf-8"))