#!/usr/bin/env python3
"""Small, dependency-free local channel for turn-based AI agents."""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import re
import sys
import tempfile
import time
from pathlib import Path
from typing import Iterator, List, Optional, Tuple


DEFAULT_ROOT = Path("/tmp/claude-channels")
NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$")


def channel_root() -> Path:
    root = Path(os.environ.get("RESEARCH_ROUNDTABLE_DIR", str(DEFAULT_ROOT))).expanduser()
    root.mkdir(parents=True, exist_ok=True)
    return root


def safe_name(value: str, label: str) -> str:
    if not NAME_RE.fullmatch(value):
        raise SystemExit(
            f"invalid {label} {value!r}; use 1-80 letters, digits, dots, underscores, or hyphens"
        )
    return value


def paths(channel: str, agent: str) -> Tuple[Path, Path]:
    channel = safe_name(channel, "channel")
    agent = safe_name(agent, "agent")
    root = channel_root()
    return root / f"{channel}.ndjson", root / f"{channel}.{agent}.cursor"


@contextlib.contextmanager
def exclusive_lock(path: Path) -> Iterator[None]:
    """Best-effort cross-platform one-byte advisory lock."""
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = path.open("a+")
    try:
        if os.name == "nt":
            import msvcrt

            handle.seek(0)
            if handle.tell() == 0:
                handle.write("0")
                handle.flush()
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        yield
    finally:
        try:
            if os.name == "nt":
                import msvcrt

                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        finally:
            handle.close()


def ensure_transcript(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch(exist_ok=True)


def read_lines(path: Path) -> List[str]:
    ensure_transcript(path)
    with exclusive_lock(path.with_suffix(path.suffix + ".lock")):
        return [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def read_cursor(path: Path) -> int:
    try:
        return max(0, int(path.read_text(encoding="utf-8").strip()))
    except (FileNotFoundError, ValueError):
        return 0


def write_cursor(path: Path, value: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=path.name + ".", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(f"{max(0, value)}\n")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def parse(raw: str) -> Optional[dict]:
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(value, dict):
        return None
    if not isinstance(value.get("from"), str) or not isinstance(value.get("text"), str):
        return None
    return value


def format_message(value: dict) -> str:
    return f"[{value['from']}] {value['text']}"


def append_message(transcript: Path, agent: str, text: str) -> None:
    text = text.strip()
    if not text:
        raise SystemExit("refusing to send an empty message")
    record = {
        "from": safe_name(agent, "agent"),
        "ts": int(time.time()),
        "text": text,
    }
    ensure_transcript(transcript)
    lock = transcript.with_suffix(transcript.suffix + ".lock")
    with exclusive_lock(lock):
        with transcript.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
            handle.flush()
            os.fsync(handle.fileno())


def collect(channel: str, agent: str) -> List[dict]:
    transcript, cursor = paths(channel, agent)
    cursor_lock = cursor.with_suffix(cursor.suffix + ".lock")
    with exclusive_lock(cursor_lock):
        lines = read_lines(transcript)
        start = min(read_cursor(cursor), len(lines))
        messages = []
        for raw in lines[start:]:
            value = parse(raw)
            if value and value["from"] != agent:
                messages.append(value)
        write_cursor(cursor, len(lines))
        return messages


def receive(channel: str, agent: str, timeout: Optional[float], interval: float) -> List[dict]:
    deadline = None if timeout is None else time.monotonic() + max(0.0, timeout)
    while True:
        messages = collect(channel, agent)
        if messages:
            return messages
        if deadline is not None and time.monotonic() >= deadline:
            return []
        time.sleep(max(0.05, interval))


def cmd_setup(args: argparse.Namespace) -> int:
    transcript, cursor = paths(args.channel, args.agent)
    lines = read_lines(transcript)
    write_cursor(cursor, len(lines))
    print(f"channel={args.channel} agent={args.agent} transcript={transcript} cursor={cursor}")
    return 0


def cmd_send(args: argparse.Namespace) -> int:
    transcript, _ = paths(args.channel, args.agent)
    body = list(args.text or [])
    stdin_mode = bool(args.stdin) or body == ["--stdin"] or body == ["-"]
    if stdin_mode:
        text = sys.stdin.read()
    else:
        text = " ".join(body)
    append_message(transcript, args.agent, text)
    print(f"sent: {text.strip()[:160]}")
    return 0


def cmd_history(args: argparse.Namespace) -> int:
    transcript, _ = paths(args.channel, args.agent)
    for raw in read_lines(transcript):
        value = parse(raw)
        if value:
            print(format_message(value))
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    transcript, cursor = paths(args.channel, args.agent)
    lines = read_lines(transcript)
    position = min(read_cursor(cursor), len(lines))
    print(
        json.dumps(
            {
                "channel": args.channel,
                "agent": args.agent,
                "transcript": str(transcript),
                "lines": len(lines),
                "cursor": position,
                "pending_lines": len(lines) - position,
            },
            indent=2,
        )
    )
    return 0


def print_messages(messages: List[dict]) -> None:
    for value in messages:
        print(format_message(value), flush=True)


def cmd_poll(args: argparse.Namespace) -> int:
    print_messages(receive(args.channel, args.agent, args.timeout, args.interval))
    return 0


def cmd_wait(args: argparse.Namespace) -> int:
    print_messages(receive(args.channel, args.agent, None, args.interval))
    return 0


def cmd_stream(args: argparse.Namespace) -> int:
    try:
        while True:
            print_messages(receive(args.channel, args.agent, None, args.interval))
    except KeyboardInterrupt:
        return 0


def cmd_leave(args: argparse.Namespace) -> int:
    transcript, _ = paths(args.channel, args.agent)
    append_message(transcript, args.agent, "left the channel")
    print(f"left: channel={args.channel} agent={args.agent}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Local named channel for AI research agents")
    sub = parser.add_subparsers(dest="command", required=True)

    for name, function in (("setup", cmd_setup), ("history", cmd_history), ("status", cmd_status), ("leave", cmd_leave)):
        command = sub.add_parser(name)
        command.add_argument("channel")
        command.add_argument("agent")
        command.set_defaults(function=function)

    send = sub.add_parser("send")
    send.add_argument("channel")
    send.add_argument("agent")
    send.add_argument("--stdin", action="store_true")
    send.add_argument("text", nargs=argparse.REMAINDER)
    send.set_defaults(function=cmd_send)

    for name, function, default_timeout in (
        ("poll", cmd_poll, 0.0),
        ("listen", cmd_poll, 30.0),
    ):
        command = sub.add_parser(name)
        command.add_argument("channel")
        command.add_argument("agent")
        command.add_argument("--timeout", type=float, default=default_timeout)
        command.add_argument("--interval", type=float, default=0.25)
        command.set_defaults(function=function)

    wait = sub.add_parser("wait")
    wait.add_argument("channel")
    wait.add_argument("agent")
    wait.add_argument("--interval", type=float, default=0.25)
    wait.set_defaults(function=cmd_wait)

    stream = sub.add_parser("stream")
    stream.add_argument("channel")
    stream.add_argument("agent")
    stream.add_argument("--interval", type=float, default=0.25)
    stream.set_defaults(function=cmd_stream)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return int(args.function(args))


if __name__ == "__main__":
    raise SystemExit(main())
