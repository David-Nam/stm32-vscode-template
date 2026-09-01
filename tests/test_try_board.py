import contextlib
import io
import subprocess
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest import mock

from tools import try_board


class ArgumentTests(unittest.TestCase):
    def parse_error(self, argv):
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as caught:
                try_board.parse_args(argv)
        self.assertEqual(caught.exception.code, 2)

    def test_accepts_board_mode(self):
        board = try_board.parse_args(["NUCLEO-F411RE", "--keep"])
        self.assertEqual(board.board, "NUCLEO-F411RE")
        self.assertTrue(board.keep)

    def test_rejects_missing_or_path_like_targets(self):
        invalid_argv = (
            [],
            [".."],
            ["../victim"],
            ["board/name"],
            [r"board\name"],
            [""],
        )
        for argv in invalid_argv:
            with self.subTest(argv=argv):
                self.parse_error(argv)

    def test_rejects_unknown_options_and_extra_positionals(self):
        self.parse_error(["NUCLEO-F411RE", "--unknown"])
        self.parse_error(["BOARD", "EXTRA"])


class HostToolTests(unittest.TestCase):
    @staticmethod
    def tool_lookup(missing=()):
        paths = {
            "git": "/tools/git",
            "cmake": "/tools/cmake",
            "ninja": "/tools/ninja",
            "st-flash": "/tools/st-flash",
        }
        return lambda tool: None if tool in missing else paths.get(tool)

    def test_off_path_toolchain_is_exported_to_child_environment(self):
        bindir = Path("/opt/arm/bin")
        with mock.patch.object(
                try_board.shutil, "which", side_effect=self.tool_lookup()), \
             mock.patch.object(
                 try_board.setup_tool, "find_toolchain",
                 return_value=(bindir, False)), \
             mock.patch.object(try_board.setup_tool, "has_newlib", return_value=True), \
             contextlib.redirect_stdout(io.StringIO()):
            env = try_board.build_environment(flash=True)
        self.assertEqual(env["ARM_TOOLCHAIN_BIN"], str(bindir))

    def test_missing_tools_fail_before_a_workspace_is_created(self):
        with mock.patch.object(
                try_board.shutil, "which",
                side_effect=self.tool_lookup({"ninja"})), \
             mock.patch.object(
                 try_board.setup_tool, "find_toolchain",
                 return_value=(None, False)):
            with self.assertRaisesRegex(
                    RuntimeError, "ninja, arm-none-eabi-gcc"):
                try_board.build_environment()

    def test_flash_requires_st_flash(self):
        with mock.patch.object(
                try_board.shutil, "which",
                side_effect=self.tool_lookup({"st-flash"})), \
             mock.patch.object(
                 try_board.setup_tool, "find_toolchain",
                 return_value=(Path("/opt/arm/bin"), True)), \
             mock.patch.object(try_board.setup_tool, "has_newlib", return_value=True):
            with self.assertRaisesRegex(RuntimeError, "st-flash"):
                try_board.build_environment(flash=True)


class BuildInvocationTests(unittest.TestCase):
    def test_discovered_environment_reaches_every_child_command(self):
        env = {"ARM_TOOLCHAIN_BIN": "/opt/arm/bin"}
        with tempfile.TemporaryDirectory() as temporary, \
             mock.patch.object(try_board.subprocess, "run") as raw_run, \
             mock.patch.object(try_board, "run") as child_run:
            try_board.build_in_workspace(
                Path(temporary), "CoreH743I", flash=True, env=env)

        raw_run.assert_called_once()
        self.assertEqual(child_run.call_count, 4)
        for call in child_run.call_args_list:
            self.assertIs(call.kwargs["env"], env)


