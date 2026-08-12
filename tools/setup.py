#!/usr/bin/env python3
"""Resolve the STM32 family from config.cmake and wire up the ST submodules.

  python3 tools/setup.py               fetch CMSIS + HAL/LL for the configured MCU
  python3 tools/setup.py --dry-run     resolve and print, touch nothing
  python3 tools/setup.py --list-boards
  python3 tools/setup.py pins [UART]   console pin/AF candidates for this MCU
  python3 tools/setup.py add <alias|url>   add an extra library submodule
"""

import re
import shlex
import shutil
import subprocess
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CFG = ROOT / "config.cmake"
LIB = ROOT / "lib"
INC = ROOT / "inc"
GH = "https://github.com/STMicroelectronics"

# CMSIS-Pack descriptor. This is where the per-device memory map lives: the
# CMSIS headers only carry base addresses, and FLASH_SIZE there is a runtime
# read of the flash size register, which the linker cannot use.
PACK_URL = "https://www.keil.com/pack/Keil.STM32{fam}xx_DFP.pdsc"

# board -> (mcu, uart, tx, rx, alternate function). Memory comes from the pack.
BOARDS = {
    "CoreH743I":     ("STM32H743IITx", "USART1", "PA9", "PA10", "7"),
    "NUCLEO-H743ZI": ("STM32H743ZITx", "USART3", "PD8", "PD9",  "7"),
    "NUCLEO-F411RE": ("STM32F411RETx", "USART2", "PA2", "PA3",  "7"),
    "NUCLEO-G071RB": ("STM32G071RBTx", "USART2", "PA2", "PA3",  "1"),
}

# Offline fallback only: flash size letter in the part number. Used when the
# pack cannot be reached. RAM is not encoded in the part number at all.
FLASH_KB = {"4": 16, "6": 32, "8": 64, "B": 128, "C": 256, "D": 384,
            "E": 512, "F": 768, "G": 1024, "H": 1536, "I": 2048}

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


def read_config():
    cfg = {}
    for m in re.finditer(set_re(), CFG.read_text(), re.M):
        cfg[m.group(2)] = [v for v in shlex.split(m.group(3)) if v]
    return cfg


def write_config(name, values):
    body = " ".join(f'"{v}"' for v in values) if values else '""'
    txt, n = re.subn(set_re(name),
                     lambda m: m.group(1) + body + ")" + m.group(4),
                     CFG.read_text(), count=1, flags=re.M)
    if not n:
        die(f"config.cmake has no single-line set({name} ...) line")
    CFG.write_text(txt)


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


def flash_size(mcu):
    """Flash size from the part number letter, e.g. STM32H743II -> 2048K.

    Offline fallback for when the CMSIS-Pack is unreachable. Less reliable than
    the pack: FLASH_END in the CMSIS headers is the device-line maximum, and
    this letter table does not cover H7RS or N6 naming.
    """
    m = re.match(r"^STM32[A-Z]+\d{2,3}[A-Z]([0-9A-Z])", mcu.upper())
    if not m or m.group(1) not in FLASH_KB:
        die(f"cannot derive flash size from MCU={mcu}; set FLASH_SIZE in config.cmake")
    return f"{FLASH_KB[m.group(1)]}K"


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


# --- submodules ------------------------------------------------------------

def add_submodule(url, path, depth=False, dry=False):
    rel = path.relative_to(ROOT)
    if path.exists() and any(path.iterdir()):
        print(f"  {rel} already present, skipping")
        return
    cmd = ["git", "submodule", "add"] + (["--depth", "1"] if depth else []) + \
          ["--", url, str(rel)]
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

