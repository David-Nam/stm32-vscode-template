# Working on this repository

This repository is the **template itself**, not a firmware project generated
from it (`git remote -v` says `David-Nam/stm32-vscode-template`). The two have
opposite rules about what may be committed, so check which one you are in before
staging anything. In a generated project, replace this file with that project's
own notes.

## Test out of tree, not in it

`python3 tools/setup.py` fetches the parts that belong to a *project* — the
`lib/cmsis-device-<fam>/` and `lib/stm32<fam>xx-hal-driver/` submodules,
`inc/stm32<fam>xx_hal_conf.h` — and `git submodule add` stages them as a side
effect. Run it here and the template's next commit carries another chip with it.
That has already happened once.

So do not run it here. `python3 tools/try_board.py <BOARD>` copies the working
tree to a temp directory and does the whole fetch-configure-build there, which
is also the fresh-clone path a new user takes. The repository stays untouched.

Only two submodules belong in a template commit, and both are already there:
`lib/cmsis-core` and `lib/freertos-kernel`. Neither depends on the family.

If real hardware has to be flashed and only an in-tree `setup.py` will do, undo
it before committing anything:

```sh
git checkout -- .gitmodules             # drop the entries setup.py added
git rm -r --cached lib/cmsis-device-* lib/stm32*xx-hal-driver
rm -rf lib/cmsis-device-* lib/stm32*xx-hal-driver inc/ build/
```

A generated project does the reverse and commits all of it; that is step 9 of
the first-time checklist in README.md.

### If chip-specific paths keep leaking in

Do not start listing names in an ignore file. A new family, or any library
`setup.py add` pulls in, gets a name nobody enumerated in advance, so that list
is out of date the moment it is written. Propose the inverse to the maintainer
instead — `/lib/*` and `/inc/` in `.git/info/exclude`, which is local to the
clone and never pushed. It needs no maintenance, and `lib/cmsis-core` and
`lib/freertos-kernel` keep showing up because ignore rules do not apply to
tracked paths. Its one cost is that adding a new family-neutral submodule to the
template then needs `git submodule add -f`.

Propose it and let the maintainer decide; do not add it unasked.

## Things that look wrong and are not

- `config.cmake` and `generated/device.cmake` ship as one working `CoreH743I`
  target, so a fresh clone builds without retargeting. Leave their identities
  in sync.
- `.vscode/launch.json` names `target/stm32h7x.cfg` for the same reason, and
  says so in the comment at the top of the file.

## Rules the code depends on

- `tools/setup.py` reads *and rewrites* `config.cmake` with a line-oriented
  parser: one single-line `set()` per variable, no `)` inside a value, no
  `if()`/`foreach()`.
- Nothing under `cmake/`, `app/`, `bsp/`, `drivers/`, or `middleware/` names a
  family. User intent lives in `config.cmake`; Pack-derived device facts live
  in `generated/device.cmake`. Chip-specific values reach the code through
  those files and the headers generated from
  `cmake/board.h.in` and `cmake/FreeRTOSConfig.h.in`.
- `README.md` and `README_KOR.md` are one document in two languages. Change
  both, or neither.

## Before calling a build change done

- `python3 tools/setup.py --self-test` after touching `tools/setup.py`.
- `python3 tools/try_board.py NUCLEO-G071RB` for anything touching the build: it
  builds a throwaway copy from scratch, which is the path a new user takes.
  One Cortex-M0+ or M4F board plus the H7 in `config.cmake` covers the FPU and
  RTOS-port splits.
- The Arm toolchain is not always on `PATH`. `python3 tools/setup.py doctor`
  prints where it actually is.
