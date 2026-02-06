#!/usr/bin/env python3
"""Generate a GitHub-style contribution heatmap SVG from Claude Code usage stats."""

import json
import sys
from datetime import datetime, timedelta, timezone

# GitHub dark theme colors
COLORS = ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353"]
CELL_SIZE = 12
CELL_GAP = 2
CELL_STRIDE = CELL_SIZE + CELL_GAP
CORNER_RADIUS = 2

HEADER_HEIGHT = 36
MONTH_LABEL_HEIGHT = 20
DAY_LABEL_WIDTH = 32
LEGEND_HEIGHT = 30
PADDING = 16

FONT_FAMILY = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif"
LABEL_STYLE = f'fill="#8b949e" font-size="11" font-family="{FONT_FAMILY}"'
HEADER_STYLE = f'fill="#e6edf3" font-size="14" font-weight="600" font-family="{FONT_FAMILY}"'

MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
               "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
DAY_LABELS = {0: "Mon", 2: "Wed", 4: "Fri"}


def parse_data(raw):
    daily = {d["date"]: d["tokens"]["total"] for d in raw.get("daily", [])}
    vibe = raw.get("vibe_score", {})
    last_synced = raw.get("last_synced", "")
    return daily, vibe, last_synced


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
    daily, vibe, last_synced = parse_data(raw)

    if not daily:
        dates = []
    else:
        all_dates = sorted(daily.keys())
        start = datetime.strptime(all_dates[0], "%Y-%m-%d").date()
        end = datetime.strptime(all_dates[-1], "%Y-%m-%d").date()
        # Pad start to Monday (weekday 0)
        start -= timedelta(days=start.weekday())
        # Pad end to Sunday (weekday 6)
        end += timedelta(days=6 - end.weekday())
        dates = []
        d = start
        while d <= end:
            dates.append(d)
            d += timedelta(days=1)

    non_zero = [v for v in daily.values() if v > 0]
    thresholds = quartile_thresholds(non_zero)

    num_weeks = len(dates) // 7 if dates else 0
    grid_width = num_weeks * CELL_STRIDE
    total_width = PADDING + DAY_LABEL_WIDTH + grid_width + PADDING
    total_width = max(total_width, 300)
    grid_height = 7 * CELL_STRIDE
    total_height = PADDING + HEADER_HEIGHT + MONTH_LABEL_HEIGHT + grid_height + LEGEND_HEIGHT + PADDING

    grid_x = PADDING + DAY_LABEL_WIDTH
    grid_y = PADDING + HEADER_HEIGHT + MONTH_LABEL_HEIGHT

    parts = []
    parts.append(f'<svg xmlns="http://www.w3.org/2000/svg" '
                 f'width="{total_width}" height="{total_height}" '
                 f'viewBox="0 0 {total_width} {total_height}">')

    # Header: emoji + label + score
    emoji = vibe.get("emoji", "")
    label = vibe.get("label", "")
    score = vibe.get("score", "")
    header_text = f"{emoji} {label}" + (f" — {score}/100" if score else "")
    parts.append(f'  <text x="{PADDING}" y="{PADDING + 18}" {HEADER_STYLE}>'
                 f'{header_text}</text>')

    # Month labels
    if dates:
        month_y = PADDING + HEADER_HEIGHT + 12
        last_month = -1
        for week_idx in range(num_weeks):
            day = dates[week_idx * 7]
            if day.month != last_month:
                x = grid_x + week_idx * CELL_STRIDE
                parts.append(f'  <text x="{x}" y="{month_y}" {LABEL_STYLE}>'
                             f'{MONTH_NAMES[day.month - 1]}</text>')
                last_month = day.month

    # Day labels (Mon, Wed, Fri)
    for day_idx, name in DAY_LABELS.items():
        y = grid_y + day_idx * CELL_STRIDE + 10
        parts.append(f'  <text x="{PADDING}" y="{y}" {LABEL_STYLE}>{name}</text>')

    # Grid cells
    for i, date in enumerate(dates):
        week_idx = i // 7
        day_idx = i % 7
        key = date.strftime("%Y-%m-%d")
        value = daily.get(key, 0)
        color = color_for(value, thresholds)
        x = grid_x + week_idx * CELL_STRIDE
        y = grid_y + day_idx * CELL_STRIDE
        tooltip = f"{key}: {value:,} tokens" if value else f"{key}: No activity"
        parts.append(f'  <rect x="{x}" y="{y}" width="{CELL_SIZE}" height="{CELL_SIZE}" '
                     f'rx="{CORNER_RADIUS}" ry="{CORNER_RADIUS}" fill="{color}">'
                     f'<title>{tooltip}</title></rect>')

    # Legend
    legend_y = grid_y + grid_height + 14
    parts.append(f'  <text x="{grid_x}" y="{legend_y}" {LABEL_STYLE}>Less</text>')
    legend_box_x = grid_x + 30
    for idx, c in enumerate(COLORS):
        bx = legend_box_x + idx * (CELL_SIZE + 3)
        by = legend_y - 10
        parts.append(f'  <rect x="{bx}" y="{by}" width="{CELL_SIZE}" height="{CELL_SIZE}" '
                     f'rx="{CORNER_RADIUS}" ry="{CORNER_RADIUS}" fill="{c}"/>')
    more_x = legend_box_x + len(COLORS) * (CELL_SIZE + 3) + 4
    parts.append(f'  <text x="{more_x}" y="{legend_y}" {LABEL_STYLE}>More</text>')

    # Synced time (right-aligned)
    synced_text = f"synced {relative_time(last_synced)}"
    parts.append(f'  <text x="{total_width - PADDING}" y="{legend_y}" '
                 f'text-anchor="end" {LABEL_STYLE}>{synced_text}</text>')

    parts.append('</svg>')
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