class WorkspaceTests(unittest.TestCase):
    def test_parallel_workspaces_are_unique_and_preserve_existing_paths(self):
        with tempfile.TemporaryDirectory() as temporary:
            try_root = Path(temporary).resolve()
            existing = try_root / "try-NUCLEO-F411RE"
            existing.mkdir()
            sentinel = existing / "sentinel.txt"
            sentinel.write_text("keep", encoding="utf-8")

            with ThreadPoolExecutor(max_workers=8) as pool:
                workspaces = list(pool.map(
                    lambda _: try_board.create_workspace(
                        try_root, "NUCLEO-F411RE"),
                    range(8)))
            try:
                self.assertEqual(len(set(workspaces)), 8)
                self.assertTrue(all(path.parent == try_root
                                    for path in workspaces))
                self.assertEqual(sentinel.read_text(encoding="utf-8"), "keep")
            finally:
                for workspace in workspaces:
                    try_board.cleanup_workspace(workspace, try_root)

            self.assertTrue(existing.is_dir())

    def test_managed_workspace_cleans_by_default_and_keep_preserves(self):
        with tempfile.TemporaryDirectory() as temporary:
            try_root = Path(temporary).resolve()

            with try_board.managed_workspace(
                    try_root, "NUCLEO-F411RE") as transient:
                self.assertTrue(transient.is_dir())
            self.assertFalse(transient.exists())

            with try_board.managed_workspace(
                    try_root, "NUCLEO-F411RE", keep=True) as kept:
                self.assertTrue(kept.is_dir())
            self.assertTrue(kept.is_dir())
            try_board.cleanup_workspace(kept, try_root)

    def test_managed_workspace_cleans_after_failure(self):
        with tempfile.TemporaryDirectory() as temporary:
            try_root = Path(temporary).resolve()
            with self.assertRaisesRegex(RuntimeError, "injected"):
                with try_board.managed_workspace(
                        try_root, "NUCLEO-F411RE") as transient:
                    raise RuntimeError("injected")
            self.assertFalse(transient.exists())

    def test_cleanup_rejects_outside_and_unowned_directories(self):
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary).resolve()
            try_root = parent / "allowed"
            try_root.mkdir()

            outside = parent / "outside"
            outside.mkdir()
            (outside / try_board.WORKSPACE_MARKER).write_text(
                "forged", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "outside TRY_DIR"):
                try_board.cleanup_workspace(outside, try_root)
            self.assertTrue(outside.is_dir())

            unowned = try_root / "unowned"
            unowned.mkdir()
            with self.assertRaisesRegex(RuntimeError, "unowned workspace"):
                try_board.cleanup_workspace(unowned, try_root)
            self.assertTrue(unowned.is_dir())

    def test_try_root_must_exist_and_be_a_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.assertEqual(try_board.resolve_try_root(str(root)), root.resolve())

            missing = root / "missing"
            with self.assertRaisesRegex(ValueError, "does not exist"):
                try_board.resolve_try_root(str(missing))

            regular_file = root / "file"
            regular_file.write_text("not a directory", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "not a directory"):
                try_board.resolve_try_root(str(regular_file))


class CopyTests(unittest.TestCase):
    def test_copy_is_tracked_only_unless_explicitly_requested(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "source"
            root.mkdir()
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)

            (root / "tracked.txt").write_text("tracked", encoding="utf-8")
            (root / "untracked.txt").write_text("untracked", encoding="utf-8")
            (root / ".gitignore").write_text("ignored.txt\n", encoding="utf-8")
            (root / "ignored.txt").write_text("ignored", encoding="utf-8")
            (root / "lib").mkdir()
            (root / "lib" / "generated.c").write_text(
                "excluded", encoding="utf-8")
            subprocess.run(
                ["git", "add", "tracked.txt", ".gitignore", "lib/generated.c"],
                cwd=root, check=True)

            tracked_dest = Path(temporary) / "tracked-copy"
            tracked_dest.mkdir()
            try_board.copy_worktree(root, tracked_dest)
            self.assertTrue((tracked_dest / "tracked.txt").is_file())
            self.assertFalse((tracked_dest / "untracked.txt").exists())
            self.assertFalse((tracked_dest / "ignored.txt").exists())
            self.assertFalse((tracked_dest / "lib").exists())

            all_dest = Path(temporary) / "all-copy"
            all_dest.mkdir()
            try_board.copy_worktree(root, all_dest, include_untracked=True)
            self.assertTrue((all_dest / "tracked.txt").is_file())
            self.assertTrue((all_dest / "untracked.txt").is_file())
            self.assertFalse((all_dest / "ignored.txt").exists())
            self.assertFalse((all_dest / "lib").exists())


if __name__ == "__main__":
    unittest.main()
