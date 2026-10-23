"""
Turns a raw Doom demo recording into the README animation (animated WebP):

  +--------------------------------+----------------------+
  | Doom demo playing itself       | altf4-games@doom:~$  |
  | "MERGED PR #484 INTO ..." msgs | stats / PRs / wins   |
  |                                | typed out like a tty |
  +--------------------------------+----------------------+

Data comes from profile.yml + the GitHub API (see profile_data.py), or from
a JSON file via --data for offline runs.

  python scripts/build_doom_anim.py doom_raw.mp4 doom.webp [--data data.json]
"""

import argparse
import json
import subprocess

from PIL import Image, ImageDraw, ImageFont

from profile_data import USERNAME, load_profile, oss_data, collect_stats

FPS = 12
GAME_W, GAME_H = 576, 360
PANEL_W = 324
W, H = GAME_W + PANEL_W, GAME_H
TYPE_SECONDS = 9      # how long the panel takes to type itself out
MSG_SECONDS = 3       # how long each Doom-style message stays up
QUALITY = 45          # animated WebP quality (0-100); GIF would be ~4x bigger

# GitHub dark palette, matching the terminal card in assets/dark/
BG = (13, 17, 23)
CHROME = (22, 27, 34)
DIM = (139, 148, 158)
TEXT = (230, 237, 243)
GREEN = (126, 231, 135)
CYAN = (56, 189, 248)
GOLD = (227, 179, 65)
BLUE = (56, 189, 248)
PURPLE = (163, 113, 247)
DOOM_RED = (230, 40, 40)

FONT_PATHS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
]


def font(size, bold=False):
    return ImageFont.truetype(FONT_PATHS[1 if bold else 0], size)


def clip(s, n):
    return s if len(s) <= n else s[: n - 1].rstrip() + "…"


def short_num(n):
    return f"{n / 1000:.1f}k".replace(".0k", "k") if n >= 1000 else str(n)


# ---------------------------------------------------------------------------
# Content
# ---------------------------------------------------------------------------

def panel_lines(data, width_chars):
    """List of lines; each line is a list of (text, colour) segments."""
    prompt = f"{data.get('user', USERNAME)}@doom:~$ "
    lines = []

    s = data.get("stats")
    if s:
        lines.append([(prompt, GREEN), ("./stats", TEXT)])
        lines.append([(" repos ", CYAN), (str(s["repos"]), TEXT),
                      ("  stars ", CYAN), (short_num(s["stars"]), TEXT),
                      ("  prs ", CYAN), (str(s["prs"]), TEXT)])
        lines.append([(" commits ", CYAN), (f"{s['commits']:,}", TEXT),
                      ("  followers ", CYAN), (str(s["followers"]), TEXT)])

    prs = data.get("prs") or []
    if prs:
        lines.append([(prompt, GREEN), ("git log --oss", TEXT)])
        for p in prs[:5]:
            ref = f" #{p['number']}"
            lines.append([(" ✓ ", PURPLE), (clip(p["repo"], width_chars - 4 - len(ref)), BLUE), (ref, DIM)])

    wins = data.get("achievements") or []
    if wins:
        lines.append([(prompt, GREEN), ("cat wins", TEXT)])
        for a in wins[:3]:
            lines.append([(" ★ ", GOLD), (clip(f"{a['title']} · {a['event']}", width_chars - 3), TEXT)])
    return lines


def doom_messages(data):
    msgs = [f"MERGED PR #{p['number']} INTO {p['repo']}!".upper() for p in (data.get("prs") or [])[:4]]
    for a in (data.get("achievements") or [])[:3]:
        verb = "WON" if a["badge"].lower() == "winner" else a["badge"]
        msgs.append(f"{verb}: {a['title']}!".upper())
    return msgs or [f"{USERNAME.upper()} HAS ENTERED THE GAME!"]


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def draw_panel(img, lines, chars_shown, cursor_on):
    d = ImageDraw.Draw(img)
    x0 = GAME_W
    d.rectangle([x0, 0, W, H], fill=BG)
    d.rectangle([x0, 0, W, 26], fill=CHROME)
    for i, c in enumerate([(255, 95, 86), (255, 189, 46), (39, 201, 63)]):
        d.ellipse([x0 + 10 + i * 16, 9, x0 + 18 + i * 16, 17], fill=c)
    f_title = font(11)
    d.text((x0 + PANEL_W / 2 + 20, 13), "doom — tty1", font=f_title, fill=DIM, anchor="mm")

    f = font(12)
    y, budget = 40, chars_shown
    cursor = None
    for line in lines:
        if budget <= 0:
            break
        x = x0 + 10
        for text, colour in line:
            part = text[:budget]
            d.text((x, y), part, font=f, fill=colour)
            x += f.getlength(part)
            budget -= len(part)
            if budget <= 0:
                cursor = (x, y)
                break
        else:
            cursor = (x, y)
        y += 23
    if cursor_on and cursor:
        d.rectangle([cursor[0] + 1, cursor[1] + 1, cursor[0] + 8, cursor[1] + 14], fill=TEXT)


def draw_message(img, msg):
    d = ImageDraw.Draw(img)
    f = font(13, bold=True)
    msg = clip(msg, 60)
    d.text((7, 7), msg, font=f, fill=(0, 0, 0))
    d.text((6, 6), msg, font=f, fill=DOOM_RED)


def read_frames(path):
    cmd = ["ffmpeg", "-loglevel", "error", "-i", path,
           "-vf", f"fps={FPS},scale={GAME_W}:{GAME_H}:flags=neighbor",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    size = GAME_W * GAME_H * 3
    while True:
        buf = proc.stdout.read(size)
        if len(buf) < size:
            break
        yield Image.frombytes("RGB", (GAME_W, GAME_H), buf)
    proc.wait()


def build(raw, out, data):
    lines = panel_lines(data, width_chars=int((PANEL_W - 20) / font(12).getlength("m")))
    total_chars = sum(len(t) for line in lines for t, _ in line)
    msgs = doom_messages(data)

    enc = subprocess.Popen([
        "ffmpeg", "-y", "-loglevel", "error",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
        "-c:v", "libwebp", "-lossless", "0", "-q:v", str(QUALITY),
        "-compression_level", "6", "-loop", "0", out,
    ], stdin=subprocess.PIPE)

    for i, game in enumerate(read_frames(raw)):
        t = i / FPS
        frame = Image.new("RGB", (W, H), BG)
        frame.paste(game, (0, 0))
        msg_idx, msg_t = divmod(t, MSG_SECONDS)
        if msg_t < MSG_SECONDS - 0.5:
            draw_message(frame, msgs[int(msg_idx) % len(msgs)])
        shown = min(total_chars, int(total_chars * t / TYPE_SECONDS))
        draw_panel(frame, lines, shown, cursor_on=int(t * 2) % 2 == 0)
        enc.stdin.write(frame.tobytes())
    enc.stdin.close()
    if enc.wait() != 0:
        raise SystemExit("ffmpeg failed")
    print("Saved", out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("raw")
    ap.add_argument("out")
    ap.add_argument("--data", help="JSON with prs/stats instead of calling the API")
    args = ap.parse_args()

    profile = load_profile()
    if args.data:
        with open(args.data, encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = {"prs": oss_data(profile)["prs"], "stats": collect_stats()}
    data.setdefault("achievements", profile.get("achievements", []))
    data.setdefault("user", profile.get("terminal", {}).get("user", USERNAME))
    build(args.raw, args.out, data)


if __name__ == "__main__":
    main()
