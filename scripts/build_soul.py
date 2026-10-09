#!/usr/bin/env python3
"""Build img/soul.svg (desktop) and img/soul-mobile.svg (phones): a terminal that types and
deletes one line of soul.md at a time.

Pure SVG + SMIL, so it renders inside GitHub's <img> sandbox. Every line runs on one shared
clock, so there is no begin-event chaining to drift. No clipPath: WebKit (Safari, every iOS
browser) ignores an animated clip and draws all lines at once. Instead only the active line is
shown, and a background-coloured cover per row slides right with the cursor to reveal it.
textLength pins each row to an exact monospace width, so the cover and the cursor stay aligned
whatever font the viewer has.
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

# name, width, height, font size, side padding, first row y, row height, gap to comment
VARIANTS = [
    ("soul.svg", 800, 148, 15, 26, 84, 24, 27),
    ("soul-mobile.svg", 380, 152, 14, 18, 72, 23, 26),
]

PROMPT = "~ % "
TYPE_DT, DEL_DT = 0.055, 0.022  # seconds per character
HOLD, GAP, LEAD = 2.6, 0.5, 0.8
ROW_PAUSE = 0.12                # cursor dwell at a wrap

BG, BORDER, RULE = "#000000", "#222222", "#141414"
INK, FAINT = "#ededed", "#4a4a4a"
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


def wrap(text, cols):
    """One row if it fits. Else two: at the comma nearest the middle if both halves fit,
    otherwise at the most balanced space."""
    if len(text) <= cols:
        return [text]
    cuts = [i for i, ch in enumerate(text) if ch == " "]
    fits = [i for i in cuts if i <= cols and len(text) - i - 1 <= cols]
    assert fits, f"cannot fit in two rows of {cols}: {text}"
    commas = [i for i in fits if text[i - 1] in ",;"]
    best = min(commas or fits, key=lambda i: abs(i - len(text) / 2))
    return [text[:best], text[best + 1:]]


def discrete(events, total):
    """events: [(seconds, value)] -> SMIL values/keyTimes strings on one shared clock."""
    events = sorted(events, key=lambda e: e[0])
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


def animate(attr, events, total, dur, transform=False):
    vals, keys = discrete(events, total)
    if transform:
        return (f'<animateTransform attributeName="transform" type="translate" values="{vals}" '
                f'keyTimes="{keys}" dur="{dur}" calcMode="discrete" repeatCount="indefinite"/>')
    return (f'<animate attributeName="{attr}" values="{vals}" keyTimes="{keys}" dur="{dur}" '
            f'calcMode="discrete" repeatCount="indefinite"/>')


def build(name, W, H, FONT, PAD, Y0, LH, CG, font_uri):
    CW = FONT * 0.6                 # monospace advance
    X0 = PAD + len(PROMPT) * CW     # where typed text starts
    cols = int((W - PAD - X0) // CW)
    off = W                         # cover translate that clears a row completely

    # One plan per quote: its rows, and the cursor (row, col) at every keystroke.
    t, plan = LEAD, []
    for text, src in LINES:
        rows = wrap(text, cols)
        steps, now = [], t
        for r, row in enumerate(rows):
            if r:
                now += ROW_PAUSE
                steps.append((now, r, 0))
            for c in range(1, len(row) + 1):
                now += TYPE_DT
                steps.append((now, r, c))
        typed = now
        delete = typed + HOLD
        now = delete
        for r in reversed(range(len(rows))):
            for c in reversed(range(len(rows[r]))):
                now += DEL_DT
                steps.append((now, r, c))
            if r:
                now += ROW_PAUSE
                steps.append((now, r - 1, len(rows[r - 1])))
        plan.append((rows, src, t, typed, delete, now, steps))
        t = now + GAP
    total = t
    dur = f"{total:.2f}s"
    nrows = max(len(p[0]) for p in plan)

    # Cursor and covers; the static (no-SMIL) frame shows the first quote fully typed.
    first_rows = plan[0][0]
    cursor = [(0.0, "0 0")]
    covers = {r: [(0.0, "0 0")] for r in range(nrows)}
    for rows, _src, start, _t, _d, end, steps in plan:
        for sec, r, c in steps:
            cursor.append((sec, f"{c * CW:.1f} {r * LH}"))
            covers[r].append((sec, f"{c * CW:.1f} 0"))
            for done in range(r):
                covers[done].append((sec, f"{off} 0"))
            for ahead in range(r + 1, nrows):
                # rows this quote never reaches move away, or they would hide its comment
                covers[ahead].append((sec, "0 0" if ahead < len(rows) else f"{off} 0"))

    body = []
    for i, (rows, src, start, typed, delete, end, _steps) in enumerate(plan):
        show = [(0.0, 0), (start, 1), (end, 0)]
        base = 1 if i == 0 else 0
        g = [f'<g opacity="{base}">{animate("opacity", show, total, dur)}']
        for r, row in enumerate(rows):
            g.append(f'<text x="{X0:.1f}" y="{Y0 + r * LH}" textLength="{len(row) * CW:.1f}" '
                     f'lengthAdjust="spacingAndGlyphs" fill="{INK}">{escape(row)}</text>')
        g.append("</g>")
        body.append("".join(g))
        if src:
            note = f"# {src}"
            y = Y0 + (len(rows) - 1) * LH + CG
            fade = [(0.0, 0), (typed + 0.25, 1), (delete - 0.15, 0)]
            body.append(f'<text x="{X0:.1f}" y="{y}" textLength="{len(note) * 0.6 * (FONT - 2):.1f}" '
                        f'lengthAdjust="spacingAndGlyphs" fill="{FAINT}" style="font-size:{FONT - 2}px" '
                        f'opacity="{base}">{escape(note)}{animate("opacity", fade, total, dur)}</text>')

    # a nested <svg> viewport stops the covers at the frame; a static box, not an animated clip
    body.append(f'<svg x="1" y="37" width="{W - 2}" height="{H - 38}" viewBox="1 37 {W - 2} {H - 38}" overflow="hidden">')
    for r in range(nrows):
        rest = f"{off} 0"
        body.append(f'<rect x="{X0:.1f}" y="{Y0 + r * LH - FONT - 2}" width="{W - X0:.1f}" '
                    f'height="{FONT + 8}" fill="{BG}" transform="translate({rest})">'
                    f'{animate(None, covers[r], total, dur, transform=True)}</rect>')

    body.append("</svg>")

    last = first_rows[-1]
    rest = f"{len(last) * CW:.1f} {(len(first_rows) - 1) * LH}"
    body.append(f'<g transform="translate({rest})">{animate(None, cursor, total, dur, transform=True)}'
                f'<rect class="cur" x="{X0 + 1:.1f}" y="{Y0 - 13}" width="1.6" height="17" fill="{INK}"/></g>')

    titles = "; ".join(t for t, _ in LINES)
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" '
        f'aria-labelledby="t"><title id="t">esegal/soul.md: {escape(titles)}</title>'
        f'<style>@font-face{{font-family:GM;src:url({font_uri}) format("woff")}}'
        f'text{{font-family:{MONO};font-size:{FONT}px;letter-spacing:0}}'
        f'.cur{{animation:blink 1.05s step-end infinite}}@keyframes blink{{50%{{opacity:0}}}}</style>'
        f'<rect x="0.5" y="0.5" width="{W - 1}" height="{H - 1}" rx="12" fill="{BG}"/>'
        f'<line x1="1" y1="36" x2="{W - 1}" y2="36" stroke="{RULE}"/>'
        f'<circle cx="22" cy="18.5" r="5" fill="{RED}"/><circle cx="40" cy="18.5" r="5" fill="{AMBER}"/>'
        f'<circle cx="58" cy="18.5" r="5" fill="{GREEN}"/>'
        f'<text x="{W / 2}" y="22.5" text-anchor="middle" fill="{FAINT}" style="font-size:11.5px">{escape(TITLE)}</text>'
        f'<text x="{PAD}" y="{Y0}" fill="{BLUE}">~</text>'
        f'<text x="{PAD + 2 * CW:.1f}" y="{Y0}" fill="{GREEN}">%</text>'
        f'{"".join(body)}'
        f'<rect x="0.5" y="0.5" width="{W - 1}" height="{H - 1}" rx="12" fill="none" stroke="{BORDER}"/></svg>\n'
    )
    out = ROOT / "img" / name
    out.write_text(svg)
    print(f"wrote {out} ({len(svg) / 1024:.1f} KB, {cols} cols, {nrows} rows, cycle {total:.1f}s)")


if __name__ == "__main__":
    uri = embedded_font()
    for v in VARIANTS:
        build(*v, uri)
