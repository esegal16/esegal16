#!/usr/bin/env python3
"""Build img/soul.svg: a terminal that types and deletes one line of soul.md at a time.

Pure SVG + SMIL, so it renders inside GitHub's <img> sandbox. Every line runs on one shared
clock, so there is no begin-event chaining to drift. textLength pins each line to an exact
monospace width, so the clip and the cursor stay aligned whatever font the viewer has.
Run: python3 scripts/build_soul.py
"""
import base64
import io
from pathlib import Path
from xml.sax.saxutils import escape

from fontTools import subset
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parent.parent

LINES = [
    ("We shape our buildings, and then our buildings shape us.", "churchill"),
    ("Say little and do much.", "shammai, pirkei avot 1:15"),
    ("Take a simple idea and take it very seriously.", "munger"),
    ("Ответ нет у вас уже есть.", "you already have the no"),
    ("What you do is who you are.", "ben horowitz"),
    ("Man plans, God laughs.", "yiddish proverb"),
    ("Bad ideas can hide in complexity, but they can't hide in simplicity.", None),
    ("If not now, when?", "hillel, pirkei avot 1:14"),
    ("I don't know who discovered water, but it wasn't a fish.", "mcluhan"),
    ("Invert, always invert.", "munger"),
    ("Everything is foreseen, yet freedom of choice is given.", "rabbi akiva, pirkei avot 3:15"),
]

W, H = 800, 148
FONT = 15
CW = FONT * 0.6                 # monospace advance
PAD = 26
PROMPT = "~ % "
X0 = PAD + len(PROMPT) * CW     # where typed text starts
Y1, Y2 = 84, 111                # sentence line, comment line

TYPE_DT, DEL_DT = 0.055, 0.022  # seconds per character
HOLD, GAP, LEAD = 2.6, 0.5, 0.8

BG, BORDER, RULE = "#000000", "#222222", "#141414"
INK, DIM, FAINT = "#ededed", "#6b6b6b", "#4a4a4a"
RED, AMBER, GREEN, BLUE = "#ff5f57", "#febc2e", "#28c840", "#5eb4ff"
TITLE = "esegal/soul.md — zsh"
MONO = "'GM','Geist Mono','SF Mono',ui-monospace,Menlo,Consolas,monospace"


def embedded_font():
    """Geist Mono (OFL, fonts/OFL.txt), cut down to the glyphs this file uses, as a data URI."""
    used = "".join(t + (s or "") for t, s in LINES) + PROMPT + TITLE + "# "
    font = TTFont(ROOT / "fonts" / "GeistMono-Regular.ttf")
    opts = subset.Options()
    opts.flavor = "woff"
    opts.layout_features = []
    sub = subset.Subsetter(opts)
    sub.populate(text=used)
    sub.subset(font)
    buf = io.BytesIO()
    font.flavor = "woff"
    font.save(buf)
    return "data:font/woff;base64," + base64.b64encode(buf.getvalue()).decode()


def timeline():
    t, plan = LEAD, []
    for text, src in LINES:
        n = len(text)
        typed = t + n * TYPE_DT
        delete = typed + HOLD
        end = delete + n * DEL_DT
        plan.append((text, src, t, typed, delete, end))
        t = end + GAP
    return plan, t


def discrete(events, total):
    """events: [(seconds, value)] -> SMIL values/keyTimes strings on one shared clock."""
    events = sorted(events)
    keys, vals, last = [], [], -1.0
    for sec, v in events:
        k = round(sec / total, 5)
        if k <= last:
            k = round(last + 0.00001, 5)
        keys.append(k)
        vals.append(v)
        last = k
    assert keys[0] == 0 and keys[-1] < 1
    return ";".join(map(str, vals)), ";".join(f"{k:.5f}" for k in keys)


