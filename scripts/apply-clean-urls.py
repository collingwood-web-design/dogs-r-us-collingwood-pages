# -*- coding: utf-8 -*-
"""Convert public URLs and internal links to clean (extensionless) form.

Keeps on-disk *.html filenames for GitHub Pages. Rewrites user-facing and SEO
URLs only. Filesystem paths in Python (open/read of *.html) are left alone.

Set production origin via:
  python apply-clean-urls.py --site https://clientdomain.com
or env CLEAN_URL_SITE, or a root CNAME file (https:// + contents).
"""
from __future__ import annotations

import argparse
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

CLIENT_REDIRECT = """    <script>
      /* Prefer clean URLs when someone lands on the .html form. */
      (function () {
        var path = window.location.pathname;
        if (!/\\.html$/i.test(path)) return;
        var clean = path.replace(/\\.html$/i, "");
        if (/\\/index$/i.test(clean)) clean = clean.replace(/\\/index$/i, "/") || "/";
        if (clean === "") clean = "/";
        window.location.replace(clean + window.location.search + window.location.hash);
      })();
    </script>
"""


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
    raise SystemExit(
        "Set production site: --site https://clientdomain.com  (or CLEAN_URL_SITE / CNAME)"
    )


def is_redirect_stub(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    return (
        "http-equiv=\"refresh\"" in text.lower()
        and "location.replace" in text
        and len(text) < 2500
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site", help="Production origin, e.g. https://example.com")
    args = parser.parse_args()
    site = detect_site(args.site)

    page_stems = sorted(p.stem for p in ROOT.glob("*.html"))
    page_stems_desc = sorted(page_stems, key=len, reverse=True)
    stem_alt = "|".join(re.escape(s) for s in page_stems_desc)

    def clean_path(stem: str, fragment: str = "", query: str = "") -> str:
        if stem == "index":
            path = "./"
            if query:
                path = f"./?{query}"
            if fragment:
                path = f"{path}#{fragment}" if query else f"./#{fragment}"
            return path
        path = stem
        if query:
            path += f"?{query}"
        if fragment:
            path += f"#{fragment}"
        return path

    def clean_abs(stem: str, fragment: str = "", query: str = "") -> str:
        base = f"{site}/" if stem == "index" else f"{site}/{stem}"
        if query:
            base += f"?{query}"
        if fragment:
            base += f"#{fragment}"
        return base

    # Any https host already used with page.html (covers domain typos / old hosts)
    host_scan = re.compile(
        rf"https?://([^/\"'\s]+)/(?:{stem_alt})\.html",
        re.I,
    )

    def rewrite_text(text: str, *, urls_only: bool) -> str:
        hosts = {site}
        for m in host_scan.finditer(text):
            hosts.add("https://" + m.group(1))

        for host in sorted(hosts, key=len, reverse=True):
            text = re.sub(
                rf"{re.escape(host)}/(?P<stem>{stem_alt})\.html"
                rf"(?:\?(?P<query>[^\"'\s#>]*))?(?:#(?P<frag>[^\"'\s]*))?",
                lambda m: clean_abs(m.group("stem"), m.group("frag") or "", m.group("query") or ""),
                text,
            )

        text = re.sub(
            rf"(?P<prefix>['\"=\(\s]|^)/(?P<stem>{stem_alt})\.html"
            rf"(?:\?(?P<query>[^\"'\s#>]*))?(?:#(?P<frag>[^\"'\s]*))?",
            lambda m: f"{m.group('prefix')}{clean_path(m.group('stem'), m.group('frag') or '', m.group('query') or '')}",
            text,
            flags=re.M,
        )

        attr_alt = "href|content|action|data-thank-you-path|data-next|formaction"
        text = re.sub(
            rf"(?P<attr>{attr_alt})=(?P<q>[\"'])(?P<stem>{stem_alt})\.html"
            rf"(?:\?(?P<query>[^\"'#]*))?(?:#(?P<frag>[^\"']*))?(?P=q)",
            lambda m: (
                f'{m.group("attr")}={m.group("q")}'
                f'{clean_path(m.group("stem"), m.group("frag") or "", m.group("query") or "")}'
                f'{m.group("q")}'
            ),
            text,
            flags=re.I,
        )

        text = re.sub(
            rf"url=(?P<stem>{stem_alt})\.html(?:#(?P<frag>[^\"'\s>]*))?",
            lambda m: f"url={clean_path(m.group('stem'), m.group('frag') or '')}",
            text,
            flags=re.I,
        )
        text = re.sub(
            rf"location\.replace\((?P<q>[\"'])(?P<stem>{stem_alt})\.html"
            rf"(?:#(?P<frag>[^\"']*))?(?P=q)\)",
            lambda m: (
                f"location.replace({m.group('q')}"
                f"{clean_path(m.group('stem'), m.group('frag') or '')}"
                f"{m.group('q')})"
            ),
            text,
        )

        text = text.replace('"thank-you.html"', '"thank-you"')
        text = text.replace("'thank-you.html'", "'thank-you'")

        if not urls_only:
            text = re.sub(
                rf"(?P<q>[\"'])(?P<stem>{stem_alt})\.html"
                rf"(?:\?(?P<query>[^\"'#]*))?(?:#(?P<frag>[^\"']*))?(?P=q)",
                lambda m: (
                    f'{m.group("q")}'
                    f'{clean_path(m.group("stem"), m.group("frag") or "", m.group("query") or "")}'
                    f'{m.group("q")}'
                ),
                text,
            )
        return text

    def inject_client_redirect(text: str) -> str:
        if "Prefer clean URLs when someone lands" in text:
            return text
        return re.sub(r"(<head[^>]*>)", r"\1\n" + CLIENT_REDIRECT, text, count=1, flags=re.I)

    changed: list[str] = []
    print(f"SITE={site}")

    for path in list(ROOT.glob("*.html")) + list((ROOT / "_snippets").glob("*.html")):
        original = path.read_text(encoding="utf-8")
        updated = rewrite_text(original, urls_only=False)
        if path.parent.name != "_snippets" and not is_redirect_stub(path):
            updated = inject_client_redirect(updated)
        if updated != original:
            path.write_text(updated, encoding="utf-8", newline="\n")
            changed.append(str(path.relative_to(ROOT)))

    for rel in ("sitemap.xml", "robots.txt", "llms.txt", "js/main.js"):
        path = ROOT / rel
        if not path.exists():
            continue
        original = path.read_text(encoding="utf-8")
        updated = rewrite_text(original, urls_only=False)
        if updated != original:
            path.write_text(updated, encoding="utf-8", newline="\n")
            changed.append(rel)

    scripts_dir = ROOT / "scripts"
    if scripts_dir.exists():
        for path in scripts_dir.glob("*.py"):
            if path.name in {"apply-clean-urls.py", "apply-basepath-links.py", "audit-clean-urls.py", "preview-server.py"}:
                continue
            original = path.read_text(encoding="utf-8")
            updated = rewrite_text(original, urls_only=True)
            if updated != original:
                path.write_text(updated, encoding="utf-8", newline="\n")
                changed.append(str(path.relative_to(ROOT)))

    print(f"updated {len(changed)} files")
    for f in changed:
        print(f"  {f}")


if __name__ == "__main__":
    main()
