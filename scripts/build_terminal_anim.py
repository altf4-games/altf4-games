"""
One animated terminal for the top of the README (animated WebP):

  1. `neofetch` types itself and prints the card (ASCII logo + info rows)
  2. `doom` is typed, the window splits: Doom demo on the left, and
     `cat wins` / `cat work` / `git log` typed out in a new pane on the right

Everything is laid out in 900x452 "logical" pixels and rendered at SCALE x
for a sharper image. Doom frames come from a raw recording (record_doom.sh)
or, for local previews, from an existing animated WebP.

  python scripts/build_terminal_anim.py doom_raw.mp4 terminal.webp [--data data.json]
"""

import argparse
import json
import os
import subprocess
from html.parser import HTMLParser

from PIL import Image, ImageDraw, ImageFont

from profile_data import ROOT, USERNAME, load_profile, oss_data

SCALE = 1.5
FPS = 12
W = 900
TITLE_H = 32
BODY_H = 420
H = TITLE_H + BODY_H
STATUS_H = 24
GAME_W, GAME_H = 576, 360
PANE_X = GAME_W + 1                  # right pane starts after the divider
PANE_W = W - PANE_X
PANE_LH = 17                         # line height in the right pane
DOOM_SECONDS = 16                    # how long the split-screen part runs
TYPE_SECONDS = 10                    # how long the right pane takes to type itself
QUALITY = 40

BG = (13, 17, 23)
CHROME = (22, 27, 34)
STROKE = (48, 54, 61)
DIM = (139, 148, 158)
FAINT = (72, 79, 88)
TEXT = (230, 237, 243)
GREEN = (126, 231, 135)
BLUE = (56, 189, 248)
GOLD = (227, 179, 65)
PURPLE = (163, 113, 247)
DOOM_RED = (230, 40, 40)
BLOCKS = [(48, 54, 61), (255, 123, 114), (126, 231, 135), (227, 179, 65),
          (56, 189, 248), (163, 113, 247), (86, 212, 221), (201, 209, 217)]

FONTS = [
    ("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
     "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"),
    ("/System/Library/Fonts/Menlo.ttc", "/System/Library/Fonts/Menlo.ttc"),
]

_fonts = {}


def font(size, bold=False):
    """Monospace font at `size` logical px (rendered SCALE x bigger)."""
    key = (size, bold)
    if key not in _fonts:
        for regular, heavy in FONTS:
            path = heavy if bold else regular
            if os.path.exists(path):
                idx = 1 if (bold and path.endswith(".ttc")) else 0
                _fonts[key] = ImageFont.truetype(path, round(size * SCALE), index=idx)
                break
        else:
            raise SystemExit("no monospace font found")
    return _fonts[key]


def clip(s, n):
    return s if len(s) <= n else s[: n - 1].rstrip() + "…"


def length(f, text):
    """Width of `text` in logical px."""
    return f.getlength(text) / SCALE


class Canvas:
    """ImageDraw that takes logical coordinates."""

    def __init__(self):
        self.img = Image.new("RGB", (round(W * SCALE), round(H * SCALE)), BG)
        self.d = ImageDraw.Draw(self.img)

    @staticmethod
    def _s(v):
        return [round(x * SCALE) for x in v]

    def text(self, xy, s, f, fill, anchor=None):
        self.d.text(self._s(xy), s, font=f, fill=fill, anchor=anchor)

    def rect(self, box, fill):
        self.d.rectangle(self._s(box), fill=fill)

    def rrect(self, box, radius, fill, outline=None):
        self.d.rounded_rectangle(self._s(box), radius=round(radius * SCALE), fill=fill, outline=outline)

    def ellipse(self, box, fill):
        self.d.ellipse(self._s(box), fill=fill)

    def line(self, pts, fill):
        self.d.line(self._s([c for p in pts for c in p]), fill=fill, width=max(1, round(SCALE)))

    def paste(self, im, xy):
        self.img.paste(im, tuple(self._s(xy)))


# ---------------------------------------------------------------------------
# Content
# ---------------------------------------------------------------------------

