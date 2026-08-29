from __future__ import annotations

import collections.abc as cabc
import textwrap
from contextlib import contextmanager

from ._compat import _ansi_re
from ._compat import term_len


def _truncate_visible(text: str, n: int) -> str:
    """Return the longest prefix of ``text`` containing at most ``n`` visible
    characters.

    ANSI escape sequences inside the prefix are kept intact and do not count
    toward the visible width. A cut is never placed inside an escape sequence.
    """
    if n <= 0:
        return ""

    visible = 0
    i = 0
    cut = 0
    end = len(text)
    while i < end:
        m = _ansi_re.match(text, i)
        if m is not None:
            i = m.end()
            continue
        visible += 1
        i += 1
        cut = i
        if visible >= n:
            break
    return text[:cut]


class TextWrapper(textwrap.TextWrapper):
    """``textwrap.TextWrapper`` variant that measures widths by visible
    character count.

    ANSI escape sequences embedded in chunks, indents, or the placeholder are
    excluded from the width budget. Without this, styled help text (a styled
    ``Usage:`` prefix, a colorized option name, ...) would be wrapped earlier
    than its visible length warrants and tokens would split mid-word.
    """

    def _handle_long_word(
        self,
        reversed_chunks: list[str],
        cur_line: list[str],
        cur_len: int,
        width: int,
    ) -> None:
        space_left = max(width - cur_len, 1)

        if self.break_long_words:
            last = reversed_chunks[-1]
            cut = _truncate_visible(last, space_left)
            res = last[len(cut) :]
            cur_line.append(cut)
            reversed_chunks[-1] = res
        elif not cur_line:
            cur_line.append(reversed_chunks.pop())

    def _check_placeholder_fits(self) -> None:
        """Raise if the placeholder cannot fit alongside the active indent.

        Only relevant when :attr:`max_lines` limits the output; mirrors the
        guard at the top of :meth:`textwrap.TextWrapper._wrap_chunks`.
        """
        if self.max_lines is None:
            return

        if self.max_lines > 1:
            indent = self.subsequent_indent
        else:
            indent = self.initial_indent

        if term_len(indent) + term_len(self.placeholder.lstrip()) > self.width:
            raise ValueError("placeholder too large for max width")

    def _fill_line(self, chunks: list[str], width: int) -> tuple[list[str], int]:
        """Pop chunks onto a single line until the next one would overflow.

        Returns the accumulated line pieces and their visible length, after
        applying long-word handling and trailing-whitespace dropping.
        """
        cur_line: list[str] = []
        cur_len = 0

        while chunks:
            n = term_len(chunks[-1])

            if cur_len + n <= width:
                cur_line.append(chunks.pop())
                cur_len += n
            else:
                break

        if chunks and term_len(chunks[-1]) > width:
            self._handle_long_word(chunks, cur_line, cur_len, width)
            cur_len = sum(map(term_len, cur_line))

        if self.drop_whitespace and cur_line and cur_line[-1].strip() == "":
            cur_len -= term_len(cur_line[-1])
            del cur_line[-1]

        return cur_line, cur_len

    def _line_fits_in_max_lines(
        self, lines: list[str], chunks: list[str], cur_len: int, width: int
    ) -> bool:
        """Decide whether the current line can be emitted as-is.

        ``True`` when :attr:`max_lines` is unset, another line still remains in
        the budget, or this is the final line and its content fits.
        """
        if self.max_lines is None:
            return True

        if len(lines) + 1 < self.max_lines:
            return True

        is_last_meaningful_chunk = not chunks or (
            self.drop_whitespace and len(chunks) == 1 and not chunks[0].strip()
        )
        return is_last_meaningful_chunk and cur_len <= width

    def _append_truncated_line(
        self, lines: list[str], indent: str, cur_line: list[str], cur_len: int
    ) -> None:
        """Emit the final line ending in the placeholder when truncating.

        Drops trailing pieces until the placeholder fits, or falls back to
        appending it to the previous line / on a line of its own.
        """
        width = self.width - term_len(indent)

        while cur_line:
            if cur_line[-1].strip() and cur_len + term_len(self.placeholder) <= width:
                cur_line.append(self.placeholder)
                lines.append(indent + "".join(cur_line))
                return
            cur_len -= term_len(cur_line[-1])
            del cur_line[-1]

        if lines:
            prev_line = lines[-1].rstrip()
            if term_len(prev_line) + term_len(self.placeholder) <= self.width:
                lines[-1] = prev_line + self.placeholder
                return

        lines.append(indent + self.placeholder.lstrip())

    def _wrap_chunks(self, chunks: list[str]) -> list[str]:
        """Wrap chunks counting widths in visible characters.

        Mirrors the algorithm of :meth:`textwrap.TextWrapper._wrap_chunks`
        with every width measurement routed through
        :func:`click._compat.term_len` instead of :func:`len`, so ANSI escape
        bytes in chunks, indents, or the placeholder do not inflate the count.

        .. seealso::
            :class:`textwrap.TextWrapper` in the Python standard library documentation:
            https://docs.python.org/3/library/textwrap.html#textwrap.TextWrapper

            Reference implementation in CPython:
            https://github.com/python/cpython/blob/main/Lib/textwrap.py
        """
        if self.width <= 0:
            raise ValueError(f"invalid width {self.width!r} (must be > 0)")

        self._check_placeholder_fits()

        lines: list[str] = []
        chunks.reverse()

        while chunks:
            if lines:
                indent = self.subsequent_indent
            else:
                indent = self.initial_indent

            width = self.width - term_len(indent)

            if self.drop_whitespace and chunks[-1].strip() == "" and lines:
                del chunks[-1]

            cur_line, cur_len = self._fill_line(chunks, width)

            if not cur_line:
                continue

            if self._line_fits_in_max_lines(lines, chunks, cur_len, width):
                lines.append(indent + "".join(cur_line))
            else:
                self._append_truncated_line(lines, indent, cur_line, cur_len)
                break

        return lines

    @contextmanager
    def extra_indent(self, indent: str) -> cabc.Iterator[None]:
        old_initial_indent = self.initial_indent
        old_subsequent_indent = self.subsequent_indent
        self.initial_indent += indent
        self.subsequent_indent += indent

        try:
            yield
        finally:
            self.initial_indent = old_initial_indent
            self.subsequent_indent = old_subsequent_indent

    def indent_only(self, text: str) -> str:
        rv = []

        for idx, line in enumerate(text.splitlines()):
            indent = self.initial_indent

            if idx > 0:
                indent = self.subsequent_indent

            rv.append(f"{indent}{line}")

        return "\n".join(rv)
