"""
One animated terminal for the top of the README (animated WebP):

  1. `neofetch` types itself and prints the card (ASCII logo + info rows)
  2. `doom` is typed, the window splits: Doom demo on the left,
     `cat wins` / `cat work` typed out in a new pane on the right

Doom frames come from a raw recording (see record_doom.sh) or, for local
previews, from an existing animated WebP.

  python scripts/build_terminal_anim.py doom_raw.mp4 terminal.webp [--data data.json]
"""

import argparse
import json
import os
import subprocess

from PIL import Image, ImageDraw, ImageFont

from build_profile import load_art
from profile_data import USERNAME, load_profile, oss_data

FPS = 12
W = 900
TITLE_H = 32
BODY_H = 420
H = TITLE_H + BODY_H
GAME_W, GAME_H = 576, 360
PANE_X = GAME_W + 1                  # right pane starts after the divider
PANE_W = W - PANE_X
DOOM_SECONDS = 14                    # how long the split-screen part runs
QUALITY = 45

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


def font(size, bold=False):
    for regular, heavy in FONTS:
        path = heavy if bold else regular
        if os.path.exists(path):
            idx = 1 if (bold and path.endswith(".ttc")) else 0
            return ImageFont.truetype(path, size, index=idx)
    raise SystemExit("no monospace font found")


def clip(s, n):
    return s if len(s) <= n else s[: n - 1].rstrip() + "…"


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
    return lines


def doom_messages(data):
    msgs = [f"MERGED PR #{p['number']} INTO {p['repo']}!".upper() for p in data["prs"][:4]]
    for a in data["achievements"][:3]:
        verb = "WON" if a["badge"].lower() == "winner" else a["badge"]
        msgs.append(f"{verb}: {a['title']}!".upper())
    return msgs or [f"{USERNAME.upper()} HAS ENTERED THE GAME!"]


# ---------------------------------------------------------------------------
# Drawing
# ---------------------------------------------------------------------------

