#!/usr/bin/env python3
"""
Simple tmux-based dispatcher to launch the Codex CLI, send a predefined prompt,
and periodically print the last lines from the tmux pane for monitoring.
"""

from __future__ import annotations

import re
import subprocess
import time
import uuid
from pathlib import Path
from typing import Iterable

# Edit this prompt to drive the Codex CLI. It is sent after Codex starts.
PREDEFINED_PROMPT = (
    #"Summarize the current working directory structure"
    "@agents/roles/executor.md work on the next `ready` task."
)

# How often to poll the tmux pane for output.
POLL_INTERVAL_SECONDS = 1
# How many stable polls indicate the timer has stopped updating.
STABLE_TIMER_POLLS = 5

# Simple ANSI colors for pane output.
ANSI_CYAN = "\033[36m"
ANSI_RESET = "\033[0m"
LOG_DIR = Path(__file__).resolve().parents[1] / "scratchpads"


def run_tmux(args: Iterable[str], check: bool = True) -> subprocess.CompletedProcess[str]:
    """Execute a tmux command with sane defaults."""
    return subprocess.run(
        ["tmux", *args],
        check=check,
        text=True,
        capture_output=True,
    )


def create_session(session_name: str) -> None:
    run_tmux(["new-session", "-d", "-s", session_name])


def send_keys(target: str, line: str) -> None:
    # Use C-m to simulate Enter.
    run_tmux(["send-keys", "-t", target, line, "C-m"])


def capture_last_lines(target: str, lines: int = 10) -> str:
    result = run_tmux(
        ["capture-pane", "-t", target, "-p", "-S", f"-{lines}"],
        check=True,
    )
    # Defensive clamp in Python in case tmux returns more than requested.
    return "\n".join(result.stdout.splitlines()[-lines:])


def capture_pane(target: str) -> str:
    result = run_tmux(
        ["capture-pane", "-t", target, "-p"],
        check=True,
    )
    return result.stdout


def find_last_timer_line(lines: list[str]) -> tuple[int | None, str | None]:
    for idx in range(len(lines) - 1, -1, -1):
        if "Worked for " in lines[idx]:
            return idx, lines[idx]
    return None, None


def find_prompt_line(lines: list[str], start_index: int) -> int | None:
    prompt_markers = (">", "\u203a")
    for idx in range(start_index + 1, len(lines)):
        stripped = lines[idx].lstrip()
        if stripped.startswith(prompt_markers):
            return idx
    return None


def find_context_left(lines: list[str]) -> tuple[int | None, str | None]:
    for idx in range(len(lines) - 1, -1, -1):
        if "context left" in lines[idx]:
            match = re.search(r"(\d+)%\s+context left", lines[idx])
            if match:
                return int(match.group(1)), lines[idx]
    return None, None


def extract_timer_value(timer_line: str | None) -> str | None:
    if not timer_line:
        return None
    match = re.search(r"Worked for ([^ ]+)", timer_line)
    if match:
        return match.group(1)
    return None


def kill_session(session_name: str) -> None:
    run_tmux(["kill-session", "-t", session_name], check=False)


def write_pane_log(target: str, session_name: str) -> Path:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    log_path = LOG_DIR / f"{session_name}_{timestamp}.log"
    log_path.write_text(capture_pane(target), encoding="utf-8")
    return log_path


def main() -> None:
    session_name = f"codex_task_{uuid.uuid4().hex[:8]}"
    target = f"{session_name}:0.0"
    stable_timer_polls = 0
    last_timer_line = None
    session_created = False

    print(f"Starting tmux session '{session_name}' and launching Codex...")
    try:
        create_session(session_name)
        session_created = True

        # Start Codex CLI in the pane.
        send_keys(target, "codex -s danger-full-access")
        time.sleep(1)  # Give Codex a moment to start.

        # Send the predefined prompt (supports multi-line strings).
        for line in PREDEFINED_PROMPT.splitlines():
            if line.strip() == "":
                send_keys(target, "")  # Preserve blank lines if present.
            else:
                send_keys(target, line)
        # Ensure the prompt is submitted (extra Enter after the last line).
        send_keys(target, "\n")

        print("Monitoring tmux pane output (last 10 lines). Press Ctrl+C to stop.")
        while True:
            pane_output = capture_pane(target)
            lines = pane_output.splitlines()
            output = "\n".join(lines[-10:])
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            print(f"\n[{timestamp}] ---- tmux pane tail ----")
            print(f"{ANSI_CYAN}{output.rstrip()}{ANSI_RESET}")
            timer_index, timer_line = find_last_timer_line(lines)
            timer_value = extract_timer_value(timer_line)
            context_percent, _ = find_context_left(lines)
            timer_display = timer_value if timer_value is not None else "unknown"
            context_display = (
                f"{context_percent}%" if context_percent is not None else "unknown"
            )
            print(
                f"Metrics: timer={timer_display} context_left={context_display}"
            )
            if timer_line is None:
                stable_timer_polls = 0
                last_timer_line = None
            else:
                if timer_line == last_timer_line:
                    stable_timer_polls += 1
                else:
                    last_timer_line = timer_line
                    stable_timer_polls = 1
                if stable_timer_polls >= STABLE_TIMER_POLLS:
                    prompt_index = find_prompt_line(lines, timer_index)
                    body_lines = lines[timer_index + 1 : prompt_index]
                    while body_lines and not body_lines[0].strip():
                        body_lines.pop(0)
                    while body_lines and not body_lines[-1].strip():
                        body_lines.pop()
                    final_answer = "\n".join(body_lines)
                    print("\nDetected stable timer; final answer from pane:")
                    print(final_answer)
                    break
            time.sleep(POLL_INTERVAL_SECONDS)

    except KeyboardInterrupt:
        print("\nInterrupted by user; shutting down tmux session.")
    except FileNotFoundError as exc:
        print(f"Required binary not found: {exc}. Ensure tmux and codex are installed.")
    except subprocess.CalledProcessError as exc:
        print(f"tmux command failed: {exc}\nstdout:\n{exc.stdout}\nstderr:\n{exc.stderr}")
    finally:
        if session_created:
            try:
                log_path = write_pane_log(target, session_name)
                print(f"Saved tmux pane log to {log_path}")
            except subprocess.CalledProcessError:
                print("Unable to capture tmux pane for logging.")
        kill_session(session_name)
        print(f"tmux session '{session_name}' terminated.")


if __name__ == "__main__":
    main()
