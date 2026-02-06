#!/usr/bin/env python3
"""Generate a monthly PNL-style calendar SVG showing daily Claude Code token usage."""

import json
import sys
import calendar
from datetime import datetime, timezone

COLORS = ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353"]
TEXT_DIM = "#484f58"
TEXT_MID = "#8b949e"
TEXT_BRIGHT = "#e6edf3"

CELL_W = 88
CELL_H = 52
GAP = 3
RX = 4
PAD = 16
HEADER_H = 44
WEEKDAY_H = 28
LEGEND_H = 36

MONO = "'SF Mono', 'Cascadia Code', 'Fira Code', Consolas, monospace"
SANS = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif"

WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
MONTH_NAMES = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]


def format_tokens(n):
    if n == 0:
        return ""
    if n < 1000:
        return str(n)
    if n < 100_000:
        return f"{n / 1000:.1f}k"
    if n < 1_000_000:
        return f"{n / 1000:.0f}k"
    return f"{n / 1_000_000:.1f}M"


def relative_time(iso_str):
    if not iso_str:
        return "unknown"
    try:
        then = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        diff = now - then
        minutes = int(diff.total_seconds() / 60)
        if minutes < 1:
            return "just now"
        if minutes < 60:
            return f"{minutes}m ago"
        hours = minutes // 60
        if hours < 24:
            return f"{hours}h ago"
        days = hours // 24
        return f"{days}d ago"
    except Exception:
        return "unknown"


def quartile_thresholds(values):
    if not values:
        return [0, 0, 0, 0]
    s = sorted(values)
    n = len(s)
    return [s[0], s[n // 4], s[n // 2], s[3 * n // 4]]


def color_for(value, thresholds):
    if value == 0:
        return COLORS[0]
    if value <= thresholds[1]:
        return COLORS[1]
    if value <= thresholds[2]:
        return COLORS[2]
    if value <= thresholds[3]:
        return COLORS[3]
    return COLORS[4]


def generate_svg(raw):
    daily_data = {d["date"]: d["tokens"]["total"] for d in raw.get("daily", [])}
    vibe = raw.get("vibe_score", {})
    last_synced = raw.get("last_synced", "")

    today = datetime.now(timezone.utc).date()
    year, month = today.year, today.month

    weeks = calendar.monthcalendar(year, month)
    num_weeks = len(weeks)

    non_zero = [v for v in daily_data.values() if v > 0]
    thresholds = quartile_thresholds(non_zero)

    grid_w = 7 * CELL_W + 6 * GAP
    grid_h = num_weeks * CELL_H + (num_weeks - 1) * GAP
    total_w = PAD + grid_w + PAD
    total_h = PAD + HEADER_H + WEEKDAY_H + grid_h + GAP + LEGEND_H + PAD

    parts = []
    parts.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{total_w}" height="{total_h}" '
        f'viewBox="0 0 {total_w} {total_h}">'
    )

    # --- header ---
    emoji = vibe.get("emoji", "")
    label = vibe.get("label", "")
    score = vibe.get("score", "")
    header_left = f"{emoji} {label}" + (f" \u2014 {score}/100" if score else "")
    header_right = f"{MONTH_NAMES[month - 1]} {year}"

    hy = PAD + 22
    parts.append(
        f'  <text x="{PAD}" y="{hy}" fill="{TEXT_BRIGHT}" '
        f'font-size="15" font-weight="600" font-family="{SANS}">'
        f"{header_left}</text>"
    )
    parts.append(
        f'  <text x="{total_w - PAD}" y="{hy}" text-anchor="end" '
        f'fill="{TEXT_MID}" font-size="13" font-family="{SANS}">'
        f"{header_right}</text>"
    )

    # --- weekday headers ---
    wy = PAD + HEADER_H + 16
    for i, name in enumerate(WEEKDAYS):
        x = PAD + i * (CELL_W + GAP) + CELL_W // 2
        parts.append(
            f'  <text x="{x}" y="{wy}" text-anchor="middle" '
            f'fill="{TEXT_MID}" font-size="11" font-family="{MONO}">'
            f"{name}</text>"
        )

    # --- calendar grid ---
    grid_top = PAD + HEADER_H + WEEKDAY_H
    for row_idx, week in enumerate(weeks):
        for col_idx, day in enumerate(week):
            x = PAD + col_idx * (CELL_W + GAP)
            y = grid_top + row_idx * (CELL_H + GAP)

            if day == 0:
                parts.append(
                    f'  <rect x="{x}" y="{y}" width="{CELL_W}" height="{CELL_H}" '
                    f'rx="{RX}" fill="{COLORS[0]}" opacity="0.3"/>'
                )
                continue

            key = f"{year}-{month:02d}-{day:02d}"
            tokens = daily_data.get(key, 0)
            color = color_for(tokens, thresholds)
            is_today = day == today.day and month == today.month and year == today.year

            parts.append(
                f'  <rect x="{x}" y="{y}" width="{CELL_W}" height="{CELL_H}" '
                f'rx="{RX}" fill="{color}"/>'
            )
            if is_today:
                parts.append(
                    f'  <rect x="{x}" y="{y}" width="{CELL_W}" height="{CELL_H}" '
                    f'rx="{RX}" fill="none" stroke="{TEXT_MID}" stroke-width="1.5"/>'
                )

            # day number — top-left
            day_color = TEXT_MID if tokens == 0 else TEXT_BRIGHT
            parts.append(
                f'  <text x="{x + 8}" y="{y + 16}" '
                f'fill="{day_color}" font-size="11" font-family="{MONO}">'
                f"{day}</text>"
            )

            # token count — centered
            if tokens > 0:
                parts.append(
                    f'  <text x="{x + CELL_W // 2}" y="{y + 38}" '
                    f'text-anchor="middle" fill="{TEXT_BRIGHT}" '
                    f'font-size="14" font-weight="700" font-family="{MONO}">'
                    f"{format_tokens(tokens)}</text>"
                )

    # --- legend ---
    ly = grid_top + grid_h + GAP + 22
    parts.append(
        f'  <text x="{PAD}" y="{ly}" fill="{TEXT_MID}" '
        f'font-size="11" font-family="{SANS}">Less</text>'
    )
    box_x = PAD + 30
    for i, c in enumerate(COLORS):
        bx = box_x + i * 15
        parts.append(
            f'  <rect x="{bx}" y="{ly - 10}" width="12" height="12" '
            f'rx="2" fill="{c}"/>'
        )
    more_x = box_x + len(COLORS) * 15 + 4
    parts.append(
        f'  <text x="{more_x}" y="{ly}" fill="{TEXT_MID}" '
        f'font-size="11" font-family="{SANS}">More</text>'
    )
    parts.append(
        f'  <text x="{total_w - PAD}" y="{ly}" text-anchor="end" '
        f'fill="{TEXT_DIM}" font-size="11" font-family="{SANS}">'
        f"synced {relative_time(last_synced)}</text>"
    )

    parts.append("</svg>")
    return "\n".join(parts)


def main():
    if len(sys.argv) < 2:
        raw = json.load(sys.stdin)
    else:
        with open(sys.argv[1]) as f:
            raw = json.load(f)

    svg = generate_svg(raw)

    if len(sys.argv) >= 3:
        with open(sys.argv[2], "w") as f:
            f.write(svg)
    else:
        print(svg)


if __name__ == "__main__":
    main()