def render_logo(art_rows, width):
    """Pre-render the coloured ASCII logo once; returns an RGB image."""
    cols = max(len(r) for r in art_rows)
    cell_w = width / cols
    fs = cell_w / 0.6
    cell_h = fs * 1.12
    k = 4                                    # draw big, shrink: smoother tiny glyphs
    big = Image.new("RGB", (width * k, int(len(art_rows) * cell_h * k) + 2 * k), BG)
    d = ImageDraw.Draw(big)
    f = font(round(fs * k))
    for r, row in enumerate(art_rows):
        for c, (ch, colour) in enumerate(row):
            if ch.strip():
                d.text((c * cell_w * k, r * cell_h * k), ch, font=f, fill=colour)
    return big.resize((width, big.height // k), Image.LANCZOS)


def chrome(d, title):
    d.rounded_rectangle([0, 0, W - 1, H - 1], radius=12, outline=STROKE, fill=BG)
    d.rounded_rectangle([1, 1, W - 2, TITLE_H + 10], radius=11, fill=CHROME)
    d.rectangle([1, 14, W - 2, TITLE_H], fill=CHROME)
    for i, c in enumerate([(255, 95, 87), (254, 188, 46), (40, 200, 64)]):
        d.ellipse([16 + i * 20, 10, 28 + i * 20, 22], fill=c)
    d.text((W / 2, TITLE_H / 2 + 1), title, font=font(13), fill=DIM, anchor="mm")


def draw_segments(d, x, y, segs, budget, f):
    """Draw coloured segments up to `budget` chars; returns (cursor_xy, left)."""
    cursor = (x, y)
    for text, colour in segs:
        part = text[:max(budget, 0)]
        if part:
            d.text((x, y), part, font=f, fill=colour)
            x += f.getlength(part)
        budget -= len(text)
        cursor = (x, y)
        if budget <= 0:
            break
    return cursor, budget


def cursor_block(d, cursor, on, size=15):
    if on and cursor:
        d.rectangle([cursor[0] + 1, cursor[1] + 1, cursor[0] + 9, cursor[1] + size + 2], fill=BLUE)


# ---------------------------------------------------------------------------
# Frames
# ---------------------------------------------------------------------------

def neofetch_frames(data, logo, rows):
    """Yield PIL frames for the full-width neofetch phase."""
    user, host = data["user"], data["host"]
    prompt = f"{user}@{host}"
    prompt_segs = lambda: [(prompt, GREEN), (":", TEXT), ("~", BLUE), ("$ ", TEXT)]
    f_cmd, f_row, f_head = font(15), font(14), font(16, bold=True)
    logo_x, logo_y = 28, TITLE_H + 36
    info_x = 412
    block_h = 40 + len(rows) * 25 + 24
    info_y = logo_y + max(0, (logo.height - block_h) / 2) + 6

    start = 0.4
    type_s = 0.07
    cmd1 = "neofetch"
    logo_at = start + len(cmd1) * type_s + 0.3
    row_gap = 0.025
    info_at = logo_at
    rows_end = info_at + 0.2 + len(rows) * 0.12
    blocks_at = rows_end
    cmd2_at = blocks_at + len(BLOCKS) * 0.05 + 0.9
    cmd2 = "doom"
    end = cmd2_at + len(cmd2) * 0.12 + 0.7

    n = int(end * FPS)
    for i in range(n):
        t = i / FPS
        img = Image.new("RGB", (W, H), BG)
        d = ImageDraw.Draw(img)
        chrome(d, f"{prompt}: ~")

        # first prompt + typed command
        typed = max(0, min(len(cmd1), int((t - start) / type_s)))
        segs = prompt_segs() + [(cmd1, TEXT)]
        cur, _ = draw_segments(d, 24, TITLE_H + 14, segs, len(prompt) + 4 + typed, f_cmd)
        blink = int(t * 2) % 2 == 0

        if t >= logo_at:
            reveal = min(1.0, (t - logo_at) / (40 * row_gap))
            h = int(logo.height * reveal)
            if h:
                img.paste(logo.crop((0, 0, logo.width, h)), (logo_x, logo_y))
            tx = t - info_at
            if tx >= 0:
                d.text((info_x, info_y), prompt, font=f_head, fill=GOLD)
                d.rectangle([info_x, info_y + 24, info_x + len(prompt) * 9.6, info_y + 25], fill=FAINT)
            for k, (label, value) in enumerate(rows):
                if tx >= 0.2 + k * 0.12:
                    y = info_y + 42 + k * 25
                    d.text((info_x, y), label, font=font(14, bold=True), fill=BLUE)
                    d.text((info_x + font(14, bold=True).getlength(label), y), f": {value}", font=f_row, fill=TEXT)
            for k, c in enumerate(BLOCKS):
                if t >= blocks_at + k * 0.05:
                    y = info_y + 42 + len(rows) * 25 - 4
                    d.rectangle([info_x + k * 32, y, info_x + k * 32 + 28, y + 14], fill=c)

        if t >= cmd2_at - 0.6 and t < end:
            # second prompt at the bottom of the card
            py = TITLE_H + BODY_H - 34
            typed2 = max(0, min(len(cmd2), int((t - cmd2_at) / 0.12)))
            segs2 = prompt_segs() + [(cmd2, TEXT)]
            cur, _ = draw_segments(d, 24, py, segs2, len(prompt) + 4 + typed2, f_cmd)
        cursor_block(d, cur, blink)
        yield img


def split_frames(data, pane, game_frames, msgs):
    """Yield frames for the split: Doom left, typed pane right."""
    f_pane = font(12)
    prompt = f"{data['user']}@{data['host']}"
    char_w = f_pane.getlength("m")
    width_chars = int((PANE_W - 20) / char_w)
    lines = pane_lines(data, width_chars)
    total = sum(len(t) for line in lines for t, _ in line)
    type_s = 7.0
    f_msg = font(13, bold=True)

    for i, game in enumerate(game_frames):
        t = i / FPS
        img = Image.new("RGB", (W, H), BG)
        d = ImageDraw.Draw(img)
        chrome(d, f"{prompt}: ~ — tmux")
        top = TITLE_H + 14
        # left pane: `doom` header then the game
        d.text((12, top - 2), "$ doom", font=font(12), fill=DIM)
        gy = TITLE_H + 34
        img.paste(game, (0, gy))
        msg_idx, msg_t = divmod(t, 3)
        if msgs and msg_t < 2.5:
            m = clip(msgs[int(msg_idx) % len(msgs)], 60)
            d.text((7, gy + 7), m, font=f_msg, fill=(0, 0, 0))
            d.text((6, gy + 6), m, font=f_msg, fill=DOOM_RED)
        # tmux-style status bar
        d.rectangle([1, H - 24, W - 2, H - 2], fill=(26, 90, 48))
        d.text((12, H - 13), f"[0] 0:doom*  1:zsh", font=font(11), fill=(230, 245, 235), anchor="lm")
        d.text((W - 12, H - 13), "ALT+F4", font=font(11), fill=(230, 245, 235), anchor="rm")
        # divider
        d.line([(GAME_W, TITLE_H), (GAME_W, H - 24)], fill=STROKE, width=1)
        # right pane typed out
        shown = min(total, int(total * t / type_s))
        y, budget, cursor = top, shown, (PANE_X + 10, top)
        for line in lines:
            if budget <= 0 and y > top:
                break
            cursor, budget = draw_segments(d, PANE_X + 10, y, line, budget, f_pane)
            y += 21
        cursor_block(d, cursor, int(t * 2) % 2 == 0, size=12)
        yield img


def read_game_frames(path, seconds):
    """Doom frames at FPS, GAME_W x GAME_H."""
    limit = int(seconds * FPS)
    if path.endswith(".webp"):                       # local preview source
        im = Image.open(path)
        for k in range(min(im.n_frames, limit)):
            im.seek(k)
            yield im.convert("RGB").crop((0, 0, GAME_W, GAME_H))
        return
    cmd = ["ffmpeg", "-loglevel", "error", "-i", path,
           "-vf", f"fps={FPS},scale={GAME_W}:{GAME_H}:flags=neighbor",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    size = GAME_W * GAME_H * 3
    for _ in range(limit):
        buf = proc.stdout.read(size)
        if len(buf) < size:
            break
        yield Image.frombytes("RGB", (GAME_W, GAME_H), buf)
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

    logo = render_logo(load_art("dark"), 330)
    msgs = [] if args.raw.endswith(".webp") else doom_messages(data)   # webp previews have them baked in

    frames = list(neofetch_frames(data, logo, rows))
    frames += split_frames(data, None, read_game_frames(args.raw, DOOM_SECONDS), msgs)
    save(frames, args.out)


if __name__ == "__main__":
    main()
