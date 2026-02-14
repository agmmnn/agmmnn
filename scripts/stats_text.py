#!/usr/bin/env python3
"""Generate a plain text stats summary for GitHub profile READMEs."""

import json
import re
import sys
from datetime import datetime, timezone

MARKER_START = "<!-- VIBE_METER_START -->"
MARKER_END = "<!-- VIBE_METER_END -->"


def format_tokens(n):
    if n == 0:
        return "0"
    if n < 1000:
        return str(n)
    if n < 100_000:
        return f"{n / 1000:.1f}k"
    if n < 1_000_000:
        return f"{n / 1000:.0f}k"
    return f"{n / 1_000_000:.1f}M"


def shorten_model(name):
    name = name.replace("claude-", "")
    parts = name.split("-")
    if len(parts) >= 3 and parts[-1].isdigit() and parts[-2].isdigit():
        return f"{'-'.join(parts[:-2])} {parts[-2]}.{parts[-1]}"
    return name


def peak_phrase(hour):
    if 0 <= hour < 6:
        return "Night Owl"
    elif 6 <= hour < 9:
        return "Early Bird"
    elif 9 <= hour < 12:
        return "Morning Coder"
    elif 12 <= hour < 14:
        return "Lunch Hacker"
    elif 14 <= hour < 18:
        return "Afternoon Grinder"
    elif 18 <= hour < 21:
        return "Evening Warrior"
    else:
        return "Night Coder"


def generate_text(raw):
    daily = raw.get("daily", [])
    hourly = raw.get("history", {}).get("hourly_activity", {})

    total_tokens = sum(d["tokens"]["total"] for d in daily)
    active_days = sum(1 for d in daily if d["tokens"]["total"] > 0)
    total_sessions = sum(d.get("sessions", 0) for d in daily)
    total_prompts = sum(d.get("prompts", 0) for d in daily)

    # Top model
    model_tokens = {}
    for d in daily:
        for model, toks in (d.get("models") or {}).items():
            model_tokens[model] = model_tokens.get(model, 0) + toks
    top_models = sorted(model_tokens.items(), key=lambda x: -x[1])
    top_model = shorten_model(top_models[0][0]) if top_models else "Claude"
    num_models = len(top_models)

    # Peak hour
    hour_values = {int(k): int(v) for k, v in hourly.items()}
    peak_h = max(hour_values, key=hour_values.get) if hour_values else 0

    return (
        f"I burned {format_tokens(total_tokens)} tokens across {active_days} active days, "
        f"mass using {top_model}"
        f"{f' and {num_models - 1} other model' + ('s' if num_models > 2 else '') if num_models > 1 else ''}, "
        f"sent {format_tokens(total_prompts)} prompts in {total_sessions} sessions, "
        f"peaking at {peak_h:02d}:00 as an {peak_phrase(peak_h)}."
    )


def replace_in_file(path, text):
    """Replace content between VIBE_METER markers in a file."""
    content = open(path).read()
    pattern = re.compile(
        re.escape(MARKER_START) + r".*?" + re.escape(MARKER_END),
        re.DOTALL,
    )
    replacement = f"{MARKER_START}\n{text}\n{MARKER_END}"
    new_content, count = pattern.subn(replacement, content)
    if count == 0:
        print(f"No {MARKER_START} ... {MARKER_END} markers found in {path}", file=sys.stderr)
        sys.exit(1)
    with open(path, "w") as f:
        f.write(new_content)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Generate Claude Code plain text stats")
    parser.add_argument("input", nargs="?", help="JSON input file (default: stdin)")
    parser.add_argument("output", nargs="?", help="Output text file (default: stdout)")
    parser.add_argument("--replace", metavar="FILE",
                        help="Replace text between <!-- VIBE_METER_START/END --> markers in FILE")
    parser.add_argument("--logo", metavar="URL",
                        help="Prepend an <img> logo before the text (e.g. ./assets/logo.svg)")
    args = parser.parse_args()

    if args.input:
        with open(args.input) as f:
            raw = json.load(f)
    else:
        raw = json.load(sys.stdin)

    text = generate_text(raw)

    if args.logo:
        text = f'<img src="{args.logo}" height="14"> {text}'

    if args.replace:
        replace_in_file(args.replace, text)
    elif args.output:
        with open(args.output, "w") as f:
            f.write(text)
    else:
        print(text)


if __name__ == "__main__":
    main()
