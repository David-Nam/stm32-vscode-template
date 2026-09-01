#!/usr/bin/env python3
"""Resolve the STM32 family from config.cmake and wire up the ST submodules.

  python3 tools/setup.py               fetch CMSIS + HAL/LL for the configured MCU
  python3 tools/setup.py target --board NUCLEO-F411RE
  python3 tools/setup.py target --mcu STM32F411RETx
  python3 tools/setup.py doctor        check this machine has the build tools
  python3 tools/setup.py doctor --fix  ... and record an off-PATH toolchain
  python3 tools/setup.py --dry-run     resolve and print, touch nothing
  python3 tools/setup.py --list-boards
  python3 tools/setup.py pins [UART]   console pin/AF candidates for this MCU
  python3 tools/setup.py add <alias|url>   add an extra library submodule

Windows spells the interpreter `python`, macOS and Linux `python3`.
"""

import argparse
import glob
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CFG = ROOT / "config.cmake"
DEVICE_CFG = ROOT / "generated" / "device.cmake"
LIB = ROOT / "lib"
INC = ROOT / "inc"
GH = "https://github.com/STMicroelectronics"
# RTOS in config.cmake -> the repository holding it. Anything not listed here
# is left to `setup.py add <url>`; the build only needs a cmake/rtos-<name>.cmake.
RTOS_REPOS = {"freertos": ("https://github.com/FreeRTOS/FreeRTOS-Kernel",
                           "freertos-kernel")}
# Only for the hints this script prints: the Windows installers give you
# python.exe and no python3.exe.
PY = "python" if os.name == "nt" else "python3"

# CMSIS-Pack descriptor. This is where the per-device memory map lives: the
# CMSIS headers only carry base addresses, and FLASH_SIZE there is a runtime
# read of the flash size register, which the linker cannot use.
PACK_URL = "https://www.keil.com/pack/Keil.STM32{fam}xx_DFP.pdsc"

# board -> (mcu, uart, tx, rx, alternate function). Memory comes from the pack.
# The NUCLEOs list the UART their on-board ST-LINK exposes as a virtual COM
# port. CoreH743I has no bridge of its own, so its entry is the pair this
# template was tested on with an external USB-serial adapter; move the adapter
# or the entry if you wire it somewhere else.
BOARDS = {
    "CoreH743I":     ("STM32H743IITx", "UART4",  "PH13", "PH14", "8"),
    "NUCLEO-H743ZI": ("STM32H743ZITx", "USART3", "PD8", "PD9",  "7"),
    "NUCLEO-F411RE": ("STM32F411RETx", "USART2", "PA2", "PA3",  "7"),
    "NUCLEO-G071RB": ("STM32G071RBTx", "USART2", "PA2", "PA3",  "1"),
}

# HSE is board wiring, not a property of the MCU. These values describe the
# clock source fitted to, or supplied by ST-LINK on, the known boards above.
BOARD_HSE_HZ = {name: "8000000" for name in BOARDS}

DEVICE_FIELDS = (
    "STM32_GENERATED_BOARD", "STM32_GENERATED_MCU", "STM32_PACK_URL",
    "STM32_PACK_VENDOR", "STM32_PACK_NAME", "STM32_PACK_VERSION",
    "STM32_PACK_PART", "FAMILY", "FLASH_ORIGIN", "FLASH_SIZE",
    "RAM_ORIGIN", "RAM_SIZE", "STM32_RAM_REGION", "DEVICE_DEFINE",
    "PROCESSOR_CORE", "PROCESSOR_FPU", "CPU_FLAGS",
)

TARGET_OVERRIDE_KEYS = (
    "TARGET_FLASH_ORIGIN_OVERRIDE", "TARGET_FLASH_SIZE_OVERRIDE",
    "TARGET_RAM_ORIGIN_OVERRIDE", "TARGET_RAM_SIZE_OVERRIDE",
    "TARGET_DEVICE_DEFINE_OVERRIDE", "TARGET_CPU_FLAGS_OVERRIDE",
)

def die(msg):
    sys.exit(f"error: {msg}")


def run(*args, **kw):
    return subprocess.run(args, cwd=ROOT, check=True, text=True, **kw)


# --- config.cmake read/write ----------------------------------------------

def set_re(name=r"\w+"):
    """Match one single-line set(NAME value...) with an optional trailing comment.

    Groups: 1 prefix, 2 name, 3 value, 4 trailing comment.
    The value stops at the first ')', so a comment containing parentheses
    cannot be swallowed into it.
    """
    return rf'^([ \t]*set\([ \t]*({name})[ \t]*)([^)\n]*)\)([ \t]*(?:#.*)?)$'


def parse_config_text(text):
    cfg = {}
    for m in re.finditer(set_re(), text, re.M):
        cfg[m.group(2)] = [v for v in shlex.split(m.group(3)) if v]
    return cfg


def read_config(path=None):
    path = path or CFG
    return parse_config_text(path.read_text(encoding="utf-8"))


def cmake_body(values):
    if not values:
        return '""'
    return " ".join('"' + str(value).replace("\\", "\\\\").replace('"', '\\"') + '"'
                    for value in values)


def render_config_updates(text, updates):
    for name, values in updates.items():
        body = cmake_body(values)
        text, n = re.subn(set_re(re.escape(name)),
                          lambda m: m.group(1) + body + ")" + m.group(4),
                          text, count=1, flags=re.M)
        if not n:
            die(f"config.cmake has no single-line set({name} ...) line")
    return text


def atomic_write_text(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_text(encoding="utf-8") == text:
        return
    handle = tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=path.parent,
        prefix=f".{path.name}.", suffix=".tmp", delete=False)
    temporary = Path(handle.name)
    try:
        with handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def write_config(name, values):
    text = render_config_updates(
        CFG.read_text(encoding="utf-8"), {name: values})
    atomic_write_text(CFG, text)


