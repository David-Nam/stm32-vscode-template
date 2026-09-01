#!/usr/bin/env python3
"""Build the template from scratch for another board, in a throwaway copy.

  python3 tools/try_board.py NUCLEO-F411RE
  python3 tools/try_board.py NUCLEO-F411RE --flash # ... and write it to the board
  python3 tools/try_board.py NUCLEO-F411RE --keep  # preserve the throwaway copy

Copies the working tree (no lib/, no build/), selects the board atomically with
setup.py target, then performs a full configure and build. This is the
fresh-clone path a new user takes, so it catches anything that only works
because our own working tree is already warm. MCU-only targets are deliberately
not accepted: a complete build also needs the console wiring that a board entry
provides.

--flash writes the result to whatever is on the ST-LINK, so connect the board
you named. Verifying on hardware this way keeps setup.py's output -- the
per-chip submodules and inc/ -- out of the template's own working tree.

The copy lands in a unique directory under the system temp directory and is
removed when the command exits. Set TRY_DIR to an existing directory to put it
elsewhere, or pass --keep to preserve it. Only tracked files are copied by
default; pass --include-untracked when a deliberate test needs untracked files.
"""

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path

try:
    from . import setup as setup_tool
except ImportError:  # Direct execution: python3 tools/try_board.py
    import setup as setup_tool

ROOT = Path(__file__).resolve().parent.parent

IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*\Z")
WORKSPACE_MARKER = ".stm32-try-board-workspace"
EXCLUDED_PREFIXES = ("lib/", "build/", "inc/")


def run(*cmd, cwd, env=None):
    print(f"\n=== {' '.join(str(c) for c in cmd)}")
    subprocess.run(cmd, cwd=cwd, check=True, env=env)


def argument_parser():
    parser = argparse.ArgumentParser(
        description="Build the template for another STM32 target in a safe "
                    "throwaway copy.")
    parser.add_argument("board", help="board name from setup.py --list-boards")
    parser.add_argument("--flash", action="store_true",
                        help="flash the built image to the connected ST-LINK")
    parser.add_argument("--keep", action="store_true",
                        help="preserve the throwaway copy after the command exits")
    parser.add_argument(
        "--include-untracked", action="store_true",
        help="also copy untracked, non-ignored files from the working tree")
    return parser


def parse_args(argv=None):
    parser = argument_parser()
    args = parser.parse_args(argv)
    if not IDENTIFIER.fullmatch(args.board):
        parser.error(
            "BOARD must contain only letters, digits, '_' or '-'; "
            "path components are not allowed")
    return args


def build_environment(flash=False):
    """Validate host tools and export the discovered Arm toolchain to children."""
    required = ["git", "cmake", "ninja"]
    if flash:
        required.append("st-flash")
    missing = [tool for tool in required if not shutil.which(tool)]

    bindir, _ = setup_tool.find_toolchain()
    if bindir is None:
        missing.append("arm-none-eabi-gcc")
    elif not setup_tool.has_newlib(bindir):
        raise RuntimeError(
            f"Arm GCC at {bindir} has no newlib; install the official Arm GNU "
            "Toolchain release")

    if missing:
        raise RuntimeError(
            "missing required host tool(s): " + ", ".join(missing) +
            f". Run `{setup_tool.PY} tools/setup.py doctor` for install guidance")

    env = os.environ.copy()
    env["ARM_TOOLCHAIN_BIN"] = str(bindir)
    print(f"host toolchain: {bindir} (ARM_TOOLCHAIN_BIN set automatically)")
    print(f"host generator: {shutil.which('ninja')}")
    return env


def resolve_try_root(raw_value=None):
    raw_value = raw_value if raw_value is not None else os.environ.get("TRY_DIR")
    root = Path(raw_value).expanduser() if raw_value else Path(tempfile.gettempdir())
    try:
        root = root.resolve(strict=True)
    except FileNotFoundError as exc:
        raise ValueError(f"TRY_DIR does not exist: {root}") from exc
    if not root.is_dir():
        raise ValueError(f"TRY_DIR is not a directory: {root}")
    return root


def create_workspace(try_root, label):
    try_root = try_root.resolve(strict=True)
    dest = Path(tempfile.mkdtemp(prefix=f"stm32-try-{label}-",
                                 dir=try_root)).resolve(strict=True)
    if dest.parent != try_root:
        raise RuntimeError(f"temporary workspace escaped TRY_DIR: {dest}")
    (dest / WORKSPACE_MARKER).write_text("owned by tools/try_board.py\n",
                                         encoding="utf-8")
    return dest


def cleanup_workspace(dest, try_root):
    try_root = try_root.resolve(strict=True)
    dest = dest.resolve(strict=True)
    if dest == try_root or dest.parent != try_root:
        raise RuntimeError(f"refusing to remove path outside TRY_DIR: {dest}")
    if not (dest / WORKSPACE_MARKER).is_file():
        raise RuntimeError(f"refusing to remove unowned workspace: {dest}")
    shutil.rmtree(dest)


@contextmanager
def managed_workspace(try_root, label, keep=False):
    dest = create_workspace(try_root, label)
    try:
        yield dest
    finally:
        if keep:
            print(f"kept throwaway workspace at {dest}")
        else:
            cleanup_workspace(dest, try_root)


def worktree_files(root, include_untracked=False):
    cmd = ["git", "ls-files", "-z", "--cached"]
    if include_untracked:
        cmd.extend(("--others", "--exclude-standard"))
    output = subprocess.run(cmd, cwd=root, capture_output=True,
                            check=True).stdout
    return [os.fsdecode(path) for path in output.split(b"\0") if path]


def copy_worktree(root, dest, include_untracked=False):
    for f in worktree_files(root, include_untracked):
        # Everything setup.py produces: the submodules, the build output and the
        # HAL config it copies into inc/. A hal_conf from another family would
        # be left alone by setup.py and could hide a bug. .gitmodules goes with
        # them: this copy has no submodule gitlinks in its index, so leaving the
        # entries behind would only give setup.py stale paths.
        if f.startswith(EXCLUDED_PREFIXES) or f == ".gitmodules":
            continue
        source = root / f
        if not source.exists() and not source.is_symlink():
            continue
        target = dest / f
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target, follow_symlinks=False)


def build_in_workspace(dest, board, flash=False, env=None):
    subprocess.run(["git", "init", "-q"], cwd=dest, check=True)
    run(sys.executable, "tools/setup.py", "target", "--board", board,
        cwd=dest, env=env)
    run("cmake", "--preset", "default", cwd=dest, env=env)
    run("cmake", "--build", "--preset", "default", cwd=dest, env=env)
    if flash:
        run("cmake", "--build", "--preset", "flash", cwd=dest, env=env)


def main(argv=None):
    parser = argument_parser()
    args = parse_args(argv)
    try:
        try_root = resolve_try_root()
        env = build_environment(args.flash)
    except (ValueError, RuntimeError) as exc:
        parser.error(str(exc))

    with managed_workspace(try_root, args.board, args.keep) as dest:
        print(f"copying the working tree to {dest}")
        copy_worktree(ROOT, dest, args.include_untracked)
        build_in_workspace(dest, args.board, args.flash, env)


if __name__ == "__main__":
    main()
