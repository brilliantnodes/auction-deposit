"""Render scenes to stills (--stills name:t,...) or to one mp4 per scene by piping JPEGs to ffmpeg.

    python3 render.py stills s1:5 s2:6 ...
    python3 render.py video [s1 s2 ...]
"""
import subprocess, sys, os
from pathlib import Path
from playwright.sync_api import sync_playwright

D = Path(__file__).parent
SC = D / "scenes2"  
DUR = dict(l.split() for l in (SC / "durations.txt").read_text().splitlines())
SET = "t => { document.getAnimations().forEach(a => { a.pause(); a.currentTime = t; }); if (window.tick) window.tick(t); }"
FPS = 30


def page(b, name):
    pg = b.new_page(viewport={"width": 1920, "height": 1080})
    pg.goto("file://" + str(SC / f"{name}.html"))
    pg.wait_for_timeout(400)
    return pg


with sync_playwright() as p:
    b = p.chromium.launch()
    if sys.argv[1] == "stills":
        (D / "stills2").mkdir(exist_ok=True)
        for spec in sys.argv[2:]:
            name, ts = spec.split(":")
            pg = page(b, name)
            for t in ts.split(","):
                pg.evaluate(SET, float(t) * 1000)
                pg.screenshot(path=str(D / "stills2" / f"{name}-{t}.jpg"), type="jpeg", quality=92)
            pg.close()
    else:
        (D / "parts2").mkdir(exist_ok=True)
        for name in (sys.argv[2:] or list(DUR)):
            dur = float(DUR[name])
            pg = page(b, name)
            tmp = D / "parts2" / f"{name}.tmp.mp4"
            ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "image2pipe", "-framerate", str(FPS), "-c:v", "mjpeg", "-i", "-",
                                   "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p", "-r", str(FPS), str(tmp)], stdin=subprocess.PIPE)
            for i in range(int(round(dur * FPS))):
                pg.evaluate(SET, i * 1000 / FPS)
                ff.stdin.write(pg.screenshot(type="jpeg", quality=92))
            ff.stdin.close()
            if ff.wait() == 0:
                os.replace(tmp, D / "parts2" / f"{name}.mp4")
                print(name, "ok", flush=True)
            pg.close()
    b.close()