def build():
    plan, total = timeline()
    dur = f"{total:.2f}s"
    defs, body = [], []
    cursor = [(0.0, "0 0")]

    for i, (text, src, start, typed, delete, end) in enumerate(plan):
        n = len(text)
        ev = [(0.0, 0)]
        ev += [(start + k * TYPE_DT, round(k * CW, 1)) for k in range(1, n + 1)]
        ev += [(delete + k * DEL_DT, round((n - k) * CW, 1)) for k in range(1, n + 1)]
        vals, keys = discrete(ev, total)
        defs.append(f'<clipPath id="c{i}"><rect x="{X0}" y="{Y1 - 20}" height="28" width="0">'
                    f'<animate attributeName="width" values="{vals}" keyTimes="{keys}" dur="{dur}" '
                    f'calcMode="discrete" repeatCount="indefinite"/></rect></clipPath>')
        body.append(f'<text x="{X0}" y="{Y1}" textLength="{n * CW:.1f}" lengthAdjust="spacingAndGlyphs" '
                    f'fill="{INK}" clip-path="url(#c{i})">{escape(text)}</text>')
        cursor += [(start + k * TYPE_DT, f"{k * CW:.1f} 0") for k in range(1, n + 1)]
        cursor += [(delete + k * DEL_DT, f"{(n - k) * CW:.1f} 0") for k in range(1, n + 1)]
        if src:
            note = f"# {src}"
            vals, keys = discrete([(0.0, 0), (typed + 0.25, 1), (delete - 0.15, 0)], total)
            body.append(f'<text x="{X0}" y="{Y2}" textLength="{len(note) * 0.6 * (FONT - 2):.1f}" '
                        f'lengthAdjust="spacingAndGlyphs" fill="{FAINT}" style="font-size:{FONT - 2}px" '
                        f'opacity="0">{escape(note)}'
                        f'<animate attributeName="opacity" values="{vals}" keyTimes="{keys}" dur="{dur}" '
                        f'calcMode="discrete" repeatCount="indefinite"/></text>')

    vals, keys = discrete(cursor, total)
    body.append(f'<g><animateTransform attributeName="transform" type="translate" values="{vals}" keyTimes="{keys}" '
                f'dur="{dur}" calcMode="discrete" repeatCount="indefinite"/>'
                f'<rect class="cur" x="{X0 + 1:.1f}" y="{Y1 - 13}" width="1.6" height="17" fill="{INK}"/></g>')

    titles = "; ".join(t for t, _ in LINES)
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" '
        f'aria-labelledby="t"><title id="t">esegal/soul.md: {escape(titles)}</title>'
        f'<style>@font-face{{font-family:GM;src:url({embedded_font()}) format("woff")}}'
        f'text{{font-family:{MONO};font-size:{FONT}px;letter-spacing:0}}'
        f'.cur{{animation:blink 1.05s step-end infinite}}@keyframes blink{{50%{{opacity:0}}}}</style>'
        f'<defs>{"".join(defs)}</defs>'
        f'<rect x="0.5" y="0.5" width="{W - 1}" height="{H - 1}" rx="12" fill="{BG}" stroke="{BORDER}"/>'
        f'<line x1="1" y1="36" x2="{W - 1}" y2="36" stroke="{RULE}"/>'
        f'<circle cx="22" cy="18.5" r="5" fill="{RED}"/><circle cx="40" cy="18.5" r="5" fill="{AMBER}"/>'
        f'<circle cx="58" cy="18.5" r="5" fill="{GREEN}"/>'
        f'<text x="{W / 2}" y="22.5" text-anchor="middle" fill="{FAINT}" style="font-size:11.5px">{escape(TITLE)}</text>'
        f'<text x="{PAD}" y="{Y1}" fill="{BLUE}">~</text>'
        f'<text x="{PAD + 2 * CW:.1f}" y="{Y1}" fill="{GREEN}">%</text>'
        f'{"".join(body)}</svg>\n'
    )
    out = ROOT / "img" / "soul.svg"
    out.write_text(svg)
    print(f"wrote {out} ({len(svg) / 1024:.1f} KB, cycle {total:.1f}s)")


if __name__ == "__main__":
    build()
