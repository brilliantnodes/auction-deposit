#!/usr/bin/env python3
"""Render every record page in a real browser at the moments the live script
reads it, and check that the text matches tools/make_record.py text_lines.

    python tools/check_pages.py <tag> <D_unix> <out_dir> [--bradbury]

Run tools/make_record.py with the same arguments first. Needs Playwright with
Chromium (pip install playwright && playwright install chromium). The page
clock is set by replacing Date.now, so no waiting is needed.
"""
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent))
import make_record as mr  # noqa: E402


def main():
    tag, d, out = sys.argv[1], int(sys.argv[2]), Path(sys.argv[3])
    net = "bradbury" if "--bradbury" in sys.argv[4:] else "studio"
    tm = mr.CASES["timing"][net]
    moments = [-10, tm["result"] - 1, tm["result"] + 1] + tm["reads"] + [tm["change"] - 1, tm["change"] + 1, tm["settle"]]
    bad, n = [], 0
    with sync_playwright() as p:
        b = p.chromium.launch()
        for case in mr.CASES["cases"]:
            path = (out / mr.page_path(tag, case)).resolve()
            for m in moments:
                t = d + 60 * m
                ctx = b.new_context()
                ctx.add_init_script(f"Date.now = function () {{ return {t * 1000}; }};")
                pg = ctx.new_page()
                pg.goto("file://" + str(path))
                got = [ln.strip() for ln in pg.evaluate("document.body.innerText").splitlines() if ln.strip()]
                want = mr.text_lines(case, d, net, t)
                n += 1
                if got != want:
                    bad.append((case["key"], m, got, want))
                ctx.close()
        b.close()
    for key, m, got, want in bad:
        print(f"MISMATCH {key} at D{m:+d} min\n  got:  {got}\n  want: {want}")
    print(f"{n - len(bad)} of {n} renders match")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
