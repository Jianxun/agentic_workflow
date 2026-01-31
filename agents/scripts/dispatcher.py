#!/usr/bin/env python3
"""
Simple tmux-based dispatcher to launch the Codex CLI, send a predefined prompt,
and periodically print the last lines from the tmux pane for monitoring.
"""

from __future__ import annotations

import subprocess
import time
import uuid
from pathlib import Path
from typing import Iterable

try:
    from agents.scripts import pane_parser
except ModuleNotFoundError:
    import pane_parser

# Edit this prompt to drive the Codex CLI. It is sent after Codex starts.
PREDEFINED_PROMPT = (
    #"Summarize the current working directory structure"
    #"@agents/roles/executor.md work on task T-003."
    "@agents/roles/reviewer.md review task T-003. there are local changes on the task branch from the user, include them in the PR."
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
        ["capture-pane", "-t", target, "-p", "-S", "-"],
        check=True,
    )
    return result.stdout


def kill_session(session_name: str) -> None:
    run_tmux(["kill-session", "-t", session_name], check=False)


def write_pane_log(target: str, session_name: str) -> Path:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    log_path = LOG_DIR / f"{session_name}_{timestamp}.log"
    log_path.write_text(capture_pane(target), encoding="utf-8")
    return log_path


def render_final_answer(lines: list[str], timer_index: int | None) -> str:
    worked_for_index = pane_parser.find_last_worked_for_line(lines)
    if worked_for_index is not None:
        start_index = worked_for_index
        include_start_line = True
    elif timer_index is not None:
        start_index = timer_index
        include_start_line = False
    else:
        return "\n".join(lines).rstrip()
    prompt_index = pane_parser.find_prompt_line(lines, start_index)
    body_lines = pane_parser.extract_body_lines(
        lines,
        start_index,
        prompt_index,
        include_start_line=include_start_line,
    )
    return "\n".join(body_lines)


def main() -> None:
    session_name = f"codex_task_{uuid.uuid4().hex[:8]}"
    target = f"{session_name}:0.0"
    stable_timer_polls = 0
    last_timer_value = None
    unknown_timer_polls = 0
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
            timer_index, timer_line = pane_parser.find_last_timer_line(lines)
            timer_value = pane_parser.extract_timer_value(timer_line)
            context_percent, _ = pane_parser.find_context_left(lines)
            timer_display = timer_value if timer_value is not None else "unknown"
            context_display = (
                f"{context_percent}%" if context_percent is not None else "unknown"
            )
            print(
                f"Metrics: timer={timer_display} context_left={context_display}"
            )
            if timer_value is None:
                unknown_timer_polls += 1
                stable_timer_polls = 0
                last_timer_value = None
                if unknown_timer_polls >= STABLE_TIMER_POLLS:
                    final_answer = render_final_answer(lines, timer_index)
                    print("\nDetected missing timer; final answer from pane:")
                    print(final_answer)
                    break
            else:
                unknown_timer_polls = 0
                if timer_value == last_timer_value:
                    stable_timer_polls += 1
                else:
                    last_timer_value = timer_value
                    stable_timer_polls = 1
                if stable_timer_polls >= STABLE_TIMER_POLLS:
                    final_answer = render_final_answer(lines, timer_index)
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
