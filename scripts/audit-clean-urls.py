# -*- coding: utf-8 -*-
"""Audit clean-URL + base-path regressions."""
from __future__ import annotations

import argparse
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def detect_site(cli_site: str | None) -> str:
    if cli_site:
        return cli_site.rstrip("/")
    env = os.environ.get("CLEAN_URL_SITE", "").strip().rstrip("/")
    if env:
        return env
    cname = ROOT / "CNAME"
    if cname.exists():
        host = cname.read_text(encoding="utf-8").strip().splitlines()[0].strip()
        if host:
            return "https://" + host.lstrip("/")
    return ""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site", help="Expected production origin")
    args = parser.parse_args()
    site = detect_site(args.site)
    host = site.replace("https://", "").replace("http://", "") if site else ""

    pages = [p.stem for p in ROOT.glob("*.html")]
    stem_alt = "|".join(re.escape(s) for s in sorted(pages, key=len, reverse=True))
    page_html = re.compile(rf"(?:{stem_alt})\.html", re.I) if stem_alt else re.compile(r"$^")
    root_nav = re.compile(
        r"""(?:href|action|data-thank-you-path|formaction)=["'](/[^"']*)["']""",
        re.I,
    )

    files = list(ROOT.glob("*.html")) + list((ROOT / "_snippets").glob("*.html"))
    files += [
        ROOT / "sitemap.xml",
        ROOT / "llms.txt",
        ROOT / "robots.txt",
        ROOT / "js" / "main.js",
    ]

    print("=== page .html still exposed in URLs? ===")
    found = False
    for f in files:
        if not f.exists():
            continue
        text = f.read_text(encoding="utf-8")
        for i, line in enumerate(text.splitlines(), 1):
            if not page_html.search(line):
                continue
            if "Prefer clean URLs" in line or r"\.html$" in line or "replace(/\\.html" in line:
                continue
            if "pathname" in line and "html" in line:
                continue
            if line.strip().startswith("<!--") or "PAGE:" in line:
                continue
            print(f"{f.relative_to(ROOT)}:{i}: {line.strip()[:160]}")
            found = True
    if not found:
        print("none")

    print("=== root-relative nav links (break GH project previews)? ===")
    found = False
    for f in list(ROOT.glob("*.html")) + list((ROOT / "_snippets").glob("*.html")) + [ROOT / "js" / "main.js"]:
        if not f.exists():
            continue
        text = f.read_text(encoding="utf-8")
        for i, line in enumerate(text.splitlines(), 1):
            for m in root_nav.finditer(line):
                url = m.group(1)
                if re.match(r"^/(?:css|js|assets|docs)/", url):
                    continue
                if re.search(r"\.(?:css|js|png|jpe?g|webp|svg|pdf|ico)(?:$|\?)", url, re.I):
                    continue
                print(f"{f.relative_to(ROOT)}:{i}: {url}")
                found = True
    if not found:
        print("none")

    print("=== SEO host check ===")
    seo_files = [ROOT / "sitemap.xml", ROOT / "llms.txt", ROOT / "index.html"]
    for f in seo_files:
        if not f.exists():
            continue
        text = f.read_text(encoding="utf-8")
        if "github.io" in text:
            print(f"FAIL {f.name} contains github.io")
        elif host and host in text:
            print(f"ok {f.name} uses {host}")
        elif host:
            print(f"WARN {f.name} missing expected host {host}")
        else:
            print(f"ok {f.name} (no github.io); pass --site to verify host")


if __name__ == "__main__":
    main()
