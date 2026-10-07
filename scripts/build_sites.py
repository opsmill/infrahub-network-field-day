"""Build the static OTTERNET sites for local preview.

Each directory under ``sites/`` (except ``_shared`` and ``_build``) is one nginx
application. This copies the shared stylesheet next to every site, writes the
speed test's download file, and adds an index page that links the sites, all
into ``sites/_build``. Serve it with:

    uv run python scripts/build_sites.py && python3 -m http.server 8088 --directory sites/_build
"""

from __future__ import annotations

import html
import re
import shutil
from pathlib import Path

SITES = Path(__file__).resolve().parent.parent / "sites"
BUILD = SITES / "_build"
TEST_FILE_MEGABYTES = 20


def site_names() -> list[str]:
    return sorted(p.name for p in SITES.iterdir() if p.is_dir() and not p.name.startswith("_"))


def title_of(index: Path) -> str:
    match = re.search(r"<title>(.*?)</title>", index.read_text(encoding="utf-8"), re.DOTALL)
    return html.unescape(match.group(1)).strip() if match else index.parent.name


def build() -> list[str]:
    if BUILD.exists():
        shutil.rmtree(BUILD)
    BUILD.mkdir()
    css = SITES / "_shared" / "otternet.css"
    names = site_names()
    for name in names:
        shutil.copytree(SITES / name, BUILD / name)
        shutil.copy(css, BUILD / name / "otternet.css")
    (BUILD / "speedtest" / "testfile.bin").write_bytes(b"\0" * TEST_FILE_MEGABYTES * 1024 * 1024)
    shutil.copy(css, BUILD / "otternet.css")
    items = "\n".join(
        f'      <div class="card"><h3><a href="{n}/index.html">{html.escape(title_of(SITES / n / "index.html"))}</a></h3>'
        f"<p><code>{n}/</code></p></div>"
        for n in names
    )
    (BUILD / "index.html").write_text(
        f"""<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>OTTERNET sites</title><link rel="stylesheet" href="otternet.css"></head>
<body>
  <header><h1>OTTERNET sites</h1><p>Local preview of every static site. Each one is a separate application when deployed.</p></header>
  <main>
    <div class="grid">
{items}
    </div>
  </main>
</body>
</html>
""",
        encoding="utf-8",
    )
    return names


if __name__ == "__main__":
    print("built:", ", ".join(build()), "->", BUILD)