def pane_lines(data, width_chars):
    """Right-pane script: list of lines, each a list of (text, colour)."""
    prompt = f"{data['user']}@{data['host']}:~$ "
    lines = [[(prompt, GREEN), ("cat wins", TEXT)]]
    for a in data["achievements"][:3]:
        lines.append([(" ★ ", GOLD), (clip(a["title"], width_chars - 3), TEXT)])
        lines.append([("   ", TEXT), (clip(a["event"], width_chars - 3), DIM)])
    lines.append([(prompt, GREEN), ("cat work", TEXT)])
    for e in data["experience"][:3]:
        lines.append([(" ▸ ", PURPLE), (clip(e["role"], width_chars - 3), TEXT)])
        lines.append([("   ", TEXT), (clip(f"{e['org'].split(' (')[0]} · {e['when']}", width_chars - 3), DIM)])
    if data["prs"]:
        lines.append([(prompt, GREEN), ("git log --merged", TEXT)])
        for p in data["prs"][:5]:
            ref = f" #{p['number']}"
            lines.append([(" ✓ ", GREEN), (clip(p["repo"], width_chars - 3 - len(ref)), BLUE), (ref, DIM)])
    return lines


def doom_messages(data):
    msgs = [f"MERGED PR #{p['number']} INTO {p['repo']}!".upper() for p in data["prs"][:4]]
    for a in data["achievements"][:3]:
        verb = "WON" if a["badge"].lower() == "winner" else a["badge"]
        msgs.append(f"{verb}: {a['title']}!".upper())
    return msgs or [f"{USERNAME.upper()} HAS ENTERED THE GAME!"]


class _AsciiParser(HTMLParser):
    """Collects (char, color) pairs row by row from the <span style=color> art."""

    def __init__(self):
        super().__init__()
        self.rows = [[]]
        self._color = "#888888"
        self._in_body = False

    def handle_starttag(self, tag, attrs):
        if tag == "body":
            self._in_body = True
        elif tag == "br" and self._in_body:
            self.rows.append([])
        elif tag == "span":
            style = dict(attrs).get("style", "")
            if "color:" in style:
                self._color = style.split("color:")[1].split(";")[0].strip()

    def handle_startendtag(self, tag, attrs):
        if tag == "br" and self._in_body:
            self.rows.append([])

    def handle_data(self, data):
        if self._in_body:
            self.rows[-1].extend((ch, self._color) for ch in data if ch != "\n")


def load_art(path="ascii-art.html"):
    parser = _AsciiParser()
    with open(os.path.join(ROOT, path), encoding="utf-8") as f:
        parser.feed(f.read())
    return [r for r in parser.rows if r]


# ---------------------------------------------------------------------------
# Drawing
# ---------------------------------------------------------------------------

