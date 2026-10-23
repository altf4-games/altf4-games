#!/usr/bin/env bash
# Records Doom playing one of its built-in demos (deterministic, no input)
# into an mp4 using a virtual X display. Needs: chocolate-doom, freedoom,
# xvfb, ffmpeg (apt install chocolate-doom freedoom xvfb ffmpeg).
#
#   scripts/record_doom.sh <out.mp4> [demo] [seconds] [skip_seconds]
set -euo pipefail

OUT=${1:-doom_raw.mp4}
DEMO=${2:-demo1}
SECONDS_TO_RECORD=${3:-18}
SKIP=${4:-3}
IWAD=${IWAD:-/usr/share/games/doom/freedoom2.wad}
DOOM=${DOOM:-/usr/games/chocolate-doom}

WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT

# plain 640x400 window, no aspect stretching, no in-game messages
# (the HUD script draws its own messages on top)
cat > "$WORK/default.cfg" <<'EOF'
show_messages 0
screenblocks 10
EOF
cat > "$WORK/chocolate-doom.cfg" <<'EOF'
fullscreen 0
aspect_ratio_correct 0
window_width 640
window_height 400
grabmouse 0
EOF

cat > "$WORK/run.sh" <<EOF
export SDL_AUDIODRIVER=dummy
"$DOOM" -iwad "$IWAD" -playdemo "$DEMO" -window -nosound -nomusic \
  -config "$WORK/default.cfg" -extraconfig "$WORK/chocolate-doom.cfg" >/dev/null 2>&1 &
PID=\$!
sleep "$SKIP"
ffmpeg -y -loglevel error -f x11grab -draw_mouse 0 -video_size 640x400 \
  -framerate 15 -i "\$DISPLAY" -t "$SECONDS_TO_RECORD" -pix_fmt yuv420p "$OUT"
kill \$PID || true
EOF

xvfb-run -a -s "-screen 0 640x400x24" bash "$WORK/run.sh"
echo "Recorded $OUT"
