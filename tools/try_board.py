#!/usr/bin/env python3
"""Build the template from scratch for another board, in a throwaway copy.

  python3 tools/try_board.py NUCLEO-F411RE
  python3 tools/try_board.py "" STM32G071RBTx      # no board entry, MCU only

Copies the working tree (no lib/, no build/), clears everything setup.py is
meant to derive, then runs setup.py and a full configure and build. This is the
fresh-clone path a new user takes, so it catches anything that only works
because our own working tree is already warm.

The copy lands in the system temp directory; set TRY_DIR to put it elsewhere.
"""

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Everything setup.py is supposed to work out for itself. HSE_HZ is in here
# because it is a board property: nothing derives it, and a stale value from
# another board is worse than an empty one.
DERIVED = ("FLASH_ORIGIN", "FLASH_SIZE", "RAM_ORIGIN", "RAM_SIZE", "RAM_REGION",
           "FAMILY", "DEVICE_DEFINE", "CPU_FLAGS", "HSE_HZ",
           "CONSOLE_UART", "CONSOLE_TX", "CONSOLE_RX", "CONSOLE_AF")


def run(*cmd, cwd):
    print(f"\n=== {' '.join(str(c) for c in cmd)}")
    subprocess.run(cmd, cwd=cwd, check=True)


def main():
    board = sys.argv[1] if len(sys.argv) > 1 else ""
    mcu = sys.argv[2] if len(sys.argv) > 2 else ""
    if not board and not mcu:
        sys.exit(__doc__)

    dest = Path(os.environ.get("TRY_DIR") or tempfile.gettempdir()) / f"try-{board or mcu}"
    shutil.rmtree(dest, ignore_errors=True)
    print(f"copying the working tree to {dest}")

    files = subprocess.run(["git", "ls-files", "-co", "--exclude-standard"],
                           cwd=ROOT, capture_output=True, text=True,
                           check=True).stdout.split("\n")
    for f in filter(None, files):
        # lib/ and build/ are the submodules and the build output. .gitmodules
        # goes with them: this copy has no submodule gitlinks in its index, so
        # leaving the entries behind would only give setup.py stale paths.
        if f.startswith(("lib/", "build/")) or f == ".gitmodules":
            continue
        (dest / f).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(ROOT / f, dest / f)
    subprocess.run(["git", "init", "-q"], cwd=dest, check=True)

    # setup.py resolves its own paths from __file__, so importing the copy
    # rewrites the copy's config.cmake and leaves ours alone.
    sys.path.insert(0, str(dest / "tools"))
    import setup

    setup.write_config("BOARD", [board] if board else [])
    setup.write_config("MCU", [mcu] if mcu else [])
    for key in DERIVED:
        setup.write_config(key, [])

    run(sys.executable, "tools/setup.py", cwd=dest)
    run("cmake", "--preset", "default", cwd=dest)
    run("cmake", "--build", "--preset", "default", cwd=dest)


if __name__ == "__main__":
    main()
