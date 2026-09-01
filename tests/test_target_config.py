import contextlib
import io
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest import mock

from tools import setup


TARGETS = {
    "H7": {
        "mcu": "STM32H743IITx", "define": "STM32H743xx",
        "core": "Cortex-M7", "fpu": "DP_FPU",
        "memories": (
            ("FLASH_Bank1", 0x08000000, 0x100000),
            ("FLASH_Bank2", 0x08100000, 0x100000),
            ("DTCMRAM", 0x20000000, 0x20000),
            ("RAM_D1", 0x24000000, 0x80000),
        ),
    },
    "F4": {
        "mcu": "STM32F411RETx", "define": "STM32F411xE",
        "core": "Cortex-M4", "fpu": "1",
        "memories": (
            ("Flash", 0x08000000, 0x80000),
            ("SRAM", 0x20000000, 0x20000),
        ),
    },
    "G0": {
        "mcu": "STM32G071RBTx", "define": "STM32G071xx",
        "core": "Cortex-M0+", "fpu": "NO_FPU",
        "memories": (
            ("Main_Flash", 0x08000000, 0x20000),
            ("SRAM", 0x20000000, 0x9000),
        ),
    },
}


def pack(family):
    target = TARGETS[family]
    root = ET.Element("package")
    ET.SubElement(root, "vendor").text = "Keil"
    ET.SubElement(root, "name").text = f"STM32{family}xx_DFP"
    releases = ET.SubElement(root, "releases")
    ET.SubElement(releases, "release", version=f"test-{family}")
    devices = ET.SubElement(root, "devices")
    family_node = ET.SubElement(devices, "family", Dfamily=f"STM32{family}")
    device = ET.SubElement(family_node, "device", Dname=target["mcu"])
    ET.SubElement(device, "processor", Dcore=target["core"], Dfpu=target["fpu"])
    ET.SubElement(device, "compile", define=target["define"])
    for name, start, size in target["memories"]:
        ET.SubElement(device, "memory", name=name,
                      start=f"0x{start:08X}", size=f"0x{size:X}")
    return root


class TargetConfigTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        root = Path(self.temporary.name)
        self.config = root / "config.cmake"
        self.device = root / "generated" / "device.cmake"
        self.config.write_text(setup.CFG.read_text(encoding="utf-8"),
                               encoding="utf-8")
        self.device.parent.mkdir()
        self.device.write_text(setup.DEVICE_CFG.read_text(encoding="utf-8"),
                               encoding="utf-8")
        self.paths = mock.patch.multiple(
            setup, CFG=self.config, DEVICE_CFG=self.device)
        self.paths.start()
        self.addCleanup(self.paths.stop)
        self.addCleanup(self.temporary.cleanup)

    def run_target(self, *, board="", mcu="", ram_region="", install=None,
                   dry=False):
        def resolve(part):
            family = next(name for name, data in TARGETS.items()
                          if data["mcu"] == part)
            return family, [f"https://example.test/cmsis-{family}",
                            f"https://example.test/hal-{family}"]

        install = install or mock.Mock()
        with mock.patch.object(setup, "resolve_family", side_effect=resolve), \
             mock.patch.object(setup, "fetch_pack", side_effect=pack), \
             mock.patch.object(setup, "install_dependencies", install), \
             mock.patch.object(setup, "check_host"), \
             contextlib.redirect_stdout(io.StringIO()):
            setup.cmd_target(board=board, mcu=mcu, ram_region=ram_region,
                             dry=dry)
        return install

    def test_retarget_sequence_has_no_stale_derived_values(self):
        self.run_target(board="NUCLEO-F411RE")
        f4 = setup.read_config(self.device)
        self.assertEqual(f4["STM32_GENERATED_MCU"], ["STM32F411RETx"])
        self.assertEqual(f4["FAMILY"], ["F4"])
        self.assertEqual(f4["FLASH_SIZE"], ["512K"])
        self.assertEqual(f4["RAM_SIZE"], ["128K"])
        self.assertEqual(f4["DEVICE_DEFINE"], ["STM32F411xE"])
        self.assertIn("-mcpu=cortex-m4", f4["CPU_FLAGS"])

        self.run_target(board="NUCLEO-G071RB")
        g0 = setup.read_config(self.device)
        self.assertEqual(g0["STM32_GENERATED_MCU"], ["STM32G071RBTx"])
        self.assertEqual(g0["FAMILY"], ["G0"])
        self.assertEqual(g0["FLASH_SIZE"], ["128K"])
        self.assertEqual(g0["RAM_SIZE"], ["36K"])
        self.assertEqual(g0["DEVICE_DEFINE"], ["STM32G071xx"])
        self.assertEqual(
            g0["CPU_FLAGS"],
            ["-mcpu=cortex-m0plus", "-mthumb", "-mfloat-abi=soft"])
        self.assertNotIn("STM32H743xx", self.device.read_text(encoding="utf-8"))
        self.assertNotIn("cortex-m7", self.device.read_text(encoding="utf-8"))

    def test_same_target_is_byte_for_byte_idempotent(self):
        self.run_target(board="NUCLEO-F411RE")
        first = (self.config.read_bytes(), self.device.read_bytes())
        self.run_target(board="NUCLEO-F411RE")
        second = (self.config.read_bytes(), self.device.read_bytes())
        self.assertEqual(first, second)

    def test_named_ram_region_is_part_of_the_atomic_target_selection(self):
        self.run_target(board="CoreH743I", ram_region="RAM_D1")
        config = setup.read_config(self.config)
        device = setup.read_config(self.device)
        self.assertEqual(config["RAM_REGION"], ["RAM_D1"])
        self.assertEqual(device["STM32_RAM_REGION"], ["RAM_D1"])
        self.assertEqual(device["RAM_ORIGIN"], ["0x24000000"])
        self.assertEqual(device["RAM_SIZE"], ["512K"])

    def test_direct_mcu_clears_board_specific_and_override_values(self):
        overrides = {
            "TARGET_FLASH_ORIGIN_OVERRIDE": ["0x08008000"],
            "TARGET_CPU_FLAGS_OVERRIDE": ["-mcpu=cortex-m7"],
        }
        text = setup.render_config_updates(
            self.config.read_text(encoding="utf-8"), overrides)
        self.config.write_text(text, encoding="utf-8")

        self.run_target(mcu="STM32F411RETx")
        cfg = setup.read_config(self.config)
        self.assertEqual(cfg["BOARD"], [])
        self.assertEqual(cfg["MCU"], ["STM32F411RETx"])
        self.assertEqual(cfg["CONSOLE_UART"], [])
        self.assertEqual(cfg["HSE_HZ"], [])
        for name in setup.TARGET_OVERRIDE_KEYS:
            self.assertEqual(cfg[name], [])

    def test_board_mcu_mismatch_fails_before_resolution_or_writes(self):
        mismatch = setup.render_config_updates(
            self.config.read_text(encoding="utf-8"),
            {"BOARD": ["NUCLEO-F411RE"], "MCU": ["STM32H743IITx"]})
        self.config.write_text(mismatch, encoding="utf-8")
        before = (self.config.read_bytes(), self.device.read_bytes())
        with mock.patch.object(setup, "resolve_family") as resolve:
            with self.assertRaises(SystemExit):
                setup.cmd_init(dry=False)
        resolve.assert_not_called()
        self.assertEqual(before, (self.config.read_bytes(), self.device.read_bytes()))

    def test_dependency_failure_leaves_target_files_unchanged(self):
        before = (self.config.read_bytes(), self.device.read_bytes())
        install = mock.Mock(side_effect=RuntimeError("injected git failure"))
        with self.assertRaisesRegex(RuntimeError, "injected git failure"):
            self.run_target(board="NUCLEO-F411RE", install=install)
        self.assertEqual(before, (self.config.read_bytes(), self.device.read_bytes()))

    def test_dry_run_leaves_target_files_unchanged(self):
        before = (self.config.read_bytes(), self.device.read_bytes())
        install = self.run_target(board="NUCLEO-F411RE", dry=True)
        self.assertEqual(before, (self.config.read_bytes(), self.device.read_bytes()))
        install.assert_called_once()
        self.assertTrue(install.call_args.args[-1])

    def test_pack_failure_stops_before_dependency_or_file_changes(self):
        before = (self.config.read_bytes(), self.device.read_bytes())
        install = mock.Mock()
        with mock.patch.object(
                setup, "resolve_family",
                return_value=("F4", ["cmsis", "hal"])), \
             mock.patch.object(setup, "fetch_pack", return_value=None), \
             mock.patch.object(setup, "install_dependencies", install), \
             contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(SystemExit):
                setup.cmd_target(board="NUCLEO-F411RE")
        install.assert_not_called()
        self.assertEqual(before, (self.config.read_bytes(), self.device.read_bytes()))

    def test_second_replace_failure_rolls_back_both_files(self):
        before = (self.config.read_bytes(), self.device.read_bytes())
        next_config = setup.render_config_updates(
            self.config.read_text(encoding="utf-8"),
            {"BOARD": ["NUCLEO-F411RE"], "MCU": ["STM32F411RETx"]})
        real_write = setup.atomic_write_text
        failed = False

        def fail_config_once(path, text):
            nonlocal failed
            if path == self.config and not failed:
                failed = True
                raise OSError("injected replace failure")
            real_write(path, text)

        with mock.patch.object(setup, "fetch_pack", return_value=pack("F4")), \
             contextlib.redirect_stdout(io.StringIO()):
            values = setup.resolve_device_values(
                "NUCLEO-F411RE", "STM32F411RETx", "F4")
            next_device = setup.render_device_config(values)
        with mock.patch.object(
                setup, "atomic_write_text", side_effect=fail_config_once):
            with self.assertRaisesRegex(OSError, "replace failure"):
                setup.write_target_files(next_config, next_device)
        self.assertEqual(before, (self.config.read_bytes(), self.device.read_bytes()))

    def test_generated_file_contains_deterministic_provenance(self):
        self.run_target(board="NUCLEO-F411RE")
        device = setup.read_config(self.device)
        self.assertEqual(device["STM32_PACK_VENDOR"], ["Keil"])
        self.assertEqual(device["STM32_PACK_NAME"], ["STM32F4xx_DFP"])
        self.assertEqual(device["STM32_PACK_VERSION"], ["test-F4"])
        self.assertEqual(device["STM32_PACK_PART"], ["STM32F411RETx"])
        for field in setup.DEVICE_FIELDS:
            self.assertIn(field, device)

    def test_target_cli_requires_exactly_one_selector(self):
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                setup.parse_target_args([])
            with self.assertRaises(SystemExit):
                setup.parse_target_args(
                    ["--board", "NUCLEO-F411RE", "--mcu", "STM32F411RETx"])


if __name__ == "__main__":
    unittest.main()