def render_logo(art_rows, width):
    """Pre-render the coloured ASCII logo once, at SCALE x; returns an RGB image."""
    cols = max(len(r) for r in art_rows)
    cell_w = width * SCALE / cols
    fs = cell_w / 0.6
    cell_h = fs * 1.12
    k = 3                                    # draw big, shrink: smoother tiny glyphs
    big = Image.new("RGB", (round(width * SCALE * k), round(len(art_rows) * cell_h * k) + 2 * k), BG)
    d = ImageDraw.Draw(big)
    f = None
    for regular, _ in FONTS:
        if os.path.exists(regular):
            f = ImageFont.truetype(regular, round(fs * k))
            break
    for r, row in enumerate(art_rows):
        for c, (ch, colour) in enumerate(row):
            if ch.strip():
                d.text((c * cell_w * k, r * cell_h * k), ch, font=f, fill=colour)
    return big.resize((big.width // k, big.height // k), Image.LANCZOS)


def chrome(cv, title):
    cv.rrect([0, 0, W - 1, H - 1], 12, BG, outline=STROKE)
    cv.rrect([1, 1, W - 2, TITLE_H + 10], 11, CHROME)
    cv.rect([1, 14, W - 2, TITLE_H], CHROME)
    for i, c in enumerate([(255, 95, 87), (254, 188, 46), (40, 200, 64)]):
        cv.ellipse([16 + i * 20, 10, 28 + i * 20, 22], c)
    cv.text((W / 2, TITLE_H / 2 + 1), title, font(13), DIM, anchor="mm")


def draw_segments(cv, x, y, segs, budget, f):
    """Draw coloured segments up to `budget` chars; returns (cursor_xy, left)."""
    cursor = (x, y)
    for text, colour in segs:
        part = text[:max(budget, 0)]
        if part:
            cv.text((x, y), part, f, colour)
            x += length(f, part)
        budget -= len(text)
        cursor = (x, y)
        if budget <= 0:
            break
    return cursor, budget


def cursor_block(cv, cursor, on, size=15):
    if on and cursor:
        cv.rect([cursor[0] + 1, cursor[1] + 1, cursor[0] + 9, cursor[1] + size + 2], BLUE)


# ---------------------------------------------------------------------------
# Frames
# ---------------------------------------------------------------------------

def neofetch_frames(data, logo, rows):
    """Yield canvases for the full-width neofetch phase."""
    user, host = data["user"], data["host"]
    prompt = f"{user}@{host}"
    prompt_segs = lambda: [(prompt, GREEN), (":", TEXT), ("~", BLUE), ("$ ", TEXT)]
    f_cmd, f_row, f_label, f_head = font(15), font(14), font(14, bold=True), font(16, bold=True)
    logo_x, logo_y = 28, TITLE_H + 36
    info_x = 412
    logo_h = logo.height / SCALE
    block_h = 40 + len(rows) * 25 + 24
    info_y = logo_y + max(0, (logo_h - block_h) / 2) + 6

    start, type_s = 0.4, 0.07
    cmd1, cmd2 = "neofetch", "doom"
    logo_at = start + len(cmd1) * type_s + 0.3
    row_gap = 0.025
    rows_end = logo_at + 0.2 + len(rows) * 0.12
    cmd2_at = rows_end + len(BLOCKS) * 0.05 + 0.9
    end = cmd2_at + len(cmd2) * 0.12 + 0.7
    plen = len(prompt) + 4            # prompt, ":", "~", "$ "

    for i in range(int(end * FPS)):
        t = i / FPS
        cv = Canvas()
        chrome(cv, f"{prompt}: ~")

        typed = max(0, min(len(cmd1), int((t - start) / type_s)))
        cur, _ = draw_segments(cv, 24, TITLE_H + 14, prompt_segs() + [(cmd1, TEXT)], plen + typed, f_cmd)

        if t >= logo_at:
            reveal = min(1.0, (t - logo_at) / (40 * row_gap))
            h = int(logo.height * reveal)
            if h:
                cv.paste(logo.crop((0, 0, logo.width, h)), (logo_x, logo_y))
            tx = t - logo_at
            cv.text((info_x, info_y), prompt, f_head, GOLD)
            cv.rect([info_x, info_y + 24, info_x + len(prompt) * 9.6, info_y + 25], FAINT)
            for k, (label, value) in enumerate(rows):
                if tx >= 0.2 + k * 0.12:
                    y = info_y + 42 + k * 25
                    cv.text((info_x, y), label, f_label, BLUE)
                    cv.text((info_x + length(f_label, label), y), f": {value}", f_row, TEXT)
            for k, c in enumerate(BLOCKS):
                if t >= rows_end + k * 0.05:
                    y = info_y + 42 + len(rows) * 25 - 4
                    cv.rect([info_x + k * 32, y, info_x + k * 32 + 28, y + 14], c)

        if t >= cmd2_at - 0.6:
            typed2 = max(0, min(len(cmd2), int((t - cmd2_at) / 0.12)))
            cur, _ = draw_segments(cv, 24, TITLE_H + BODY_H - 34, prompt_segs() + [(cmd2, TEXT)],
                                   plen + typed2, f_cmd)
        cursor_block(cv, cur, int(t * 2) % 2 == 0)
        yield cv.img


def split_frames(data, game_frames, msgs):
    """Yield canvases for the split: Doom left, typed pane right."""
    f_pane = font(11)
    prompt = f"{data['user']}@{data['host']}"
    width_chars = int((PANE_W - 20) / length(f_pane, "m"))
    lines = pane_lines(data, width_chars)
    total = sum(len(t) for line in lines for t, _ in line)
    f_msg = font(13, bold=True)
    top = TITLE_H + 14

    for i, game in enumerate(game_frames):
        t = i / FPS
        cv = Canvas()
        chrome(cv, f"{prompt}: ~ — tmux")
        cv.text((12, top - 2), "$ doom", font(12), DIM)
        gy = TITLE_H + 34
        cv.paste(game, (0, gy))
        msg_idx, msg_t = divmod(t, 3)
        if msgs and msg_t < 2.5:
            m = clip(msgs[int(msg_idx) % len(msgs)], 60)
            cv.text((7, gy + 7), m, f_msg, (0, 0, 0))
            cv.text((6, gy + 6), m, f_msg, DOOM_RED)
        # tmux-style status bar
        cv.rect([1, H - STATUS_H, W - 2, H - 2], (26, 90, 48))
        cv.text((12, H - 13), "[0] 0:doom*  1:zsh", font(11), (230, 245, 235), anchor="lm")
        cv.text((W - 12, H - 13), "ALT+F4", font(11), (230, 245, 235), anchor="rm")
        cv.line([(GAME_W, TITLE_H), (GAME_W, H - STATUS_H)], STROKE)
        # right pane typed out
        shown = min(total, int(total * t / TYPE_SECONDS))
        y, budget, cursor = top, shown, (PANE_X + 10, top)
        for line in lines:
            if budget <= 0 and y > top:
                break
            cursor, budget = draw_segments(cv, PANE_X + 10, y, line, budget, f_pane)
            y += PANE_LH
        cursor_block(cv, cursor, int(t * 2) % 2 == 0, size=11)
        yield cv.img


def read_game_frames(path, seconds):
    """Doom frames at FPS, scaled to the game pane."""
    size = (round(GAME_W * SCALE), round(GAME_H * SCALE))
    limit = int(seconds * FPS)
    if path.endswith(".webp"):                       # local preview source
        im = Image.open(path)
        for k in range(min(im.n_frames, limit)):
            im.seek(k)
            yield im.convert("RGB").crop((0, 0, GAME_W, GAME_H)).resize(size, Image.BICUBIC)
        return
    cmd = ["ffmpeg", "-loglevel", "error", "-i", path,
           "-vf", f"fps={FPS},scale={size[0]}:{size[1]}:flags=lanczos",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    nbytes = size[0] * size[1] * 3
    for _ in range(limit):
        buf = proc.stdout.read(nbytes)
        if len(buf) < nbytes:
            break
        yield Image.frombytes("RGB", size, buf)
    proc.kill()


def save(frames, out):
    """Merge identical neighbours into one longer frame, then write the WebP."""
    kept, durs = [], []
    for fr in frames:
        if kept and fr.tobytes() == kept[-1].tobytes():
            durs[-1] += 1000 // FPS
        else:
            kept.append(fr)
            durs.append(1000 // FPS)
    kept[0].save(out, save_all=True, append_images=kept[1:], duration=durs,
                 loop=0, quality=QUALITY, method=6)
    print(f"Saved {out}: {len(kept)} frames, {sum(durs) / 1000:.1f}s, "
          f"{os.path.getsize(out) / 1e6:.1f} MB")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("raw", help="Doom recording (mp4) or an animated webp for previews")
    ap.add_argument("out")
    ap.add_argument("--data", help="JSON with prs instead of calling the API")
    args = ap.parse_args()

    profile = load_profile()
    term = profile.get("terminal", {})
    if args.data:
        with open(args.data, encoding="utf-8") as f:
            oss = json.load(f)
    else:
        oss = oss_data(profile)
    data = {
        "user": term.get("user", USERNAME),
        "host": term.get("host", "github"),
        "prs": oss["prs"],
        "achievements": profile.get("achievements", []),
        "experience": profile.get("experience", []),
    }
    rows = [(label, str(value).replace("{oss_prs}", str(oss.get("total", len(oss["prs"])))))
            for label, value in term["rows"]]
    rows = [(label, clip(value, 52 - len(label))) for label, value in rows]

    logo = render_logo(load_art("ascii-art.html"), 330)
    msgs = [] if args.raw.endswith(".webp") else doom_messages(data)   # webp previews have them baked in

    frames = list(neofetch_frames(data, logo, rows))
    frames += split_frames(data, read_game_frames(args.raw, DOOM_SECONDS), msgs)
    save(frames, args.out)


if __name__ == "__main__":
    main()
