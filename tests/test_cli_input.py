"""Tests for cli_input: @<path> expansion + Rich→ANSI helper.

The prompt_toolkit session itself is exercised manually — these tests cover
the deterministic helpers wired into the REPL.
"""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from ai4math.cli_input import _rich_to_ansi, expand_at_paths


class TestExpandAtPaths(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _write(self, name: str, content: str) -> Path:
        p = self.base / name
        p.write_text(content, encoding="utf-8")
        return p

    def test_inlines_existing_file(self):
        self._write("q.md", "求 ∫ x^2 dx")
        text = "请看 @q.md 这道题"
        out, inlined = expand_at_paths(text, base_dir=self.base)
        self.assertIn("求 ∫ x^2 dx", out)
        self.assertEqual(len(inlined), 1)
        self.assertTrue(inlined[0].endswith("q.md"))

    def test_leaves_unresolved_token_intact(self):
        text = "see the @reference variable"
        out, inlined = expand_at_paths(text, base_dir=self.base)
        self.assertEqual(out, text)
        self.assertEqual(inlined, [])

    def test_strips_trailing_punctuation_when_resolving(self):
        self._write("foo.md", "hello")
        text = "see @foo.md."
        out, inlined = expand_at_paths(text, base_dir=self.base)
        self.assertEqual(len(inlined), 1)
        # The trailing dot is preserved in the output.
        self.assertTrue(out.rstrip().endswith("."))
        self.assertIn("hello", out)

    def test_multiple_tokens(self):
        self._write("a.md", "AAA")
        self._write("b.md", "BBB")
        text = "compare @a.md and @b.md"
        out, inlined = expand_at_paths(text, base_dir=self.base)
        self.assertEqual(len(inlined), 2)
        self.assertIn("AAA", out)
        self.assertIn("BBB", out)

    def test_skips_oversized_file(self):
        big = self.base / "big.bin"
        # Just over the 256 KiB cap.
        big.write_bytes(b"x" * (256 * 1024 + 1))
        text = "@big.bin"
        out, inlined = expand_at_paths(text, base_dir=self.base)
        self.assertEqual(inlined, [])
        self.assertEqual(out, text)

    def test_skips_binary_file(self):
        b = self.base / "blob.bin"
        b.write_bytes(b"\xff\xfe\x00\x01garbage")
        text = "@blob.bin"
        out, inlined = expand_at_paths(text, base_dir=self.base)
        self.assertEqual(inlined, [])
        self.assertEqual(out, text)

    def test_absolute_path(self):
        f = self._write("abs.md", "ABS")
        text = f"@{f}"
        out, inlined = expand_at_paths(text, base_dir=self.base)
        self.assertEqual(len(inlined), 1)
        self.assertIn("ABS", out)

    def test_tilde_expansion(self):
        # Build a token under $HOME that we control.
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", dir=os.path.expanduser("~"), delete=False
        ) as fh:
            fh.write("HOMEFILE")
            home_path = Path(fh.name)
        try:
            rel = "~/" + home_path.name
            text = f"@{rel}"
            out, inlined = expand_at_paths(text, base_dir=self.base)
            self.assertEqual(len(inlined), 1)
            self.assertIn("HOMEFILE", out)
        finally:
            home_path.unlink()

    def test_directory_is_not_inlined(self):
        (self.base / "sub").mkdir()
        text = "@sub"
        out, inlined = expand_at_paths(text, base_dir=self.base)
        self.assertEqual(inlined, [])
        self.assertEqual(out, text)


class TestRichToAnsi(unittest.TestCase):
    def test_open_and_close(self):
        out = _rich_to_ansi("[bold green]You > [/bold green]")
        # Bold = SGR 1, green = 32; close = SGR 0.
        self.assertIn("\x1b[1;32m", out)
        self.assertIn("\x1b[0m", out)
        self.assertIn("You > ", out)

    def test_unknown_style_collapses(self):
        out = _rich_to_ansi("[unknown]hi[/unknown]")
        self.assertIn("hi", out)
        # No partial SGR with empty body should sneak through.
        self.assertNotIn("\x1b[m", out)


if __name__ == "__main__":
    unittest.main()