def render_device_config(values):
    missing = [name for name in DEVICE_FIELDS if name not in values]
    if missing:
        raise ValueError(f"device config is missing: {', '.join(missing)}")
    lines = [
        "# Generated by tools/setup.py target. Do not edit by hand.",
        "# Re-run the target command to replace this file atomically.",
        "",
    ]
    for name in DEVICE_FIELDS:
        value = values[name]
        items = value if isinstance(value, list) else [value]
        lines.append(f"set({name} {cmake_body(items)})")
    return "\n".join(lines) + "\n"


def write_target_files(config_text, device_text):
    """Replace the two target files as one fail-closed transaction.

    There is no portable two-file atomic rename. device.cmake is replaced
    first and carries BOARD/MCU identity fields, so an interruption can only
    produce a CMake mismatch error, never a silently mixed target. An ordinary
    write failure rolls both files back to their original bytes.
    """
    originals = {}
    for path in (DEVICE_CFG, CFG):
        originals[path] = path.read_text(encoding="utf-8") if path.exists() else None
    try:
        atomic_write_text(DEVICE_CFG, device_text)
        atomic_write_text(CFG, config_text)
    except Exception:
        for path in (DEVICE_CFG, CFG):
            original = originals[path]
            if original is None:
                path.unlink(missing_ok=True)
            else:
                atomic_write_text(path, original)
        raise


# --- family resolution -----------------------------------------------------

def family_candidates(mcu):
    """Candidate family strings for a part number, best guess first.

    STM32H743IITx -> H7      STM32WB55RG -> WB5, WB
    STM32H7S3L8   -> H7RS    STM32G071RB -> G0
    """
    mcu = mcu.upper()
    m = re.match(r"^STM32([A-Z]+)(\d)", mcu)
    if not m:
        die(f"cannot parse a family out of MCU={mcu!r} "
            f"(expected something like STM32H743IITx)")
    letters, digit = m.group(1), m.group(2)
    out = []
    if re.match(r"^STM32H7[RS]", mcu):      # H7Rx/H7Sx live in their own repo
        out.append("H7RS")
    out += [letters + digit, letters]
    return list(dict.fromkeys(out))


def repo_exists(url):
    return subprocess.run(["git", "ls-remote", "--exit-code", "-h", url],
                          capture_output=True).returncode == 0


def resolve_family(mcu):
    """Pick the family whose repos actually exist on GitHub. No guessing."""
    tried = []
    for fam in family_candidates(mcu):
        f = fam.lower()
        repos = [f"{GH}/cmsis-device-{f}", f"{GH}/stm32{f}xx-hal-driver"]
        print(f"  checking {fam:5s} ... ", end="", flush=True)
        if all(repo_exists(r) for r in repos):
            print("found")
            return fam, repos
        print("no")
        tried += repos
    die(f"no ST repository matches MCU={mcu}.\n  tried:\n    " +
        "\n    ".join(tried))


# --- memory map, from the CMSIS-Pack --------------------------------------

def pack_part(mcu):
    """Part name as the pack spells it: a trailing temperature grade digit
    becomes 'x'. STM32H743IIT6 -> STM32H743IITx"""
    return re.sub(r"\d$", "x", mcu)


