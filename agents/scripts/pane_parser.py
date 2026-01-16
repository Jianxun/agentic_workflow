"""Utilities for parsing Codex tmux pane output."""

from __future__ import annotations

import re
from typing import Iterable

TIMER_PATTERN = re.compile(
    r"\((?P<time>(?:\d+m )?\d+s) \u2022 esc to interrupt\)"
)


def find_last_timer_line(lines: Iterable[str]) -> tuple[int | None, str | None]:
    """Return the last index and line that report the active timer."""
    line_list = list(lines)
    for idx in range(len(line_list) - 1, -1, -1):
        if TIMER_PATTERN.search(line_list[idx]):
            return idx, line_list[idx]
    return None, None


def find_prompt_line(lines: Iterable[str], start_index: int) -> int | None:
    """Find the first prompt line after a given index."""
    prompt_markers = (">", "\u203a")
    line_list = list(lines)
    for idx in range(start_index + 1, len(line_list)):
        stripped = line_list[idx].lstrip()
        if stripped.startswith(prompt_markers):
            return idx
    return None


def find_context_left(lines: Iterable[str]) -> tuple[int | None, str | None]:
    """Return the last reported context percent remaining."""
    line_list = list(lines)
    for idx in range(len(line_list) - 1, -1, -1):
        if "context left" in line_list[idx]:
            match = re.search(r"(\d+)%\s+context left", line_list[idx])
            if match:
                return int(match.group(1)), line_list[idx]
    return None, None


def extract_timer_value(timer_line: str | None) -> str | None:
    """Extract the timer duration token from a timer line."""
    if not timer_line:
        return None
    match = TIMER_PATTERN.search(timer_line)
    if match:
        return match.group("time")
    return None


def find_last_worked_for_line(lines: Iterable[str]) -> int | None:
    """Return the last index containing a Worked for summary line."""
    line_list = list(lines)
    for idx in range(len(line_list) - 1, -1, -1):
        if "Worked for " in line_list[idx]:
            return idx
    return None


def extract_body_lines(
    lines: Iterable[str],
    start_index: int | None,
    prompt_index: int | None,
    include_start_line: bool = False,
) -> list[str]:
    """Extract the final answer body between the timer and prompt lines."""
    if start_index is None:
        return []
    line_list = list(lines)
    end_index = prompt_index if prompt_index is not None else len(line_list)
    slice_start = start_index if include_start_line else start_index + 1
    body_lines = list(line_list[slice_start:end_index])
    while body_lines and not body_lines[0].strip():
        body_lines.pop(0)
    while body_lines and not body_lines[-1].strip():
        body_lines.pop()
    return body_lines
