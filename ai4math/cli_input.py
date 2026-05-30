"""Interactive prompt helpers for the AI4Math REPL.

Replaces the previous `console.input()` (Python ``input()`` + GNU readline)
with a `prompt_toolkit`-based prompt. Two motivations:

* `@<path>` Tab completion so questions can reference files on disk.
* Correct CJK editing. GNU readline asks the terminal to back up by one column
  per backspace, but a CJK character occupies two columns; the cursor drifts
  and stale glyphs linger. `prompt_toolkit` uses ``wcwidth`` and redraws the
  visible region, so wide characters erase cleanly.

The module degrades gracefully if `prompt_toolkit` is missing or stdin is not
a TTY — callers fall back to ``console.input``.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from typing import Callable

try:
    from prompt_toolkit import PromptSession
    from prompt_toolkit.completion import Completer, Completion, PathCompleter
    from prompt_toolkit.document import Document
    from prompt_toolkit.formatted_text import ANSI
    from prompt_toolkit.history import FileHistory, InMemoryHistory
    _HAS_PT = True
except ImportError:  # pragma: no cover — optional but listed in pyproject
    _HAS_PT = False


# `@token` — anything up to whitespace or another `@`. Trailing punctuation is
# trimmed inside the expander so `see @foo.md.` still resolves `foo.md`.
_AT_TOKEN_RE = re.compile(r"@([^\s@]+)")

# REPL slash commands offered as Tab completions.
_COMMANDS = (
    "/help", "/tools", "/reset", "/clear", "/copy", "/last",
    "/save", "/save last", "/ml", "/multiline", "/quit", "/exit",
)


# ---------------------------------------------------------------------------
# Completers
# ---------------------------------------------------------------------------

if _HAS_PT:

    class _AtPathCompleter(Completer):
        """Completes filesystem paths after an ``@`` sigil at the cursor."""

        def __init__(self) -> None:
            self._inner = PathCompleter(expanduser=True)

        def get_completions(self, document, complete_event):
            text = document.text_before_cursor
            m = re.search(r"@([^\s@]*)$", text)
            if m is None:
                return
            partial = m.group(1)
            # Re-anchor the inner PathCompleter at the path portion only.
            sub = Document(text=partial, cursor_position=len(partial))
            yield from self._inner.get_completions(sub, complete_event)

    class _CommandCompleter(Completer):
        """Completes ``/command`` names on the first token of the line."""

        def get_completions(self, document, complete_event):
            text = document.text_before_cursor
            if not text.startswith("/") or " " in text:
                return
            for cmd in _COMMANDS:
                if cmd.startswith(text):
                    yield Completion(cmd, start_position=-len(text))

    class _Combined(Completer):
        def __init__(self, *completers: Completer) -> None:
            self._cs = completers

        def get_completions(self, document, complete_event):
            for c in self._cs:
                yield from c.get_completions(document, complete_event)


# ---------------------------------------------------------------------------
# Session factory + prompt wrapper
# ---------------------------------------------------------------------------

def make_session(history_file: str | None = None):
    """Build a PromptSession with ``@`` and slash completion.

    Returns ``None`` when prompt_toolkit is unavailable so callers can fall
    back without branching twice.
    """
    if not _HAS_PT:
        return None
    history = FileHistory(history_file) if history_file else InMemoryHistory()
    completer = _Combined(_AtPathCompleter(), _CommandCompleter())
    return PromptSession(
        completer=completer,
        history=history,
        complete_while_typing=False,
        enable_suspend=True,
    )


def prompt_line(
    session,
    rich_markup_prompt: str,
    *,
    fallback: Callable[[str], str],
) -> str:
    """Read one line.

    `rich_markup_prompt` is the prompt string with Rich markup. When the
    prompt_toolkit session is active, the markup is rewritten to ANSI; when
    falling back, the original markup is passed to ``console.input``.
    """
    if session is None or not sys.stdin.isatty():
        return fallback(rich_markup_prompt)
    return session.prompt(ANSI(_rich_to_ansi(rich_markup_prompt)))


# Minimal Rich-markup → ANSI conversion. Only covers the colors/weights used
# by the REPL prompts; anything else collapses to the inner text.
_RICH_STYLE_TO_SGR = {
    "bold": "1",
    "dim": "2",
    "red": "31", "green": "32", "yellow": "33",
    "blue": "34", "magenta": "35", "cyan": "36", "white": "37",
}


def _rich_to_ansi(s: str) -> str:
    def _open(m: re.Match) -> str:
        styles = m.group(1).split()
        codes = [_RICH_STYLE_TO_SGR[st] for st in styles if st in _RICH_STYLE_TO_SGR]
        return f"\x1b[{';'.join(codes)}m" if codes else ""

    out = re.sub(r"\[/[^\]]*\]", "\x1b[0m", s)
    out = re.sub(r"\[([^/\]]+)\]", _open, out)
    return out


# ---------------------------------------------------------------------------
# @<path> expansion
# ---------------------------------------------------------------------------

# Hard cap per inlined file. Generous for math problem statements; keeps a
# stray `@/var/log/syslog` from blowing up the prompt.
_MAX_INLINE_BYTES = 256 * 1024


def expand_at_paths(
    text: str,
    *,
    base_dir: Path | None = None,
) -> tuple[str, list[str]]:
    """Inline ``@<path>`` tokens that resolve to readable UTF-8 files.

    A token is left untouched when the path does not resolve, the file is
    binary, exceeds the size cap, or cannot be read. This keeps prose like
    "see the @reference variable" intact when no such file exists.

    Returns ``(expanded_text, [absolute_paths_inlined])``.
    """
    base = base_dir or Path.cwd()
    inlined: list[str] = []

    def _replace(match: re.Match) -> str:
        raw = match.group(1)
        # Trim trailing prose punctuation: "see @foo.md." → path "foo.md".
        trailing = ""
        while raw and raw[-1] in ",.;:!?)]}":
            trailing = raw[-1] + trailing
            raw = raw[:-1]
        if not raw:
            return match.group(0)

        candidate = Path(os.path.expanduser(raw))
        if not candidate.is_absolute():
            candidate = base / candidate
        try:
            resolved = candidate.resolve(strict=False)
            if not resolved.is_file():
                return match.group(0)
            if resolved.stat().st_size > _MAX_INLINE_BYTES:
                return match.group(0)
            content = resolved.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return match.group(0)

        inlined.append(str(resolved))
        return (
            f"\n\n--- 文件: {resolved} ---\n"
            f"{content}\n"
            f"--- 文件结束 ---\n\n"
            f"{trailing}"
        )

    return _AT_TOKEN_RE.sub(_replace, text), inlined
