# -*- coding: utf-8 -*-
"""Convert root-relative clean URLs to path-relative ones for GH Pages project previews.

SEO absolute URLs stay on the production domain. Navigation becomes path-relative
so links resolve under /REPOSITORY-NAME/ on GitHub Pages project sites.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

NAV_ATTRS = "href|action|data-thank-you-path|data-next|formaction"


def to_path_relative(url: str) -> str:
    if not url.startswith("/") or url.startswith("//"):
        return url
    rest = url[1:]
    if rest == "" or rest.startswith("?") or rest.startswith("#"):
        if rest.startswith("#") or rest.startswith("?"):
            return "./" + rest
        return "./"
    return rest


def rewrite_nav_urls(text: str) -> str:
    def attr_sub(m: re.Match[str]) -> str:
        raw = m.group("url")
        if raw.startswith(("http://", "https://", "mailto:", "tel:", "#")):
            return m.group(0)
        if re.match(r"^/(?:css|js|assets|docs)/", raw):
            return m.group(0)
        if raw.startswith("/") and re.search(
            r"\.(?:css|js|png|jpe?g|webp|gif|svg|pdf|ico|woff2?|ttf|map)(?:$|\?)",
            raw,
            re.I,
        ):
            return m.group(0)
        return f'{m.group("attr")}={m.group("q")}{to_path_relative(raw)}{m.group("q")}'

    text = re.sub(
        rf"(?P<attr>{NAV_ATTRS})=(?P<q>[\"'])(?P<url>[^\"']+)(?P=q)",
        attr_sub,
        text,
        flags=re.I,
    )
    text = re.sub(
        r"url=/(?P<path>[^\s\"'>]+)",
        lambda m: f"url={to_path_relative('/' + m.group('path'))}",
        text,
        flags=re.I,
    )
    text = re.sub(
        rf"location\.replace\((?P<q>[\"'])/(?P<path>[^\"']*)(?P=q)\)",
        lambda m: f"location.replace({m.group('q')}{to_path_relative('/' + m.group('path'))}{m.group('q')})",
        text,
    )
    text = text.replace('"/thank-you"', '"thank-you"').replace("'/thank-you'", "'thank-you'")
    return text


def main() -> None:
    changed: list[str] = []
    targets = list(ROOT.glob("*.html")) + list((ROOT / "_snippets").glob("*.html"))
    targets.append(ROOT / "js" / "main.js")
    for path in targets:
        if not path.exists():
            continue
        original = path.read_text(encoding="utf-8")
        updated = rewrite_nav_urls(original)
        if updated != original:
            path.write_text(updated, encoding="utf-8", newline="\n")
            changed.append(str(path.relative_to(ROOT)))
    print(f"updated {len(changed)} files")
    for f in changed:
        print(f"  {f}")


if __name__ == "__main__":
    main()
