# MCUs this template does not support

This template builds one image for one Cortex-M core out of internal flash.
The parts below break one of those assumptions. Each entry says how the part is
detected and what `tools/setup.py` does about it.

This is a template, not a product: if you need one of these, change the
template rather than adding an option to it. Add the part here when you do.

## Two different cores, both yours to program

| Part | Cores | Detected by |
|---|---|---|
| STM32H745, H747, H755, H757 | Cortex-M7 + Cortex-M4 | two `<processor>` records in the CMSIS-Pack `<subFamily>` |
| STM32WL54, WL55 | Cortex-M4 + Cortex-M0+ | same |

Each core needs its own startup file, vector table, compiler flags, linker
layout and flash slot, plus a boot order and a shared-memory contract between
them. That is a different build model, not a setting.

`setup.py target` refuses these before touching any file.

**Not in this group:** a part whose second core runs vendor firmware you never
build. STM32WB55 pairs a Cortex-M4 with a Cortex-M0+ that runs ST's wireless
stack, and its Pack record lists one processor, so it is an ordinary
single-image target here.

## No usable internal flash

| Part | Flash in the Pack | Note |
|---|---|---|
| STM32N657 | none | RAM regions only; needs an external loader to boot |
| STM32H7S3, H7S7 | 64 KB at 0x08000000 | boot flash only; the application lives in external memory |

The linker script places `.text` in internal flash. N657 has none at all.
H7S3 has enough to hold a first-stage loader and nothing else, so it passes a
"has flash" check and still cannot hold an application. Both need an external
memory controller brought up before first instruction fetch, and that setup is
board-specific.

## A different core architecture

| Part | Core |
|---|---|
| STM32MP1, MP2 | Cortex-A7 / Cortex-A35 (plus a Cortex-M coprocessor) |

The device repositories exist, so family resolution succeeds, but there is no
`-mcpu` entry for these cores and the boot path is a Linux one.

## A different alternate-function model

| Part | Why |
|---|---|
| STM32F1 | its HAL has no `GPIO_InitTypeDef.Alternate` field and no `GPIO_AF<n>_<peripheral>` macros |

F1 remaps peripherals with `__HAL_AFIO_REMAP_*` instead of per-pin alternate
function numbers. `cmake/board.h.in` emits `GPIO_AF@CONSOLE_AF@_@CONSOLE_UART@`,
which does not exist on F1, so the console does not compile. Supporting F1
means a second console model in `board.h.in`.

## Split secure / non-secure memory maps

Not excluded, but worth knowing: on TrustZone parts the Pack can list every
region twice, once as `_NS` and once as `_S` (STM32N657 lists 32 regions this
way). Where that happens, `RAM_REGION` has two names for the same memory and
the choice is ambiguous. STM32U575 does not split this way and works today.

## Verified as working

STM32H743, STM32F411, STM32G071, STM32U575. See the board table in the README.