def resolve_layout(cfg, mcu, fam, dry):
    """Fill the device layout in config.cmake from the CMSIS-Pack.

    Only empty values are written, so anything you set by hand stays put.
    """
    def put(name, val):
        if (cfg.get(name) or [""])[0]:
            return
        print(f"    set {name} = {val if isinstance(val, str) else ' '.join(val)}")
        if not dry:
            write_config(name, [val] if isinstance(val, str) else val)

    put("FAMILY", fam)
    keys = ("FLASH_ORIGIN", "FLASH_SIZE", "RAM_ORIGIN", "RAM_SIZE",
            "DEVICE_DEFINE", "CPU_FLAGS")
    if all((cfg.get(k) or [""])[0] for k in keys):
        print("  device layout already set in config.cmake, leaving it alone")
        return

    part = pack_part(mcu)
    print(f"  reading {part} from CMSIS-Pack")
    root = fetch_pack(fam)
    info = pack_device(root, part) if root is not None else None
    if not info:
        if root is not None:
            print(f"  warning: {part} not listed in the pack")
        fs = flash_size(mcu)
        print(f"  falling back to the part number: flash {fs}. Set RAM_ORIGIN, "
              f"RAM_SIZE, DEVICE_DEFINE and CPU_FLAGS in config.cmake by hand.")
        put("FLASH_ORIGIN", "0x08000000")
        put("FLASH_SIZE", fs)
        return

    for n, (s, sz) in sorted(info["mem"].items(), key=lambda kv: kv[1][0]):
        print(f"      {n:12s} 0x{s:08X}  {kb(sz):>7s}")
    region = (cfg.get("RAM_REGION") or [""])[0] or None
    f_o, f_s, r_o, r_s, chosen = derive_memory(info["mem"], region)
    print(f"    flash 0x{f_o:08X} {kb(f_s)}   ram {chosen} 0x{r_o:08X} {kb(r_s)}")
    print(f"    {info.get('core')}  fpu={info.get('fpu')}  define={info.get('define')}")

    if not info.get("define"):
        die(f"pack has no compile define for {part}; set DEVICE_DEFINE by hand")
    put("FLASH_ORIGIN", f"0x{f_o:08X}")
    put("FLASH_SIZE", kb(f_s))
    put("RAM_ORIGIN", f"0x{r_o:08X}")
    put("RAM_SIZE", kb(r_s))
    put("DEVICE_DEFINE", info["define"])
    put("CPU_FLAGS", cpu_flags(info.get("core"), info.get("fpu")))


def cmd_init(dry):
    cfg = read_config()
    board = (cfg.get("BOARD") or [""])[0]
    mcu = (cfg.get("MCU") or [""])[0]

    if board and not mcu:
        if board not in BOARDS:
            die(f"unknown BOARD={board!r}. Run --list-boards, or set MCU directly.")
        mcu, uart, tx, rx, af = BOARDS[board]
        print(f"board {board} -> {mcu}")
        for name, val in [("MCU", mcu), ("CONSOLE_UART", uart), ("CONSOLE_TX", tx),
                          ("CONSOLE_RX", rx), ("CONSOLE_AF", af)]:
            if not (cfg.get(name) or [""])[0] and not dry:
                write_config(name, [val])
                print(f"  set {name} = {val}")
    if not mcu:
        die("set MCU or BOARD in config.cmake")

    print(f"resolving family for {mcu}")
    fam, (dev_url, hal_url) = resolve_family(mcu)
    resolve_layout(cfg, mcu, fam, dry)

    print("submodules:")
    LIB.mkdir(exist_ok=True)
    add_submodule(f"{GH}/cmsis-core", LIB / "cmsis-core", dry=dry)
    add_submodule(dev_url, LIB / f"cmsis-device-{fam.lower()}", dry=dry)
    hal_dir = LIB / f"stm32{fam.lower()}xx-hal-driver"
    add_submodule(hal_url, hal_dir, dry=dry)

    if not dry:
        copy_hal_conf(hal_dir)
        n_hal = len(list(hal_dir.glob("Src/*_hal_*.c")))
        n_ll = len(list(hal_dir.glob("Src/*_ll_*.c")))
        print(f"done: family {fam}, {n_hal} HAL sources, {n_ll} LL sources")
        # Which UART reaches a USB-serial bridge is wiring, not a chip fact, so
        # say so here rather than letting the build fail on an empty pin later.
        cfg = read_config()
        missing = [k for k in ("CONSOLE_UART", "CONSOLE_TX", "CONSOLE_RX", "CONSOLE_AF")
                   if not (cfg.get(k) or [""])[0]]
        if missing:
            print(f"\nconsole not configured yet: {', '.join(missing)}")
            print(f"  the build will not run until these are set. To see what "
                  f"{mcu} offers:\n    python3 tools/setup.py pins")
    else:
        print(f"dry run done: family {fam}")


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

    rel = str(path.relative_to(ROOT))
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

    for mcu, want in [("STM32H743IITx", "2048K"), ("STM32F411RETx", "512K"),
                      ("STM32G071RBTx", "128K"), ("STM32C031C6Tx", "32K"),
                      ("STM32WB55RGVx", "1024K")]:
        assert flash_size(mcu) == want, (mcu, flash_size(mcu))

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
    print("self-test ok")


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
