#!/usr/bin/env python3

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROFILES = (
    "larrabeedylan_work_darwin",
    "larrabeedylan_work_linux",
    "larrabeedylan_home_darwin",
)
TEMPLATE = "profiles/%s/.claude/skills/changes-diagram/assets/template.html"

RULES = """
changes-diagram's template.html, the page every published diagram is rendered from:

  the three profile copies            byte-identical — nothing else checks this file
  <meta name="viewport">              width=device-width, or a phone lays the page out
                                      at ~980px and shrinks the whole thing
  <script id="view-math">             present exactly once
  the view-math block                 touches no document, window or ELK, so it is
                                      testable with nothing stubbed
  word-break: break-all               gone — it breaks identifiers mid-token
  addEventListener("resize", fit)     gone — a hidden URL bar must not reset the view
  touch-action: none on .canvas       still set, and the page handles the pinch itself
  ViewMath.pinch / pointercancel      wired, since touch-action: none switches the
                                      browser's own pinch off

the view-math block, driven under node:

  fitAll                              contains the graph, at the viewport's aspect
  legible on a wide graph on a phone  stops at the readability floor, not below it
  legible anchors                     at the start of the flow, not the middle
  legible on a graph that fits        identical to fitAll
  rescale                             holds pixels-per-unit and the centre point
  rescale                             adopts the new viewport's aspect
  pinch, fingers 2x apart             halves the view width
  pinch                               holds the point under the fingers
  pinch, fingers moved together       pans by the gesture, with no zoom
  pinch, zero finger distance         returns the view untouched
  zoomAt                              scales, and holds its anchor
  clampZoom                           bounds how far out, and keeps the aspect
  clampZoom on an ordinary view       returns it untouched
  a zero-sized viewport               never yields a non-finite view
"""

DRIVER = r"""
const VM = require(process.argv[2]);
const out = [];
const ok = (label, cond, detail) => out.push({ label, ok: !!cond, detail: detail === undefined ? "" : String(detail) });
const near = (a, b) => Math.abs(a - b) <= 1e-6 * Math.max(1, Math.abs(a), Math.abs(b));

const phone = { left: 0, top: 0, width: 360, height: 520 };
const desk = { left: 0, top: 0, width: 1200, height: 800 };
const wide = { x: 0, y: 0, w: 9000, h: 1800 };
const small = { x: 0, y: 0, w: 300, h: 200 };
const FLOOR = 8 / 12.5;

{
  const v = VM.fitAll(wide, phone.width / phone.height);
  ok("fitAll contains the whole graph",
     v.x <= wide.x && v.y <= wide.y && v.x + v.w >= wide.x + wide.w && v.y + v.h >= wide.y + wide.h,
     JSON.stringify(v));
  ok("fitAll matches the viewport aspect", near(v.w / v.h, phone.width / phone.height), v.w / v.h);
}

{
  const v = VM.legible(wide, phone, FLOOR);
  const scale = phone.width / v.w;
  ok("legible never scales below the readability floor", scale >= FLOOR - 1e-9, "scale " + scale);
  ok("legible stops at the floor rather than past it", near(scale, FLOOR), "scale " + scale);
  const fitted = VM.fitAll(wide, phone.width / phone.height);
  ok("legible is closer in than fit-all on a wide graph", v.w < fitted.w, v.w + " vs " + fitted.w);
  ok("legible anchors at the start of the flow",
     v.x <= wide.x && v.y <= wide.y && v.x > wide.x - 100 && v.y > wide.y - 100, JSON.stringify(v));
}

{
  const v = VM.legible(small, desk, FLOOR);
  const fitted = VM.fitAll(small, desk.width / desk.height);
  ok("legible leaves a graph that already fits alone",
     near(v.x, fitted.x) && near(v.y, fitted.y) && near(v.w, fitted.w) && near(v.h, fitted.h),
     JSON.stringify(v) + " vs " + JSON.stringify(fitted));
}

{
  const v = { x: 100, y: 50, w: 600, h: 400 };
  const r = VM.rescale(v, { width: 1200, height: 800 }, { width: 360, height: 520 });
  ok("rescale holds pixels per unit", near(1200 / v.w, 360 / r.w), (1200 / v.w) + " vs " + (360 / r.w));
  ok("rescale holds the centre point",
     near(v.x + v.w / 2, r.x + r.w / 2) && near(v.y + v.h / 2, r.y + r.h / 2), JSON.stringify(r));
  ok("rescale adopts the new viewport aspect", near(r.w / r.h, 360 / 520), r.w / r.h);
}

{
  const v = { x: 0, y: 0, w: 1000, h: 1000 };
  const rect = { left: 0, top: 0, width: 500, height: 500 };
  const from = { ax: 200, ay: 250, bx: 300, by: 250 };
  const to = { ax: 150, ay: 250, bx: 350, by: 250 };
  const anchor = VM.toSvg(v, rect, 250, 250);
  const n = VM.pinch(v, rect, from, to);
  const after = VM.toSvg(n, rect, 250, 250);
  ok("fingers twice as far apart halve the view width", near(n.w, v.w / 2), n.w);
  ok("a pinch holds the point under the fingers", near(after.x, anchor.x) && near(after.y, anchor.y),
     JSON.stringify(after) + " vs " + JSON.stringify(anchor));
}

{
  const v = { x: 0, y: 0, w: 1000, h: 1000 };
  const rect = { left: 0, top: 0, width: 500, height: 500 };
  const from = { ax: 200, ay: 250, bx: 300, by: 250 };
  const to = { ax: 250, ay: 250, bx: 350, by: 250 };
  const n = VM.pinch(v, rect, from, to);
  ok("two fingers moved together pan without zooming", near(n.w, v.w) && near(n.h, v.h), n.w);
  ok("two fingers moved together pan by the gesture", near(n.x, v.x - 100), n.x);
}

{
  const v = { x: 0, y: 0, w: 100, h: 100 };
  const rect = { left: 0, top: 0, width: 500, height: 500 };
  const still = { ax: 10, ay: 10, bx: 10, by: 10 };
  ok("a zero-distance pinch returns the view untouched", VM.pinch(v, rect, still, still) === v);
}

{
  const v = { x: 0, y: 0, w: 1000, h: 1000 };
  const n = VM.zoomAt(v, 0.5, 400, 600);
  ok("zoomAt scales the view by its factor", near(n.w, 500), n.w);
  ok("zoomAt holds its anchor", near((400 - n.x) / n.w, (400 - v.x) / v.w), n.x);
}

{
  const bounds = { x: 0, y: 0, w: 1000, h: 400 };
  const far = VM.clampZoom({ x: 0, y: 0, w: 1e9, h: 4e8 }, bounds);
  ok("clampZoom bounds how far out the view goes", far.w <= 1000 * 8 + 1e-6, far.w);
  ok("clampZoom keeps the aspect it was given", near(far.w / far.h, 1e9 / 4e8), far.w / far.h);
  const ordinary = { x: 10, y: 10, w: 500, h: 200 };
  ok("clampZoom returns an ordinary view untouched", VM.clampZoom(ordinary, bounds) === ordinary);
}

{
  const tall = { left: 0, top: 0, width: 770, height: 778 };
  const squat = { x: 0, y: 0, w: 4788, h: 596 };
  const h = VM.contentHeight(squat, tall, FLOOR, 24);
  ok("contentHeight trims a canvas a short graph cannot fill", h < tall.height, h);
  ok("contentHeight leaves room for the graph at the chosen scale",
     h >= squat.h * FLOOR + 24 - 1, h + " vs " + (squat.h * FLOOR + 24));
  const square = { x: 0, y: 0, w: 700, h: 3000 };
  ok("contentHeight does not trim a canvas a tall graph fills",
     VM.contentHeight(square, tall, FLOOR, 24) >= tall.height,
     VM.contentHeight(square, tall, FLOOR, 24));
}

{
  const flat = { left: 0, top: 0, width: 0, height: 0 };
  const v = { x: 0, y: 0, w: 100, h: 100 };
  ok("legible survives a zero-sized viewport",
     Number.isFinite(VM.legible({ x: 0, y: 0, w: 10, h: 10 }, flat, FLOOR).w));
  ok("rescale survives a zero-sized viewport",
     Number.isFinite(VM.rescale(v, { width: 0, height: 0 }, { width: 360, height: 520 }).w));
  ok("toSvg survives a zero-sized viewport", Number.isFinite(VM.toSvg(v, flat, 5, 5).x));
}

process.stdout.write(JSON.stringify(out));
"""


