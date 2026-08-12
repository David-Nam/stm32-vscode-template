#!/usr/bin/env bash
# Build the template from scratch for another board, in a throwaway copy.
#
#   tools/try_board.sh NUCLEO-F411RE
#   tools/try_board.sh "" STM32G071RBTx      # no board entry, MCU only
#
# Copies the tracked files (no lib/, no build/), clears everything setup.py is
# meant to derive, then runs setup.py and make. This is the fresh-clone path a
# new user takes, so it catches anything that only works because our own
# working tree is already warm.
set -euo pipefail

BOARD=${1:-}
MCU=${2:-}
ROOT=$(cd "$(dirname "$0")/.." && pwd)
DEST=${TRY_DIR:-${TMPDIR:-/tmp}}/try-${BOARD:-$MCU}

rm -rf "$DEST"
mkdir -p "$DEST"
git -C "$ROOT" ls-files -co --exclude-standard | grep -vE '^(lib|build)/' |
  while read -r f; do
    mkdir -p "$DEST/$(dirname "$f")"
    cp "$ROOT/$f" "$DEST/$f"
  done
git -C "$DEST" init -q

cd "$DEST"
python3 - "$BOARD" "$MCU" <<'EOF'
import sys
sys.path.insert(0, "tools")
import setup as s
board, mcu = sys.argv[1], sys.argv[2]
s.write_config("BOARD", [board] if board else [])
s.write_config("MCU", [mcu] if mcu else [])
for k in ("FLASH_ORIGIN", "FLASH_SIZE", "RAM_ORIGIN", "RAM_SIZE", "RAM_REGION",
          "FAMILY", "DEVICE_DEFINE", "CPU_FLAGS", "HSE_HZ",
          "CONSOLE_UART", "CONSOLE_TX", "CONSOLE_RX", "CONSOLE_AF"):
    s.write_config(k, [])
EOF

echo "=== setup ==="
python3 tools/setup.py
echo "=== build ==="
make
