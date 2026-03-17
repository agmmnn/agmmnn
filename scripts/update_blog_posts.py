#!/usr/bin/env python3
"""Update README blog post markers from an RSS feed."""

from __future__ import annotations

import argparse
import html
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET

MARKER_START = "<!-- BLOG-POST-LIST:START -->"
MARKER_END = "<!-- BLOG-POST-LIST:END -->"


def fetch_feed(url: str) -> bytes:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "agmmnn-readme-updater/1.0",
            "Accept": "application/rss+xml, application/xml, text/xml;q=0.9, */*;q=0.8",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()


def parse_posts(feed_bytes: bytes, limit: int) -> list[tuple[str, str]]:
    root = ET.fromstring(feed_bytes)
    channel = root.find("./channel")
    if channel is None:
        return []

    posts: list[tuple[str, str]] = []
    for item in channel.findall("./item"):
        title = item.findtext("title")
        link = item.findtext("link")
        if not title or not link:
            continue
        posts.append((html.unescape(title.strip()), link.strip()))
        if len(posts) >= limit:
            break
    return posts


def render_posts(posts: list[tuple[str, str]]) -> str:
    return "\n".join(f"- [{title}]({link})" for title, link in posts)


def replace_in_file(path: str, rendered_posts: str) -> bool:
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    pattern = re.compile(
        re.escape(MARKER_START) + r".*?" + re.escape(MARKER_END),
        re.DOTALL,
    )
    if not pattern.search(content):
        print(f"No blog markers found in {path}; skipping update.")
        return False

    replacement = f"{MARKER_START}\n{rendered_posts}\n{MARKER_END}"
    new_content = pattern.sub(replacement, content, count=1)

    if new_content == content:
        return False

    with open(path, "w", encoding="utf-8") as f:
        f.write(new_content)
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Update README blog post list from RSS.")
    parser.add_argument("--feed", required=True, help="RSS or Atom feed URL")
    parser.add_argument("--file", required=True, help="Markdown file to update")
    parser.add_argument("--max-posts", type=int, default=3, help="Number of posts to include")
    args = parser.parse_args()

    try:
        feed_bytes = fetch_feed(args.feed)
        posts = parse_posts(feed_bytes, args.max_posts)
        rendered_posts = render_posts(posts)
        replace_in_file(args.file, rendered_posts)
    except Exception as exc:  # pragma: no cover - workflow script
        print(f"Failed to update blog posts: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