class Suite:
    def __init__(self):
        self.failures = 0
        self.checked = 0

    def ok(self, label, condition, detail=""):
        self.checked += 1
        if not condition:
            self.failures += 1
            print("  fail — %s" % label)
            if detail:
                print("      %s" % detail.strip().replace("\n", "\n      "))


def read(profile):
    return open(os.path.join(REPO, TEMPLATE % profile), "rb").read()


def view_math(page):
    found = re.findall(r'<script id="view-math">(.*?)</script>', page, re.S)
    return found


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "rules":
        print(RULES.strip())
        return 0

    suite = Suite()
    reference = read(PROFILES[0])
    for profile in PROFILES[1:]:
        suite.ok("%s is byte-identical to %s" % (profile, PROFILES[0]),
                 read(profile) == reference, "sizes %d and %d" % (len(read(profile)), len(reference)))

    page = reference.decode()
    blocks = view_math(page)
    suite.ok("the view-math block is present exactly once", len(blocks) == 1, "found %d" % len(blocks))
    if len(blocks) != 1:
        print("check-diagram-template: %d of %d checks failed" % (suite.failures, suite.checked))
        return 1

    block = blocks[0]
    for forbidden in ("document", "window", "ELK", "getElementById"):
        suite.ok("the view-math block touches no %s" % forbidden, forbidden not in block)

    suite.ok("the page declares the device-width viewport",
             re.search(r'<meta name="viewport"[^>]*width=device-width', page) is not None)
    suite.ok("word-break: break-all is gone", "word-break: break-all" not in page)
    suite.ok("resize is not wired straight to fit", 'addEventListener("resize", fit)' not in page)
    suite.ok("the canvas still owns its touches", "touch-action: none" in page)
    suite.ok("the page runs the pinch itself", "ViewMath.pinch" in page)
    suite.ok("the page handles a cancelled gesture", "pointercancel" in page)

    work = tempfile.mkdtemp()
    try:
        module = os.path.join(work, "view-math.js")
        driver = os.path.join(work, "driver.js")
        with open(module, "w") as handle:
            handle.write(block + "\nmodule.exports = ViewMath;\n")
        with open(driver, "w") as handle:
            handle.write(DRIVER)
        finished = subprocess.run([shutil.which("node") or "node", driver, module],
                                  capture_output=True, text=True)
        suite.ok("the view-math block runs under node", finished.returncode == 0,
                 finished.stderr or finished.stdout)
        if finished.returncode == 0:
            for case in json.loads(finished.stdout):
                suite.ok(case["label"], case["ok"], case["detail"])
    finally:
        shutil.rmtree(work, ignore_errors=True)

    if suite.failures:
        print("check-diagram-template: %d of %d checks failed" % (suite.failures, suite.checked))
        return 1
    print("check-diagram-template: %d checks passed" % suite.checked)
    return 0


if __name__ == "__main__":
    sys.exit(main())