def fetch_pack(fam):
    url = PACK_URL.format(fam=fam.upper())
    req = urllib.request.Request(url, headers={"User-Agent": "stm32-template-setup"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return ET.fromstring(r.read())
    except Exception as e:
        print(f"  warning: cannot read {url} ({e})")
        return None


def pack_provenance(root, fam):
    release = root.find("./releases/release")
    return {
        "STM32_PACK_URL": PACK_URL.format(fam=fam.upper()),
        "STM32_PACK_VENDOR": root.findtext("vendor") or "unknown",
        "STM32_PACK_NAME": root.findtext("name") or f"STM32{fam.upper()}xx_DFP",
        "STM32_PACK_VERSION": (release.get("version")
                               if release is not None else "unknown"),
    }


def pack_device(root, part):
    """Everything we need about `part`: memory map, device define, core, FPU.

    Attributes are inherited down family > subFamily > device, so they have to
    be accumulated on the way in. Two naming conventions are in use: G0/H7 put
    the full part name in <device Dname=...>, F4 uses a short Dname plus
    <variant Dvariant=...>.
    """
    def walk(node, inherited):
        info = {k: dict(v) if k == "mem" else v for k, v in inherited.items()}
        for m in node.findall("memory"):
            info["mem"][m.get("name")] = (int(m.get("start"), 16), int(m.get("size"), 16))
        for c in node.findall("compile"):
            if c.get("define"):
                info["define"] = c.get("define")
        for p in node.findall("processor"):
            for key, attr in (("core", "Dcore"), ("fpu", "Dfpu")):
                if p.get(attr):
                    info[key] = p.get(attr)
        if node.tag == "device":
            names = [node.get("Dname")] + [v.get("Dvariant") for v in node.findall("variant")]
            if part in names:
                return info
        for child in node:
            if child.tag in ("family", "subFamily", "device"):
                hit = walk(child, info)
                if hit is not None:
                    return hit
        return None

    for fam in root.iter("family"):
        hit = walk(fam, {"mem": {}})
        if hit is not None:
            return hit
    return None


# -mcpu for each core the STM32 range uses.
CORE_MCPU = {
    "Cortex-M0": "cortex-m0", "Cortex-M0+": "cortex-m0plus",
    "Cortex-M3": "cortex-m3", "Cortex-M4": "cortex-m4",
    "Cortex-M7": "cortex-m7", "Cortex-M33": "cortex-m33",
    "Cortex-M55": "cortex-m55", "Cortex-M85": "cortex-m85",
}
# (core, single/double precision) -> -mfpu. Anything else falls back to
# -mfpu=auto, which lets gcc derive the unit from -mcpu.
CORE_FPU = {
    ("Cortex-M4", "SP"): "fpv4-sp-d16",
    ("Cortex-M7", "SP"): "fpv5-sp-d16",
    ("Cortex-M7", "DP"): "fpv5-d16",
    ("Cortex-M33", "SP"): "fpv5-sp-d16",
    ("Cortex-M33", "DP"): "fpv5-d16",
}


def cpu_flags(core, fpu):
    """Compiler flags for a core. `fpu` uses either the current spelling
    (DP_FPU/SP_FPU/NO_FPU) or the legacy 1/0 that the STM32F4 pack still uses.
    """
    if core not in CORE_MCPU:
        die(f"unknown core {core!r}; set CPU_FLAGS in config.cmake by hand")
    flags = [f"-mcpu={CORE_MCPU[core]}", "-mthumb"]
    kind = {"DP_FPU": "DP", "SP_FPU": "SP", "1": "SP"}.get(fpu or "NO_FPU")
    if not kind:
        return flags + ["-mfloat-abi=soft"]
    unit = CORE_FPU.get((core, kind), "auto")
    if unit == "auto":
        print(f"  note: no -mfpu mapping for {core}/{kind}, using -mfpu=auto")
    return flags + [f"-mfpu={unit}", "-mfloat-abi=hard"]


def contiguous_size(regions, origin):
    """Total size of the block of back-to-back regions starting at `origin`.

    STM32H743 splits its 2 MB flash into two 1 MB banks that abut, and U5
    splits SRAM into three abutting blocks. Both are one region to the linker.
    """
    end, used = origin, set()
    while True:
        nxt = next(((s, sz) for s, sz in regions
                    if s == end and (s, sz) not in used), None)
        if not nxt:
            return end - origin
        used.add(nxt)
        end += nxt[1]


IS_FLASH = re.compile(r"flash|rom", re.I)


def derive_memory(mems, ram_region=None):
    """Pick the flash and RAM blocks the linker script should use.

    RAM defaults to whatever sits at 0x20000000. That is TCM or main SRAM on
    every STM32 and is usable straight out of reset; picking the largest
    region instead would land on things like the STM32H7 D2 SRAM, which hangs
    unless its RCC clock is enabled first.
    """
    # Drop secure aliases of a region that also has a non-secure view.
    m = {n: v for n, v in mems.items()
         if not (n.endswith("_S") and n[:-2] + "_NS" in mems)}
    flash = {n: v for n, v in m.items() if IS_FLASH.search(n)}
    ram = {n: v for n, v in m.items() if not IS_FLASH.search(n)}
    if not flash or not ram:
        die(f"pack entry has no usable flash/ram regions: {sorted(mems)}")

    f_origin = min(s for s, _ in flash.values())
    f_size = contiguous_size(flash.values(), f_origin)

    if ram_region:
        if ram_region not in mems:
            die(f"RAM_REGION={ram_region!r} not in pack; available: {sorted(ram)}")
        name = ram_region
    else:
        at_default = [n for n, (s, _) in ram.items() if s == 0x20000000]
        name = at_default[0] if at_default else max(ram, key=lambda n: ram[n][1])
    r_origin = mems[name][0]
    r_size = contiguous_size(ram.values(), r_origin)
    return f_origin, f_size, r_origin, r_size, name


def kb(n):
    return f"{n // 1024}K"


# --- console pin candidates, from ST's open pin data ------------------------
#
# Which UART is wired to the USB-serial bridge is a board decision, so nothing
# can derive it. What can be derived is the pin and alternate-function number
# for each choice, which is the part people otherwise dig out of a datasheet.

PINDATA = "https://raw.githubusercontent.com/STMicroelectronics/STM32_open_pin_data/master/mcu"
PINDATA_TREE = ("https://api.github.com/repos/STMicroelectronics/"
                "STM32_open_pin_data/git/trees/master:mcu")
UART_SIG = re.compile(r"^(LPUART\d+|US?ART\d+)_(TX|RX)$")


def fetch(url, as_json=False):
    req = urllib.request.Request(url, headers={"User-Agent": "stm32-template-setup"})
    with urllib.request.urlopen(req, timeout=30) as r:
        raw = r.read()
    if as_json:
        import json
        return json.loads(raw)
    root = ET.fromstring(raw)
    for el in root.iter():                      # drop the xmlns noise
        el.tag = el.tag.rsplit("}", 1)[-1]
    return root


def pin_name(raw):
    """Canonical pin name out of ST's spelling, which carries the boot/debug
    role along: "PB3 (JTDO/TRACESWO)" -> "PB3". Power and reset pins drop out.
    """
    m = re.match(r"^(P[A-Z]\d+)\b", (raw or "").strip())
    return m.group(1) if m else None


def pindata_file(part):
    """Find the pin-data file for a part. Names are sometimes patterns that
    stand for several parts, e.g. STM32C031C(4-6)Tx covers C4 and C6."""
    names = [e["path"] for e in fetch(PINDATA_TREE, as_json=True)["tree"]
             if e["path"].endswith(".xml")]
    if f"{part}.xml" in names:
        return f"{part}.xml"
    for name in names:
        pat = "".join(
            "(?:" + "|".join(re.escape(a) for a in tok[1:-1].split("-")) + ")"
            if tok.startswith("(") else re.escape(tok)
            for tok in re.split(r"(\([^)]*\))", name[:-4]))
        if re.fullmatch(pat, part, re.I):
            return name
    die(f"{part} is not in ST's open pin data")


def cmd_pins(mcu, want=None):
    part = pack_part(mcu)
    print(f"console pin candidates for {part}"
          + (f", {want} only" if want else "") + "\n")
    mcu_xml = fetch(f"{PINDATA}/{urllib.parse.quote(pindata_file(part))}")

    on_package = {n for n in (pin_name(p.get("Name")) for p in mcu_xml.findall("Pin")) if n}
    gpio = next((ip.get("Version") for ip in mcu_xml.findall("IP")
                 if ip.get("Name") == "GPIO"), None)
    if not gpio:
        die(f"{part} has no GPIO IP entry in the pin data")
    modes = fetch(f"{PINDATA}/IP/GPIO-{urllib.parse.quote(gpio)}_Modes.xml")

    found = {}
    for pin in modes.findall("GPIO_Pin"):
        name = pin_name(pin.get("Name"))
        if not name or name not in on_package:
            continue
        for sig in pin.findall("PinSignal"):
            m = UART_SIG.match(sig.get("Name") or "")
            af = sig.find("SpecificParameter/PossibleValue")
            # Value looks like GPIO_AF8_UART4. The number is not positional:
            # on STM32H743, UART4 is AF8 on PH13 but AF6 on PA12.
            n = re.match(r"GPIO_AF(\d+)_", af.text or "") if af is not None else None
            if m and n:
                # A pin can be listed more than once when the family file
                # carries remap variants; the pair is what matters.
                found.setdefault(m.group(1), {"TX": set(), "RX": set()})
                found[m.group(1)][m.group(2)].add((name, n.group(1)))

    for inst in sorted(found):
        if want and inst != want.upper():
            continue
        for role in ("TX", "RX"):
            pins = " ".join(f"{p}(AF{af})" for p, af in sorted(found[inst][role]))
            print(f"  {inst if role == 'TX' else '':10s} {role} {pins}")
        print()
    print("Pick a TX/RX pair that shares an AF number and put it in config.cmake:")
    print('  set(CONSOLE_UART "UART4")   set(CONSOLE_TX "PH13")')
    print('  set(CONSOLE_AF "8")         set(CONSOLE_RX "PH14")')


# --- host tools -------------------------------------------------------------
#
# What a README cannot do: look at this machine. Nothing here installs anything
# or edits your shell profile -- it reports what is missing with the command to
# fix it, and writes the one path the project owns (ARM_TOOLCHAIN_BIN, plus the
# copy of it VSCode needs) when the toolchain is installed but off PATH.

HOST = "windows" if os.name == "nt" else "macos" if sys.platform == "darwin" else "linux"

ARM_DOWNLOAD = "https://developer.arm.com/downloads/-/arm-gnu-toolchain-downloads"

# tool -> what breaks without it, and how each host installs it.
TOOLS = [
    ("git", "everything", {"macos": "xcode-select --install",
                           "linux": "sudo apt install git",
                           "windows": "winget install Git.Git"}),
    ("cmake", "the build", {"macos": "brew install cmake",
                            "linux": "sudo apt install cmake",
                            "windows": "winget install Kitware.CMake"}),
    ("ninja", "the build (CMakePresets.json asks for it)",
     {"macos": "brew install ninja",
      "linux": "sudo apt install ninja-build",
      "windows": "winget install Ninja-build.Ninja"}),
    ("arm-none-eabi-gcc", "compiling anything",
     {h: f"{ARM_DOWNLOAD}  (Homebrew's build has no newlib, printf will not link)"
      for h in ("macos", "linux", "windows")}),
    ("st-flash", "cmake --build --preset flash",
     {"macos": "brew install stlink",
      "linux": "sudo apt install stlink-tools",
      "windows": "https://github.com/stlink-org/stlink/releases"}),
    ("st-util", "the VSCode 'Debug (st-util)' configuration",
     {"macos": "brew install stlink",
      "linux": "sudo apt install stlink-tools",
      "windows": "https://github.com/stlink-org/stlink/releases"}),
    ("openocd", "the VSCode 'Debug (OpenOCD)' configuration",
     {"macos": "brew install open-ocd",
      "linux": "sudo apt install openocd",
      "windows": "https://openocd.org/pages/getting-openocd.html"}),
]
NEEDED_TO_BUILD = ("git", "cmake", "ninja", "arm-none-eabi-gcc")

# Where each host's installer puts the Arm toolchain when it is not on PATH.
# Newest first once sorted, so a machine with several releases gets the latest.
TOOLCHAIN_GLOBS = {
    "macos": ["/Applications/ArmGNUToolchain/*/*/bin",
              "~/.local/opt/arm-gnu-toolchain-*/bin",
              "/opt/arm-gnu-toolchain-*/bin",
              "/usr/local/arm-gnu-toolchain-*/bin"],
    "linux": ["~/.local/opt/arm-gnu-toolchain-*/bin",
              "/opt/arm-gnu-toolchain-*/bin",
              "/usr/local/arm-gnu-toolchain-*/bin",
              "/opt/gcc-arm-none-eabi-*/bin"],
    "windows": ["C:/Program Files (x86)/Arm GNU Toolchain arm-none-eabi/*/bin",
                "C:/Program Files/Arm GNU Toolchain arm-none-eabi/*/bin",
                "~/AppData/Local/Programs/Arm GNU Toolchain arm-none-eabi/*/bin"],
}

VSCODE_SETTINGS = ROOT / ".vscode" / "settings.json"
GDB_PATH_LINE = re.compile(
    r'^[ \t]*(?://[ \t]*)?"cortex-debug\.armToolchainPath".*\n', re.M)


def find_toolchain():
    """(bin directory, is it on PATH). Falls back to env and install dirs."""
    found = shutil.which("arm-none-eabi-gcc")
    if found:
        return Path(found).parent, True
    configured = os.environ.get("ARM_TOOLCHAIN_BIN")
    if configured:
        configured = os.path.expanduser(configured)
        if shutil.which("arm-none-eabi-gcc", path=configured):
            return Path(configured), False
    for pattern in TOOLCHAIN_GLOBS[HOST]:
        for d in sorted(glob.glob(os.path.expanduser(pattern)), reverse=True):
            if shutil.which("arm-none-eabi-gcc", path=d):
                return Path(d), False
    return None, False


def has_newlib(bindir):
    """Homebrew's arm-none-eabi-gcc ships no newlib, so --specs=nano.specs has
    nothing to link against. Ask gcc where libc_nano.a is: it echoes the bare
    name back when it cannot find one."""
    gcc = shutil.which("arm-none-eabi-gcc", path=str(bindir))
    out = subprocess.run([gcc, "-print-file-name=libc_nano.a"],
                         capture_output=True, text=True).stdout.strip()
    return os.path.isabs(out) and Path(out).exists()


def cmake_version():
    out = subprocess.run(["cmake", "--version"], capture_output=True,
                         text=True).stdout
    m = re.search(r"(\d+)\.(\d+)\.(\d+)", out)
    return tuple(int(g) for g in m.groups()) if m else None


def set_vscode_toolchain(bindir, settings=None):
    """Point Cortex-Debug at an off-PATH toolchain. The setting sits in
    settings.json as a commented example; swap it for a live one."""
    settings = settings or VSCODE_SETTINGS
    if not settings.exists():
        return False
    txt = settings.read_text()
    line = f'  "cortex-debug.armToolchainPath": "{Path(bindir).as_posix()}",\n'
    if line in txt:
        return True
    seen = [0]

    def repl(_):
        seen[0] += 1
        return line if seen[0] == 1 else ""     # keep one, drop the examples

    txt, n = GDB_PATH_LINE.subn(repl, txt)
    if not n:
        return False
    settings.write_text(txt)
    return True


def wire_toolchain(bindir, on_path, fix):
    """Record an off-PATH toolchain where the build and the debugger look.

    Both files are committed, so this only happens when asked for: `doctor`
    says what it would write, `doctor --fix` writes it.
    """
    if on_path:
        return
    environment_path = os.environ.get("ARM_TOOLCHAIN_BIN")
    if environment_path:
        environment_path = Path(os.path.expanduser(environment_path))
        if environment_path.resolve() == Path(bindir).resolve():
            return
    if ")" in str(bindir):
        # config.cmake is read back by a line parser that stops at the first
        # ')', which the default Windows install path is full of.
        print("      that path contains ')', which config.cmake cannot hold.")
        print("      Add it to PATH instead, or set the environment variable:")
        print(f"        ARM_TOOLCHAIN_BIN={bindir}")
        return
    posix = Path(bindir).as_posix()
    if (read_config().get("ARM_TOOLCHAIN_BIN") or [""])[0] == posix:
        return
    if not fix:
        print(f"      run `{PY} tools/setup.py doctor --fix` to write this path")
        print("      into config.cmake and .vscode/settings.json")
        return
    write_config("ARM_TOOLCHAIN_BIN", [posix])
    print("      wrote ARM_TOOLCHAIN_BIN into config.cmake")
    if set_vscode_toolchain(bindir):
        print("      wrote cortex-debug.armToolchainPath into .vscode/settings.json")


def check_host(brief=False, fix=False):
    """Report on the host tools. Returns the list of missing build tools."""
    if not brief:
        print(f"host: {HOST}\n")
    missing = []
    for tool, purpose, hints in TOOLS:
        note = ""
        if tool == "arm-none-eabi-gcc":
            bindir, on_path = find_toolchain()
            path = str(bindir) if bindir else None
            if bindir and not has_newlib(bindir):
                path, note = None, "found, but it has no newlib"
            elif bindir and not on_path:
                note = "not on PATH"
        else:
            path = shutil.which(tool)
            if tool == "cmake" and path:
                v = cmake_version()
                if v and v < (3, 21):
                    path, note = None, f"{'.'.join(map(str, v))} is too old, need 3.21"
                elif v:
                    note = ".".join(map(str, v))

        if path and not brief:
            print(f"  {tool:18s} ok    {path}" + (f"  ({note})" if note else ""))
        if not path:
            if tool in NEEDED_TO_BUILD:
                missing.append(tool)
            print(f"  {tool:18s} MISSING  {note or 'needed for ' + purpose}")
            print(f"      {hints[HOST]}")
        if tool == "arm-none-eabi-gcc" and path:
            wire_toolchain(bindir, on_path, fix)

    if missing:
        print(f"\n{len(missing)} tool(s) missing before this can build: "
              + ", ".join(missing))
    elif not brief:
        print("\nall build tools present")
    return missing


# --- submodules ------------------------------------------------------------

def is_registered(rel):
    """True if the index already carries a gitlink for this path, which it does
    in every repository generated from the template."""
    out = subprocess.run(["git", "ls-files", "--stage", "--", rel],
                         cwd=ROOT, capture_output=True, text=True).stdout
    return out.startswith("160000")             # git's mode for a submodule


def add_submodule(url, path, depth=False, dry=False):
    rel = path.relative_to(ROOT).as_posix()     # git wants '/' on Windows too
    if path.exists() and any(path.iterdir()):
        print(f"  {rel} already present, skipping")
        return
    # Cloning without --recurse-submodules leaves the directory empty while the
    # entry is still in .gitmodules and in the index. `git submodule add` calls
    # that a conflict, so check it out instead of trying to add it again.
    if is_registered(rel):
        print(f"  {rel} registered but empty, checking it out")
        if not dry:
            run("git", "submodule", "update", "--init", "--", rel,
                stdout=subprocess.DEVNULL)
        return
    cmd = ["git", "submodule", "add"] + (["--depth", "1"] if depth else []) + \
          ["--", url, rel]
    if dry:
        print(f"  would run: {' '.join(cmd)}")
        return
    print(f"  adding {rel}")
    run(*cmd, stdout=subprocess.DEVNULL)


def copy_hal_conf(hal_dir, dry=False):
    tpl = next(hal_dir.glob("Inc/*_hal_conf_template.h"), None)
    if not tpl:
        die(f"no *_hal_conf_template.h under {hal_dir}/Inc")
    dst = INC / tpl.name.replace("_template", "")
    if dst.exists():
        print(f"  {dst.relative_to(ROOT)} already present, keeping your edits")
        return
    if dry:
        print(f"  would copy {tpl.name} -> {dst.relative_to(ROOT)}")
        return
    INC.mkdir(exist_ok=True)
    shutil.copy(tpl, dst)
    print(f"  copied {dst.relative_to(ROOT)}")


# --- commands --------------------------------------------------------------

def target_selection(board="", mcu="", ram_region=""):
    if board:
        if board not in BOARDS:
            die(f"unknown BOARD={board!r}. Run --list-boards, or use --mcu.")
        board_mcu, uart, tx, rx, af = BOARDS[board]
        if mcu and mcu != board_mcu:
            die(f"BOARD={board} requires MCU={board_mcu}, not {mcu}")
        mcu = board_mcu
        console = (uart, tx, rx, af)
        hse_hz = BOARD_HSE_HZ.get(board, "")
    else:
        console = ("", "", "", "")
        hse_hz = ""
    if not mcu:
        die("BOARD or MCU is required")

    updates = {
        "BOARD": [board] if board else [],
        "MCU": [mcu],
        "RAM_REGION": [ram_region] if ram_region else [],
        "CONSOLE_UART": [console[0]] if console[0] else [],
        "CONSOLE_TX": [console[1]] if console[1] else [],
        "CONSOLE_RX": [console[2]] if console[2] else [],
        "CONSOLE_AF": [console[3]] if console[3] else [],
        "HSE_HZ": [hse_hz] if hse_hz else [],
    }
    updates.update({name: [] for name in TARGET_OVERRIDE_KEYS})
    return mcu, updates


def configured_target(cfg):
    board = (cfg.get("BOARD") or [""])[0]
    mcu = (cfg.get("MCU") or [""])[0]
    if board:
        if board not in BOARDS:
            die(f"unknown BOARD={board!r}. Run --list-boards, or use setup.py target.")
        board_mcu = BOARDS[board][0]
        if mcu != board_mcu:
            die(f"BOARD={board} requires MCU={board_mcu}, not {mcu or '<empty>'}. "
                f"Run: {PY} tools/setup.py target --board {board}")
    if not mcu:
        die("target is not configured. Run setup.py target --board or --mcu")
    return board, mcu


def resolve_device_values(board, mcu, fam, ram_region=""):
    part = pack_part(mcu)
    print(f"  reading {part} from CMSIS-Pack")
    root = fetch_pack(fam)
    if root is None:
        die("CMSIS-Pack is required to change target; existing target files were not changed")
    info = pack_device(root, part)
    if not info:
        die(f"{part} is not listed in {PACK_URL.format(fam=fam.upper())}; "
            "existing target files were not changed")

    for n, (s, sz) in sorted(info["mem"].items(), key=lambda kv: kv[1][0]):
        print(f"      {n:12s} 0x{s:08X}  {kb(sz):>7s}")
    region = ram_region or None
    f_o, f_s, r_o, r_s, chosen = derive_memory(info["mem"], region)
    print(f"    flash 0x{f_o:08X} {kb(f_s)}   ram {chosen} 0x{r_o:08X} {kb(r_s)}")
    print(f"    {info.get('core')}  fpu={info.get('fpu')}  define={info.get('define')}")

    if not info.get("define"):
        die(f"pack has no compile define for {part}; existing target files were not changed")

    values = {
        "STM32_GENERATED_BOARD": board,
        "STM32_GENERATED_MCU": mcu,
        "STM32_PACK_PART": part,
        "FAMILY": fam,
        "FLASH_ORIGIN": f"0x{f_o:08X}",
        "FLASH_SIZE": kb(f_s),
        "RAM_ORIGIN": f"0x{r_o:08X}",
        "RAM_SIZE": kb(r_s),
        "STM32_RAM_REGION": chosen,
        "DEVICE_DEFINE": info["define"],
        "PROCESSOR_CORE": info.get("core") or "",
        "PROCESSOR_FPU": info.get("fpu") or "",
        "CPU_FLAGS": cpu_flags(info.get("core"), info.get("fpu")),
    }
    values.update(pack_provenance(root, fam))
    return values


def print_device_diff(old, new):
    changed = []
    for name in DEVICE_FIELDS:
        old_value = " ".join(old.get(name, [])) or "<unset>"
        value = new[name]
        new_value = " ".join(value) if isinstance(value, list) else value
        new_value = new_value or "<unset>"
        if old_value != new_value:
            changed.append((name, old_value, new_value))
    if not changed:
        print("target metadata unchanged")
        return
    print("target metadata changes:")
    for name, old_value, new_value in changed:
        print(f"  {name}: {old_value} -> {new_value}")


def install_dependencies(cfg, fam, dev_url, hal_url, dry=False):
    print("submodules:")
    if not dry:
        LIB.mkdir(exist_ok=True)
    add_submodule(f"{GH}/cmsis-core", LIB / "cmsis-core", dry=dry)
    add_submodule(dev_url, LIB / f"cmsis-device-{fam.lower()}", dry=dry)
    hal_dir = LIB / f"stm32{fam.lower()}xx-hal-driver"
    add_submodule(hal_url, hal_dir, dry=dry)

    rtos = (cfg.get("RTOS") or [""])[0]
    if rtos in RTOS_REPOS:
        url, path = RTOS_REPOS[rtos]
        add_submodule(url, LIB / path, dry=dry)
    elif rtos and rtos != "none":
        print(f"  RTOS={rtos} is not one setup.py knows how to fetch. Add its "
              f"sources with `{PY} tools/setup.py add <url>`.")

    if dry:
        return
    copy_hal_conf(hal_dir)
    n_hal = len(list(hal_dir.glob("Src/*_hal_*.c")))
    n_ll = len(list(hal_dir.glob("Src/*_ll_*.c")))
    print(f"dependencies ready: family {fam}, {n_hal} HAL sources, {n_ll} LL sources")


def report_console(cfg, mcu):
    missing = [key for key in ("CONSOLE_UART", "CONSOLE_TX", "CONSOLE_RX", "CONSOLE_AF")
               if not (cfg.get(key) or [""])[0]]
    if missing:
        print(f"\nconsole not configured yet: {', '.join(missing)}")
        print(f"  the build will not run until these are set. To see what "
              f"{mcu} offers:\n    {PY} tools/setup.py pins")


def cmd_init(dry):
    cfg = read_config()
    board, mcu = configured_target(cfg)
    if not DEVICE_CFG.exists():
        die(f"{DEVICE_CFG.relative_to(ROOT)} is missing. Run: {PY} tools/setup.py "
            f"target {'--board ' + board if board else '--mcu ' + mcu}")
    device = read_config(DEVICE_CFG)
    generated_board = (device.get("STM32_GENERATED_BOARD") or [""])[0]
    generated_mcu = (device.get("STM32_GENERATED_MCU") or [""])[0]
    if (generated_board, generated_mcu) != (board, mcu):
        die("config.cmake target does not match generated/device.cmake. Run: "
            f"{PY} tools/setup.py target "
            f"{'--board ' + board if board else '--mcu ' + mcu}")

    print(f"resolving family for {mcu}")
    fam, (dev_url, hal_url) = resolve_family(mcu)
    generated_family = (device.get("FAMILY") or [""])[0]
    if generated_family != fam:
        die(f"generated FAMILY={generated_family} does not match resolved FAMILY={fam}. "
            "Run setup.py target again")
    install_dependencies(cfg, fam, dev_url, hal_url, dry)

    if not dry:
        report_console(cfg, mcu)
        check_host(brief=True)
        print(f"done: target {board or mcu}, family {fam}")
    else:
        print(f"dry run done: family {fam}")


def cmd_target(board="", mcu="", ram_region="", dry=False):
    current_text = CFG.read_text(encoding="utf-8")
    selected_mcu, updates = target_selection(board, mcu, ram_region)
    next_text = render_config_updates(current_text, updates)
    next_cfg = parse_config_text(next_text)

    print(f"target {board or selected_mcu} -> {selected_mcu}")
    print(f"resolving family for {selected_mcu}")
    fam, (dev_url, hal_url) = resolve_family(selected_mcu)
    ram_region = (next_cfg.get("RAM_REGION") or [""])[0]
    device_values = resolve_device_values(board, selected_mcu, fam, ram_region)
    device_text = render_device_config(device_values)
    old_device = read_config(DEVICE_CFG) if DEVICE_CFG.exists() else {}
    print_device_diff(old_device, device_values)

    old_family = (old_device.get("FAMILY") or [""])[0]
    if old_family and old_family != fam:
        print(f"note: existing {old_family} family submodules and HAL config are kept; "
              "remove them explicitly after verifying the new target")

    # Dependency setup can fail for network or git reasons. Do it before the
    # target files are replaced so the previous target remains byte-for-byte
    # intact on those failures.
    install_dependencies(next_cfg, fam, dev_url, hal_url, dry)
    if dry:
        print("dry run done: target files unchanged")
        return

    try:
        write_target_files(next_text, device_text)
    except Exception as exc:
        die(f"could not commit target files atomically: {exc}")
    report_console(next_cfg, selected_mcu)
    check_host(brief=True)
    print(f"done: target {board or selected_mcu}, family {fam}")


def cmd_add(target):
    cfg = read_config()
    mcu = (cfg.get("MCU") or [""])[0]
    depth = False
    if target == "cube":
        # Full Cube repo: examples, BSP, middlewares. Shallow, it is huge.
        fam, _ = resolve_family(mcu)
        url, depth = f"{GH}/STM32Cube{fam}", True
    else:
        url = target
    if not repo_exists(url):
        die(f"{url} is not reachable")

    path = LIB / url.rstrip("/").rsplit("/", 1)[-1].removesuffix(".git")
    LIB.mkdir(exist_ok=True)
    add_submodule(url, path, depth=depth)

    rel = path.relative_to(ROOT).as_posix()
    dirs = [d for d in cfg.get("EXTRA_LIB_DIRS", []) if d]
    if rel not in dirs:
        write_config("EXTRA_LIB_DIRS", dirs + [rel])
        print(f"  EXTRA_LIB_DIRS += {rel}")


def self_test():
    """Offline check of the parsers. No network, no git."""
    def parse(line):
        m = re.search(set_re(), line, re.M)
        return (m.group(2), [v for v in shlex.split(m.group(3)) if v]) if m else None

    assert parse('set(A "1")') == ("A", ["1"])
    assert parse('  set(A "1")   ') == ("A", ["1"])
    assert parse('set(A "")') == ("A", [])
    assert parse("set(A)") == ("A", [])
    assert parse("set(A -x -y)") == ("A", ["-x", "-y"])
    # A trailing comment must not leak into the value, parentheses or not.
    assert parse('set(A "1") # note') == ("A", ["1"])
    assert parse('set(A "1")  # note (with parens)') == ("A", ["1"])
    # Multi-line set() is not supported and must not half-match.
    assert parse('set(A\n  "1")') is None

    for mcu, want in [("STM32H743IITx", "H7"), ("STM32F411RETx", "F4"),
                      ("STM32G071RBTx", "G0"), ("STM32L476RGTx", "L4"),
                      ("STM32C031C6Tx", "C0"), ("STM32U575ZITx", "U5")]:
        assert family_candidates(mcu)[0] == want, (mcu, family_candidates(mcu))
    # Families with no digit in the repo name fall through to the 2nd candidate.
    assert family_candidates("STM32WB55RGVx") == ["WB5", "WB"]
    assert family_candidates("STM32WBA52CGUx") == ["WBA5", "WBA"]
    # H7Rx/H7Sx are a separate repo and must be tried first.
    assert family_candidates("STM32H7S3L8Hx")[0] == "H7RS"

    for bad in ["STM32", "H743IITx", "notachip"]:
        try:
            family_candidates(bad)
        except SystemExit:
            pass
        else:
            raise AssertionError(f"{bad} should have been rejected")

    assert pack_part("STM32H743IIT6") == "STM32H743IITx"
    assert pack_part("STM32H743IITx") == "STM32H743IITx"

    # Real STM32H743IITx pack entry: two abutting 1 MB flash banks, and RAM
    # spread over four non-abutting regions.
    h743 = {"DTCMRAM": (0x20000000, 0x20000), "RAM_D1": (0x24000000, 0x80000),
            "RAM_D2": (0x30000000, 0x48000), "RAM_D3": (0x38000000, 0x10000),
            "FLASH_Bank1": (0x08000000, 0x100000),
            "FLASH_Bank2": (0x08100000, 0x100000)}
    assert derive_memory(h743) == (0x08000000, 2048 * 1024, 0x20000000, 128 * 1024, "DTCMRAM")
    # An explicit region wins, and picks up nothing contiguous after it.
    assert derive_memory(h743, "RAM_D1")[2:] == (0x24000000, 512 * 1024, "RAM_D1")

    # Real STM32U575ZITx entry: secure aliases must be dropped, and the three
    # abutting non-secure SRAM blocks merge into one 768K region.
    u575 = {"Flash_NS": (0x08000000, 0x200000), "Flash_S": (0x0C000000, 0x200000),
            "SRAM1_NS": (0x20000000, 0x30000), "SRAM1_S": (0x30000000, 0x30000),
            "SRAM2_NS": (0x20030000, 0x10000), "SRAM2_S": (0x30030000, 0x10000),
            "SRAM3_NS": (0x20040000, 0x80000), "SRAM3_S": (0x30040000, 0x80000),
            "SRAM4_NS": (0x28000000, 0x4000),  "SRAM4_S": (0x38000000, 0x4000)}
    assert derive_memory(u575) == (0x08000000, 2048 * 1024, 0x20000000, 768 * 1024, "SRAM1_NS")

    # Single-SRAM part: nothing to choose, nothing to merge.
    f411 = {"Flash": (0x08000000, 0x80000), "SRAM": (0x20000000, 0x20000)}
    assert derive_memory(f411) == (0x08000000, 512 * 1024, 0x20000000, 128 * 1024, "SRAM")

    # Core/FPU spellings seen across the packs, including the legacy "1" that
    # the STM32F4 pack still uses for "has an FPU".
    assert cpu_flags("Cortex-M7", "DP_FPU")[-2:] == ["-mfpu=fpv5-d16", "-mfloat-abi=hard"]
    assert cpu_flags("Cortex-M4", "1")[-2:] == ["-mfpu=fpv4-sp-d16", "-mfloat-abi=hard"]
    assert cpu_flags("Cortex-M33", "SP_FPU")[-2:] == ["-mfpu=fpv5-sp-d16", "-mfloat-abi=hard"]
    assert cpu_flags("Cortex-M0+", "NO_FPU") == ["-mcpu=cortex-m0plus", "-mthumb", "-mfloat-abi=soft"]
    assert cpu_flags("Cortex-M3", None) == ["-mcpu=cortex-m3", "-mthumb", "-mfloat-abi=soft"]
    try:
        cpu_flags("Cortex-A7", "DP_FPU")
    except SystemExit:
        pass
    else:
        raise AssertionError("unknown core should have been rejected")

    # Every tool needs an install hint on every host, or check_host raises
    # KeyError on the very machine that is missing that tool.
    for tool, _, hints in TOOLS:
        assert set(hints) == {"macos", "linux", "windows"}, tool
    assert set(TOOLCHAIN_GLOBS) == {"macos", "linux", "windows"}

    # Fetching an RTOS is pointless without the CMake file that builds it.
    for name in RTOS_REPOS:
        assert (ROOT / "cmake" / f"rtos-{name}.cmake").exists(), name
    assert set(NEEDED_TO_BUILD) <= {t[0] for t in TOOLS}

    # The settings.json rewrite collapses the commented examples into one live
    # setting, and running it again changes nothing.
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        s = Path(tmp) / "settings.json"
        s.write_text('{\n'
                     '  // "cortex-debug.armToolchainPath": "/one/bin",\n'
                     '  // "cortex-debug.armToolchainPath": "C:/two/bin",\n'
                     '  "cmake.configureOnOpen": false\n}\n')
        assert set_vscode_toolchain("/x/bin", s)
        out = s.read_text()
        assert out.count("cortex-debug.armToolchainPath") == 1, out
        assert '"cortex-debug.armToolchainPath": "/x/bin",' in out, out
        assert "cmake.configureOnOpen" in out, out
        assert set_vscode_toolchain("/x/bin", s) and s.read_text() == out
        # A path already written must be updated, not duplicated.
        assert set_vscode_toolchain("/y/bin", s)
        out = s.read_text()
        assert out.count("cortex-debug.armToolchainPath") == 1, out
        assert '"/y/bin"' in out, out
    print("self-test ok")


def parse_target_args(args):
    parser = argparse.ArgumentParser(prog=f"{PY} tools/setup.py target")
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--board")
    target.add_argument("--mcu")
    parser.add_argument("--ram-region", default="")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(args)


def main():
    args = sys.argv[1:]
    if args[:1] == ["--self-test"]:
        self_test()
    elif args[:1] == ["--list-boards"]:
        for b, v in BOARDS.items():
            print(f"  {b:16s} {v[0]:16s} console {v[1]} {v[2]}/{v[3]}")
    elif args[:1] == ["add"]:
        if len(args) != 2:
            die("usage: setup.py add <alias|url>")
        cmd_add(args[1])
    elif args[:1] == ["target"]:
        target = parse_target_args(args[1:])
        cmd_target(board=target.board or "", mcu=target.mcu or "",
                   ram_region=target.ram_region, dry=target.dry_run)
    elif args[:1] == ["doctor"]:
        if args[1:] not in ([], ["--fix"]):
            die("usage: setup.py doctor [--fix]")
        sys.exit(1 if check_host(fix=args[1:] == ["--fix"]) else 0)
    elif args[:1] == ["pins"]:
        mcu = (read_config().get("MCU") or [""])[0]
        if not mcu:
            die("set MCU in config.cmake first")
        cmd_pins(mcu, args[1] if len(args) > 1 else None)
    elif args in ([], ["--dry-run"]):
        cmd_init(dry=bool(args))
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
