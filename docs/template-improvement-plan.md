# STM32 CMake 템플릿 개선 계획

작성 기준: 2026-08-18

최종 갱신: 2026-09-01 (Stage 2 commit)

## 1. 목적

이 저장소를 가볍고 예측 가능한 `config.cmake` 기반 STM32 CMake 템플릿으로
정리한다. 목표는 세 가지다.

1. 타깃 설정은 프로젝트 시작 시 한 번이다. 바꿀 때는 이전 값을 고쳐 쓰지 않고
   파생물을 지운 뒤 다시 만든다.
2. 지원하지 않는 칩은 파일을 하나라도 바꾸기 전에 명확한 이유와 함께 거부한다.
3. H7 말고 다른 STM32도 명령 하나로 쓸 수 있다.

기능 수를 늘리는 것이 목표가 아니다. 이 템플릿은 단일 코어, 단일 실행 image에
고정하고, 새 칩을 만나면 옵션을 추가하는 대신 템플릿 자체를 고친다.

## 2. 범위

### 지원

- 단일 Cortex-M 코어, 내장 Flash, 단일 image
- STM32 HAL1
- 주 RAM 영역 하나 (H7처럼 여러 개면 `RAM_REGION`으로 선택)
- Arm GNU Toolchain + CMake + Ninja
- bare-metal 또는 FreeRTOS
- Cortex-Debug 기반 VS Code build/flash/debug
- macOS, Linux, Windows
- README.md와 README_KOR.md 두 언어

호스트 도구 점검, 라이브러리 추가 명령, 팀 온보딩 같은 프로젝트 운영은 지원 범위가
아니다. 그것을 아는 사람이 만들어야 한다.

### 배포 형태

이 저장소는 GitHub 템플릿으로 등록되어 "Use this template"으로 복제된다. 따라서
다음이 따라온다.

- 저장소의 모든 파일이 생성된 프로젝트로 복사된다. 템플릿에서만 쓰는 것은
  `template/` 한 폴더에 모아, 첫 프로젝트 체크리스트가 그 폴더만 지우게 한다.
  `setup.py`도 여기 들어간다. 첫 설정을 마치면 할 일이 없기 때문이다.
- 첫 설정이 만든 것(`generated/device.cmake`, `inc/`의 HAL 설정,
  `docs/libraries-<fam>.md`, `lib/`의 서브모듈)은 그 프로젝트의 것이 되고, 이후
  관리는 프로젝트가 한다.
- 템플릿 갱신은 생성된 프로젝트로 전파되지 않는다. 새 칩 지원을 추가해도 기존
  프로젝트는 직접 가져가야 한다.
- `.github/workflows`도 복사되어 남의 저장소에서 실행되므로, 워크플로는 템플릿
  저장소에서만 돌도록 조건을 건다.
- 템플릿은 설정이 비어 있는 상태로 출하한다. 첫 명령은 언제나
  `setup.py --board <name>` 또는 `--mcu <part>`이고, 한 번만 실행된다.

### 지원하지 않음

조용히 오동작하게 두지 않고 `setup.py`가 조기에 실패시킨다.

- 서로 다른 코어를 가진 멀티코어 MCU (STM32H745/H747/H755/H757, STM32WL54/WL55)
- 내장 Flash가 없거나 boot flash만 있는 MCU (STM32N657, STM32H7S3/H7S7)
- Cortex-A 계열 (STM32MP1/MP2)
- STM32F1 (HAL의 alternate function 모델이 달라 `board.h.in`이 컴파일되지 않는다)
- TrustZone secure/non-secure 분리
- HAL2 / STM32C5 계열
- bootloader + application 같은 복수 image

목록과 판정 근거는 [docs/unsupported-mcu.md](unsupported-mcu.md)에 두고 README
양 언어에서 링크한다. 새 제외 사례를 찾으면 그 문서에 추가한다.

보조 코어가 있어도 사용자가 image 하나만 build하면 멀티코어로 보지 않는다.
STM32WB55의 Cortex-M0+는 ST의 무선 스택 전용이고 Pack에도 processor가 하나만
있으므로 일반 단일 image 타깃이다.

### 전제하지 않는 것

과거 계획에 있었으나 실제 요구가 없어 삭제한 전제다. 다시 넣지 않는다.

- 인터넷이 없는 환경. clone과 `setup.py target`은 네트워크를 쓴다.
- 같은 template commit이 항상 같은 바이너리를 만든다는 보장. HAL을 upstream
  기본 branch에서 받으므로 성립하지 않으며, 성립시키려 lock 파일을 두지 않는다.
- 타깃을 자주 바꾼다는 전제. 보통 프로젝트 시작 시 한 번이다.
- 테스트의 병렬 실행.
- 악의적인 사용자 입력. `try_board.py`의 경로 안전장치는 과거의 실제 삭제 사고를
  막기 위한 것이지 공격을 가정한 것이 아니다.

## 3. 현재 기준선

- Stage 1, Stage 2 완료 및 commit (`a505a45`, `a67a11b`). 다음은 Stage 3.
- `docs/unsupported-mcu.md`는 작성했으나 아직 untracked. Stage 3에서 함께 commit한다.
- `python3 tools/setup.py --self-test` 통과
- fresh build 통과: CoreH743I, NUCLEO-F411RE, NUCLEO-G071RB
- 하드웨어 확인(2026-08-19): CoreH743I/STM32H743IITx에서 `--flash` 후 UART로
  FreeRTOS tick과 4,624 byte free heap 확인
- 알려진 미해결
  - `RAM_REGION`이 FLASH 영역 이름도 받아들인다
  - CMake `clean` 이후 `.bin`, `.hex`, `.map`이 남는다
  - `config.cmake`와 `generated/device.cmake`가 CoreH743I로 출하되어, 다른 보드
    사용자가 콘솔 핀과 HSE를 지우지 않으면 조용히 틀린 값을 쓴다
  - `.vscode/launch.json`에 `build/stm32-template.elf`가 하드코딩되어 있다
  - 템플릿에서만 쓰는 것들이 생성된 프로젝트로 복사된다. 유지보수 문서,
    `tools/`, `tests/`, `CLAUDE.md`가 여러 군데로 흩어져 있다
  - `tools/`와 `tests/`가 루트 이름을 선점해, 프로젝트가 자기 것을 둘 자리가 없다
  - `setup.py`가 여러 번 실행된다고 가정해 상태 판단 코드를 안고 있고,
    호스트 툴체인 탐색과 VSCode 설정 수정까지 한다 (191줄)
  - `setup.py add`는 개발 중에 쓰는 명령인데, 그때 `setup.py`는 이미 없다
  - 자동 CI가 없다

## 4. 원칙

1. **옵션을 늘리지 않는다.** 새 설정 변수는 실제로 걸린 문제를 푸는 경우에만
   추가한다. 구현체가 하나뿐인 확장 지점을 새로 만들지 않는다.
2. **새 칩은 코드가 아니라 값이다.** 패밀리 지원은 ST의 split 저장소 이름 규칙과
   CMSIS-Pack에서 파생된다. 패밀리 이름은 `cmake/`, `app/`, `bsp/`, `drivers/`,
   `middleware/` 어디에도 나오지 않는다.
3. **라이브러리는 통째로 쓴다.** 패밀리마다 ST 저장소 두 개
   (`cmsis-device-<fam>`, `stm32<fam>xx-hal-driver`)를 submodule로 붙이고, 그
   안에서 파일을 골라내지 않는다. `Src/*.c`는 `_template.c`만 빼고 전부
   컴파일하고 나머지는 `--gc-sections`가 버린다. 예외는 `inc/`로 복사하는
   `*_hal_conf.h` 하나이며, 이는 프로젝트가 수정해서 소유해야 하는 파일이다.
4. **디바이스 값의 소스는 CMSIS-Pack PDSC 하나다.** Flash/RAM 주소와 크기, 코어,
   FPU는 PDSC에서만 읽는다. STM32Cube 저장소의 예제 링커 스크립트는 IDE가 자동
   생성한 파일이고 ST 평가보드 품번만 담고 있으므로 소스로 쓰지 않는다. 조회는
   `setup.py target` 실행 시 1회이며 결과와 팩 버전은 `generated/device.cmake`에
   커밋된다.
5. **`setup.py`는 첫 설정만 하고 사라진다.** 칩이 바뀌면 다른 프로젝트이고,
   보드가 바뀌어도 다른 프로젝트다. 템플릿은 시작점이지 사용자 프로젝트의 관리
   도구가 아니다. 한 번만 실행된다고 정하면 "지금 어떤 상태인가"를 판단할 코드가
   전부 없어진다. 이미 설정된 상태를 만나면 거부한다.
6. **한 번 쓰고 버릴 도구가 만드는 것은 문서로 남긴다.** 도구는 지워져도 문서는
   프로젝트에 남는다. 라이브러리 목록이 그 예다.
7. **지원 밖은 파일을 바꾸기 전에 거부한다.**

## 5. 단계 요약

| 순서 | 우선순위 | 단계 | 끝나면 이렇게 된다 |
|---:|---|---|---|
| 1 | P0 | 시험 빌드 도구가 남의 폴더를 지우지 않게 | 보드 이름을 잘못 입력해도 실제 폴더가 안 지워짐 |
| 2 | P0 | 칩 바꾸기를 명령 한 번으로 | 칩을 바꿀 때 손으로 맞출 값이 없음 |
| 3 | P0 | 빈 상태로 출하, 한 번만 실행, 못 쓰는 칩 거부 | 첫 명령이 칩 선택이고, 다시 돌리면 거부되며, 못 쓰는 칩은 파일을 바꾸기 전에 막힘 |
| 4 | P1 | 안 쓰는 명령 제거, 라이브러리 목록 문서화 | `add`가 사라지고, 대신 그 패밀리의 ST 라이브러리 목록이 `docs/`에 남음 |
| 5 | P1 | 새 칩 추가 절차와 템플릿 전용 파일 격리 | 새 보드를 표 한 줄로 추가하고, 프로젝트는 `template/` 폴더 하나만 지우면 됨. `tools/`와 `tests/`가 비워짐 |
| 6 | P2 | 이름을 바꾸면 경로도 따라오게 | 이름을 바꿔도 손으로 맞출 곳이 없고 `clean`이 다 지움 |
| 7 | P2 | CI (선택) | PR마다 자동으로 테스트와 빌드가 돌아감 |

각 단계는 기존 단일 image build를 계속 통과시켜야 한다.

## 6. 단계별 구현 계획

각 Stage는 "무엇을 한 줄로 바꾸는가"부터 적는다. 자세한 항목은 그 아래에 둔다.

## Stage 1 — 시험 빌드 도구가 남의 폴더를 지우지 않게

우선순위: P0

**한 줄 요약**: 보드 이름을 잘못 입력해도 실제 폴더가 지워지지 않는다.

### What

- 지금은 사용자가 준 보드 이름으로 항상 같은 경로를 만들고, 만들기 전에 그
  경로를 통째로 지운다. 이 두 동작을 없앤다.
- 대신 실행할 때마다 `tempfile.mkdtemp()`로 새 임시 폴더를 만든다. 이름이 매번
  달라지므로 기존 폴더와 겹칠 일이 없다.
- 끝나면 자동으로 지우고, `--keep`을 준 경우에만 남긴다.
- `argparse`로 모르는 옵션과 이상한 보드 이름(`..`, `/` 같은 경로 문자)을
  실행 전에 거부한다.

### Why

`try_board.py NUCLEO-F411RE`를 치면 그 이름으로 폴더 경로를 만들고 **먼저
지웠다.** 이름을 잘못 주면 임시 폴더가 아니라 실제 폴더가 지워진다. 실제로 한 번
겪은 사고이고, 다른 어떤 개선보다 먼저 막아야 했다.

### Verification

```sh
python3 -m unittest tests.test_try_board
python3 tools/try_board.py NUCLEO-G071RB --keep
git status --short
```

보드 없이 확인 가능하다.

### Progress

- [x] Implemented
- [x] Self-verified
- [x] Reported
- [x] Chip-verified / N/A confirmed
- [x] Committed by user

## Stage 2 — 칩 바꾸기를 명령 한 번으로

우선순위: P0

**한 줄 요약**: 칩을 바꿀 때 손으로 맞춰야 할 값이 없어진다.

### What

- 설정을 두 파일로 나눈다.
  - `config.cmake` — **사람이 정하는 것**. 어느 보드를 쓸지, RTOS를 쓸지.
  - `generated/device.cmake` — **칩에서 따라오는 것**. Flash 주소와 크기, 코어
    종류, 컴파일 플래그. 손으로 고치는 파일이 아니다.
- 칩 변경은 명령 하나로 한다.

  ```sh
  python3 tools/setup.py target --board NUCLEO-F411RE
  python3 tools/setup.py target --mcu STM32G071RBTx
  ```

- 이 명령은 **검증이 다 끝난 뒤에 한꺼번에** 파일을 쓴다. 중간에 네트워크가
  끊기면 아무것도 바뀌지 않은 상태로 남는다.
- 보드와 MCU가 서로 안 맞으면 파일을 쓰기 전에 실패한다.
- 두 파일의 보드/MCU가 어긋나 있으면 CMake가 빌드를 시작하지 않는다.
- `try_board.py`가 라이브러리를 받기 전에 필요한 도구부터 확인하고, PATH에 없는
  Arm 툴체인을 찾아 하위 프로세스에 넘긴다.

### Why

전에는 `MCU`만 바꾸고 나머지를 비우지 않으면 이전 칩의 FAMILY, 컴파일 플래그,
메모리 주소가 그대로 남았다. **F411용이라고 생각하고 만든 펌웨어가 사실은 H7
설정으로 빌드되는데, 빌드는 성공한다.** 이걸 못 잡으면 나머지 개선은 의미가 없다.

### Verification

```sh
python3 -m unittest tests.test_target_config
python3 tools/setup.py --self-test
python3 tools/try_board.py NUCLEO-G071RB
python3 tools/try_board.py NUCLEO-F411RE
python3 tools/try_board.py CoreH743I
```

실제 확인(2026-08-19): CoreH743I/STM32H743IITx에 플래시한 뒤 UART로 64 MHz
system/PCLK1, 끊기지 않는 FreeRTOS tick, 4,624 byte로 안정된 free heap 확인.

### Progress

- [x] Implemented
- [x] Self-verified
- [x] Reported
- [x] Chip-verified / N/A confirmed
- [x] Committed by user

## Stage 3 — 빈 상태로 출하, 한 번만 실행, 못 쓰는 칩 거부

우선순위: P0

**한 줄 요약**: 새 프로젝트는 빈 설정으로 시작하고, `setup.py`는 첫 설정 한 번만
돌며, 지원하지 않는 칩은 파일을 바꾸기 전에 막힌다.

### What 1: 빈 상태로 출하

- `config.cmake`에서 **칩과 보드에 딸린 값을 비운 채로** 출하한다.
  `BOARD`, `MCU`, `CONSOLE_UART`/`TX`/`RX`/`AF`, `HSE_HZ`, `RAM_REGION`.
- 칩과 상관없는 값은 그대로 둔다. `RTOS`, `FREERTOS_HEAP_KB`, `CONSOLE_BAUD`,
  `ARM_TOOLCHAIN_BIN`.
- `generated/device.cmake`는 아예 커밋하지 않는다. 첫 설정이 만든다.
- 값이 비었을 때 나올 메시지는 이미 다 있으니 새로 만들지 않는다. CMake는
  `generated/device.cmake is missing`, `setup.py`는 `target is not configured`.

### What 2: 한 번만 실행

- 명령을 하나로 합친다. `target` 서브명령을 없앤다.

  ```sh
  python3 tools/setup.py --board NUCLEO-F411RE
  python3 tools/setup.py --mcu STM32F411RETx
  ```

  경로는 Stage 5에서 `template/setup.py`로 바뀐다.

- **이미 설정되어 있으면 거부한다.**

  ```text
  이미 STM32H743IITx로 설정되어 있습니다.
  다른 칩이나 보드는 새 프로젝트로 시작하세요.
  이 프로젝트에서 바꿔야 한다면 config.cmake와 generated/device.cmake를
  직접 고치세요.
  ```

- 한 번만 도니까 "지금 어떤 상태인가"를 판단하는 코드가 전부 필요 없어진다.
  다음을 지운다.
  - `cmd_init` — 인자 없는 실행. 설정 명령과 하는 일이 겹친다
  - `configured_target` — 설정 후 다시 읽을 일이 없다
  - `print_device_diff` — 비교할 이전 값이 없다
  - `write_target_files`의 롤백 — 실패하면 폴더를 지우고 다시 시작한다
- 설정 도중 꼬이면 폴더를 지우고 템플릿에서 다시 받는다. 그 시점에는 아직
  사용자 코드가 없다.
- 코드를 쓴 뒤에 보드를 바꿔야 하면 두 파일을 직접 고친다. 같은 칩이면
  `generated/device.cmake`는 손댈 필요가 없고, `config.cmake`의 `BOARD`,
  `CONSOLE_*`, `HSE_HZ`만 바꾸면 된다.

### What 3: 못 쓰는 칩은 미리 거부

- CMSIS-Pack에 프로세서가 둘 이상 적혀 있으면 멀티코어로 보고 바로 실패한다.
  코어를 임의로 고르지 않는다.
- 내장 Flash가 없으면 실패한다. Flash가 있어도 부트로더 크기밖에 안 되면
  (STM32H7S3의 64 KB) 같은 이유로 실패한다.
- 아는 코어 목록에 없으면 Cortex-A까지 포함해 이유를 말하고 실패한다.
- `RAM_REGION`에는 RAM 이름만 받는다. 지금은 FLASH 이름도 통과한다.
- 품번 끝의 등급 문자를 감안해 Pack의 표기와 맞춰본다.
  예: `STM32U575ZIT6Q`, `STM32C031C(4-6)Tx`.
- **모든 거부는 파일을 하나도 바꾸기 전에** 일어나고, 이유를 한 문장으로 말하며
  `docs/unsupported-mcu.md`를 가리킨다.

### 예상 변경 파일

- `tools/setup.py`
- `config.cmake`
- `generated/device.cmake` (템플릿에서 삭제)
- `tests/fixtures/pdsc/*`
- `tests/test_pack_parser.py`
- `docs/unsupported-mcu.md`
- `README.md`
- `README_KOR.md`

### Why

**빈 출하**: CoreH743I로 출하하는 이유는 "받자마자 빌드된다"였는데 사실이 아니다.
H7 라이브러리가 템플릿에 없어 어차피 `setup.py`를 돌려야 한다. 이득은 없고 위험만
남는다. `PH13`/`PH14`, `AF8`, `HSE_HZ 8000000`은 CoreH743I의 배선값이라, 다른 보드
사용자가 지우지 않으면 **빌드는 성공하고 UART만 죽는다.**

**한 번만 실행**: 칩이 바뀌면 다른 프로젝트이고, 보드가 바뀌어도 다른
프로젝트다. 템플릿은 시작점이지 사용자 프로젝트의 관리 도구가 아니다. 여러 번
실행된다고 가정하는 순간 이전 상태를 지울지, 사용자 수정을 백업할지, 실패 시
어디까지 되돌릴지를 전부 정해야 한다. 한 번만 돈다고 정하면 그 전부가 없어진다.

**거부**: 실패하는 자리가 문제다. H745는 프로세서 여러 개 중 마지막 M4로 설정을
덮어쓰고, N657은 링커 스크립트를 만드는 도중에야 실패한다. 둘 다 저장소를 일부
바꿔놓은 뒤에 깨진다.

### Verification

```sh
python3 -m unittest tests.test_pack_parser
python3 tools/setup.py --self-test
python3 tools/try_board.py NUCLEO-G071RB
python3 tools/try_board.py CoreH743I
```

테스트용 Pack 표본:

- 성공해야 하는 것: H743, F411, G071, U575
- 실패해야 하는 것: H745(멀티코어), WL55(멀티코어), N657(Flash 없음),
  H7S3(부트 Flash만)
- 실패해야 하는 것: `RAM_REGION`에 FLASH 이름을 넣은 경우
- 같게 해석되어야 하는 것: `STM32U575ZIT6`, `STM32U575ZIT6Q`

확인할 항목:

- 빈 설정에서 `cmake --preset default`가 알아들을 수 있는 메시지로 실패한다
- 빈 설정에서 첫 실행이 성공하고, 같은 명령을 다시 돌리면 거부한다
- 실패 케이스가 라이브러리를 받기 전, 파일을 쓰기 전에 실패하고 작업 폴더가 그대로다

보드 없이 확인 가능하다.

### Progress

- [ ] Implemented
- [ ] Self-verified
- [ ] Reported
- [ ] Chip-verified / N/A confirmed
- [ ] Committed by user

## Stage 4 — 안 쓰는 명령을 지우고, 라이브러리 목록을 문서로 남기기

우선순위: P1

**한 줄 요약**: `add` 명령을 없애는 대신, 첫 설정 때 그 패밀리가 쓸 수 있는 ST
라이브러리 목록을 `docs/`에 만들어 둔다.

### What

- `setup.py add`를 통째로 지운다. `add cube`도 함께 사라진다.
- 첫 설정 때 `docs/libraries-<fam>.md`를 만든다.
  - 출처는 `STM32Cube<FAM>` 저장소의 `.gitmodules` 파일 하나다. F4 기준 9 KB에
    항목 56개가 들어 있다. 저장소 본체(790 MB)는 받지 않는다.
  - 경로 앞부분으로 세 그룹으로 나눈다. F4 기준 미들웨어 7개, 보드 BSP 13개,
    부품 드라이버 34개. 이미 받은 CMSIS와 HAL 두 개는 뺀다.
  - 문서 첫머리에 추가 방법을 적는다.

    ```sh
    git submodule add <URL> lib/<이름>
    # config.cmake의 EXTRA_LIB_DIRS에 "lib/<이름>" 추가
    ```

  - `EXTRA_LIB_DIRS`가 하위 `*.c`를 전부 컴파일하고 `Inc/`나 `Include/`를 include
    경로에 붙인다는 것, 예제가 섞인 저장소를 통째로 넣으면 중복 심볼이 난다는
    것을 한 줄씩 적는다.
  - 생성 날짜와 출처 URL을 적어 이 목록이 스냅샷임을 밝힌다.
  - `.gitmodules`를 못 받으면 문서를 만들지 않고 넘어간다. 빌드에 필요한 것이
    아니므로 첫 설정을 실패시키지 않는다. 대신 출처 URL을 한 줄 출력한다.
- `.gitignore`에서 `*.ioc.bak`, `.mxproject`를 지운다. `/Debug/`, `/Release/`가
  필요하면 최상위에만 적용한다.
- 원칙 3(라이브러리는 통째로 쓴다)을 README와 `cmake/stm32.cmake` 주석에 적는다.
- `EXTRA_LIB_DIRS`가 하위 `.c`를 전부 모으는 방식은 **그대로 둔다.** manifest나
  CMake target을 요구하도록 바꾸면 설정이 늘고 얻는 것이 없다.

### 예상 변경 파일

- `tools/setup.py`
- `cmake/stm32.cmake`
- `config.cmake`
- `.gitignore`
- `docs/libraries-<fam>.md` (생성물)
- `README.md`
- `README_KOR.md`

### Why

`add`는 개발 중에 쓰는 명령인데, 그때 `setup.py`는 이미 지워지고 없다. 남겨도 못
쓴다. 반대로 문서는 프로젝트에 남는다. 그게 원래 문제였다.

그리고 라이브러리를 붙이는 일 자체는 `git submodule add` 한 줄과 `config.cmake`
한 줄이다. 자동화할 만한 일이 아니다. 정말 없어서 곤란한 것은 **어떤 라이브러리가
있고 URL이 무엇인지**이고, 그건 문서가 답한다.

`add cube`는 특히 나쁘다. 790 MB짜리 껍데기 저장소를 받아 하위 `.c`를 전부
컴파일하는데, 정작 사람이 원하는 목록은 그 안의 9 KB 파일 하나다.

### Verification

```sh
python3 tools/setup.py --help
python3 tools/try_board.py NUCLEO-G071RB
rg -n "add cube|mxproject" .
```

확인할 항목:

- `add`가 명령 목록에 없다
- 첫 설정 후 `docs/libraries-g0.md`가 생기고, 표의 URL이 실제로 열린다
- `.gitmodules`를 못 받는 상황을 만들어도 첫 설정이 성공한다
- 지우기로 한 ignore 항목이 남아 있지 않다
- 대표 보드 빌드가 그대로 통과한다

보드 없이 확인 가능하다.

### Progress

- [ ] Implemented
- [ ] Self-verified
- [ ] Reported
- [ ] Chip-verified / N/A confirmed
- [ ] Committed by user

## Stage 5 — 새 칩 추가 절차와 템플릿 전용 파일 격리

우선순위: P1

**한 줄 요약**: 새 보드 추가 방법을 문서 한 곳에 모으고, 템플릿에서만 쓰는 것을
`template/` 한 폴더로 격리해 프로젝트가 폴더 하나만 지우면 되게 한다.

### What 1: 새 보드 추가 절차

- README 양 언어에 절차를 둔다.
  1. `setup.py pins`로 콘솔 UART와 핀, AF 번호 확인
  2. `setup.py`의 `BOARDS`에 한 줄 추가
  3. `try_board.py <BOARD>`로 빌드 확인
  4. 보드가 있으면 `--flash`로 UART 출력 확인
- 검증된 보드 표를 둔다. 실제로 확인한 것만 적고 "될 것 같은 것" 등급은 두지
  않는다.
- 지원하지 않는 조합이 어떤 메시지로 실패하는지 한 문단 적고
  `docs/unsupported-mcu.md`를 링크한다. 링크는 양 언어에 둔다.
- 새 제외 사례를 찾으면 `docs/unsupported-mcu.md`에 근거와 함께 추가한다.
- Quick Start를 첫 설정 명령 하나 중심으로 줄여 첫 빌드까지 5분 안에 끝나게 한다.
- "수정할 유일한 파일"이라는 표현을 "하드웨어 빌드 설정의 기준 파일"로 고친다.
- README의 `CoreH743I`를 출하 상태가 아니라 예시로 다시 쓴다. 양 언어 모두.

### What 2: 템플릿 전용 파일 격리

템플릿에서만 쓰는 것을 한 폴더로 모은다.

```text
template/
├── README.md            유지보수 규칙 (지금 CLAUDE.md 내용)
├── improvement-plan.md  이 문서
├── setup.py             tools/에서 이동. 첫 설정 한 번만 쓴다
├── try_board.py         tools/에서 이동
└── tests/               최상위 tests/에서 이동

docs/unsupported-mcu.md  프로젝트에서도 보므로 남김
docs/libraries-<fam>.md  첫 설정이 만든 것. 프로젝트가 가진다
```

`tools/` 폴더가 사라진다. `setup.py`는 첫 설정을 마치면 할 일이 없으므로
`template/`과 함께 지워진다.

- 첫 프로젝트 체크리스트의 삭제 안내를 한 줄로 줄인다: `template/` 폴더 삭제.
- 최상위 `tests/`와 `tools/`를 비워, 프로젝트가 두 이름을 자기 것으로 쓸 수 있게
  한다. 둘 다 펌웨어 프로젝트가 흔히 만드는 폴더 이름이다.
- **`doctor`를 통째로 지운다** (191줄). 툴체인 탐색, newlib 검사,
  `.vscode/settings.json` 자동 수정이 전부 사라진다.
  - 빌드는 `doctor` 없이도 명확히 실패한다. `cmake/arm-none-eabi.cmake`가
    `find_program(... REQUIRED)`로 툴체인을 찾고, 없으면 configure가 멈춘다.
  - Windows 설치 경로에 괄호가 있어 `config.cmake`에 넣을 수 없다는 주의사항은
    이미 `config.cmake` 주석에 적혀 있다.
  - 팀원 온보딩 점검은 그 팀의 OS와 CI를 아는 프로젝트의 몫이다. 템플릿은 모른다.
  - `.vscode/settings.json`의 `cortex-debug.armToolchainPath`는 주석 처리된
    예시로 남고, 필요한 사람이 주석을 푼다.
  - `try_board.py`가 쓰던 `find_toolchain()`을 자기 안으로 옮긴다. 25줄쯤이고
    `template/` 안이라 프로젝트에는 영향이 없다.
  - `self_test`에서 `TOOLS`, `TOOLCHAIN_GLOBS`, `set_vscode_toolchain` 관련
    검사를 지운다.
- `setup.py`와 `try_board.py`는 같은 폴더에 남으므로 import 방식은 그대로 둔다.
- `template/__init__.py`와 `template/tests/__init__.py`를 두어
  `python3 -m unittest template.tests.<이름>` 형태를 유지한다.
- Stage 1에서 3까지 만든 테스트 파일도 함께 옮기고, 앞 Stage의 검증 명령 경로를
  이 문서와 README에서 갱신한다.
- `CLAUDE.md`는 커밋하지 않는다. `.gitignore`에 넣고 내용은 `template/README.md`로
  옮긴다. 유지자는 clone 후 한 줄로 되살린다.

  ```sh
  echo "@template/README.md" > CLAUDE.md
  ```

  이러면 생성된 프로젝트에는 `CLAUDE.md`가 아예 없다. 그 프로젝트 담당자가 자기
  내용으로 처음부터 쓰면 된다.
- `.github/workflows`는 위치가 고정이라 옮길 수 없다. Stage 7의 저장소 조건이
  그 역할을 대신한다.

### 예상 변경 파일

- `README.md`
- `README_KOR.md`
- `.gitignore`
- `CLAUDE.md` (커밋 해제, 내용은 `template/README.md`로 이동)
- `template/*` (`tools/*`, `tests/*`, 이 문서를 이동)
- `docs/unsupported-mcu.md`
- `config.cmake` (주석)

### Why

다른 STM32를 쉽게 쓸 수 있어야 한다는 것이 이 템플릿의 목적인데, 지금은 그 절차가
문서 여러 곳에 흩어져 있고 Quick Start와 상세 절차가 서로 다르다.

템플릿 전용 파일도 같은 문제다. 지울 것이 여러 군데로 흩어져 있으면 체크리스트가
그만큼 길어지고, **긴 체크리스트는 지켜지지 않는다.** 한 폴더면 한 줄이다.
`tests/`와 `tools/`는 특히 급하다. 펌웨어 프로젝트가 흔히 만드는 두 이름을
템플릿이 차지하고 있기 때문이다.

`doctor`는 다른 이유로 지운다. 이 템플릿은 그 프로젝트의 팀도, OS도, CI도
모른다. 호스트 점검 도구는 그것을 아는 사람이 만들어야 한다.

### Verification

```sh
python3 template/setup.py --list-boards
python3 -m unittest discover -s template/tests -t .
python3 template/try_board.py NUCLEO-G071RB
```

확인할 항목:

- 문서 절차만 따라 해서 지원 보드 빌드가 된다
- 표에 적힌 보드와 `BOARDS`의 내용이 같다
- 영/한 문서의 명령과 링크가 서로 같다 (사람이 확인)
- 폴더를 옮긴 뒤에도 모든 테스트와 `try_board.py`가 그대로 통과한다
- 첫 설정을 마치고 `template/`을 지운 사본에서 configure와 빌드가 성공한다
- 최상위에 `tools/`와 `tests/`가 없다
- 문서에 옛 경로(`tools/setup.py`, `tools/try_board.py`)가 남아 있지 않다

보드가 있으면 `--flash`로 UART 출력까지 확인한다. 없으면 생략한다.

### Progress

- [ ] Implemented
- [ ] Self-verified
- [ ] Reported
- [ ] Chip-verified / N/A confirmed
- [ ] Committed by user

## Stage 6 — 이름을 바꾸면 경로도 따라오게

우선순위: P2

**한 줄 요약**: 프로젝트 이름을 바꿔도 손으로 맞출 곳이 없고, `clean`이 예전
산출물을 남기지 않는다.

### What

- `.vscode/launch.json`에 박혀 있는 `build/stm32-template.elf`를 없앤다.
- `PROJECT_NAME`과 출력 파일 이름을 한 곳에서만 정한다.
- `.bin`, `.hex`, `.map`을 CMake에 산출물로 등록해 `clean`이 지우게 한다.
- custom command에 `VERBATIM`을 붙인다.
- 여기서 설정을 늘리지 않는다. `CONSOLE=none`이나 TX/RX AF 분리는 넣지 않는다.

### 예상 변경 파일

- `CMakeLists.txt`
- `cmake/stm32.cmake`
- `.vscode/launch.json`
- `.vscode/tasks.json`

### Why

지금은 프로젝트 이름을 바꾸면 `CMakeLists.txt`와 `launch.json` 두 군데를 손으로
맞춰야 한다. 하나를 잊으면 디버거가 예전 이름의 파일을 찾는다. 그리고 `clean`
뒤에도 `.bin`이 남아 있어서, 빌드에 실패한 줄 모르고 **예전 파일을 플래시할 수
있다.**

### Verification

```sh
cmake --preset default
cmake --build --preset default
cmake --build --preset default --target clean
ls build
```

확인할 항목:

- `clean` 뒤에 `.elf`, `.bin`, `.hex`, `.map`이 모두 없다
- 프로젝트 이름을 바꾸면 빌드/플래시/디버그 경로가 함께 바뀐다

보드가 있으면 플래시와 디버거 진입까지 확인한다.

### Progress

- [ ] Implemented
- [ ] Self-verified
- [ ] Reported
- [ ] Chip-verified / N/A confirmed
- [ ] Committed by user

## Stage 7 — CI (선택)

우선순위: P2

**한 줄 요약**: PR마다 자동으로 테스트와 빌드를 돌린다. 넣지 않아도 나머지
단계는 성립한다.

큰 변경을 여러 번 하는 동안 대표 보드 빌드가 계속 통과하는지 자동으로 보고 싶을
때만 넣는다.

### What

- workflow 파일 하나에 job 하나만 둔다. Linux에서
  `python3 -m unittest discover -s template/tests -t .`,
  `python3 template/setup.py --self-test`,
  `python3 template/try_board.py NUCLEO-G071RB`.
- Windows job은 넣지 않는다. `doctor`가 사라지면서 Windows에서만 도는 코드가 `PY`
  변수와 `tasks.json`의 명령 오버라이드 정도로 줄었다. `--self-test`만 돌리자고
  job을 하나 더 둘 값이 없다. Windows에서 깨지는 것이 실제로 나오면 그때 넣는다.
- 이 workflow는 **템플릿 저장소에서만 돌아야 한다.** 생성된 프로젝트로 복사되어도
  조용히 넘어가도록 job에 조건을 건다.

  ```yaml
  if: github.repository == 'David-Nam/stm32-vscode-template'
  ```

  이게 없으면 G071을 쓰지도 않는 남의 프로젝트에서 서브모듈을 받고 빌드하다
  실패한다.
- 그 이상(format/static check, 여러 보드 matrix, 예약 실행)은 넣지 않는다.

### 예상 변경 파일

- `.github/workflows/ci.yml`

### Verification

- 새로 clone한 상태에서 job이 통과한다
- 일부러 넣은 회귀가 job을 실패시킨다
- 저장소 이름이 다르면 job이 실행되지 않는다

보드 없이 확인 가능하다. CI는 하드웨어 확인을 대체하지 않는다.

### Progress

- [ ] Implemented
- [ ] Self-verified
- [ ] Reported
- [ ] Chip-verified / N/A confirmed
- [ ] Committed by user

## 7. 하지 않기로 한 것

다시 논의하지 않기 위해 이유와 함께 남긴다. 필요해지는 시점에 그때의 요구로
다시 판단한다.

- **서로 다른 코어를 가진 멀티코어 지원**: H745/H747/H755/H757, WL54/WL55.
  image target 구조, core별 build context, shared memory와 IPC 계약이 전부
  따라온다. 근거는 `docs/unsupported-mcu.md`에 있다.
- **bootloader + application 복수 image, combined HEX**: 필요해진 적이 없다.
- **내장 Flash가 없거나 boot flash만 있는 MCU, Cortex-A 계열, STM32F1,
  TrustZone, HAL2/STM32C5**: `docs/unsupported-mcu.md` 참고.
- **dependency lock과 `--frozen`**: 인터넷 없는 환경을 전제하지 않는다.
  빌드는 이미 네트워크 없이 되고, 칩을 바꿀 때는 어차피 HAL을 받아야 한다.
- **HAL 모듈 선별 컴파일**: 원칙 3과 충돌한다. `--gc-sections`가 이미 버린다.
- **`CONSOLE=none`, `CONSOLE_TX_AF`/`CONSOLE_RX_AF` 분리**: 옵션만 늘어난다.
- **STM32Cube 통짜 저장소 사용**: H7 기준 790 MB이고 하위 submodule 51개의 껍데기라
  정작 필요한 두 디렉터리가 비어서 온다. split 저장소 두 개로 같은 파일을 13 MB에
  얻는다.
- **예제 링커 스크립트를 메모리 값의 소스로 사용**: IDE 생성물이고 ST
  평가보드 품번만 있다. STM32CubeF4의 `.ld` 1,171개가 품번 기준으로는 30종뿐이다.
- **호스트 도구 점검(`doctor`)**: 빌드는 `find_program(... REQUIRED)`로 이미
  명확히 실패하고, Windows 경로 주의사항은 `config.cmake` 주석에 있다. 팀 온보딩
  점검은 그 팀의 OS와 CI를 아는 프로젝트가 만든다.
- **`setup.py add` 같은 라이브러리 관리 명령**: 개발 중에 쓰는 명령인데 그때
  `setup.py`는 이미 없다. `git submodule add` 한 줄과 `config.cmake` 한 줄이면
  되고, 필요한 것은 목록이라 문서로 남긴다.
- **칩이나 보드 재설정 명령**: 칩이 바뀌면 다른 프로젝트이고 보드가 바뀌어도 다른
  프로젝트다. 설정 도중 꼬이면 폴더를 지우고 다시 받는다. 코드를 쓴 뒤라면 두
  파일을 직접 고친다.
- **문서 영/한 일치를 CI로 검사**: 사람이 맞춘다.

## 8. 단계 운영 규칙

1. 현재 Stage 범위만 구현한다.
2. 문서에 정의한 self-verification을 실행한다.
3. 변경 파일, 실제 검증 명령과 출력, 남은 hardware 검증을 보고한다.
4. hardware 검증이 있으면 사용자가 실행한 결과를 확인한다.
5. 사용자가 승인한 뒤 사용자가 직접 stage/commit한다.
6. 이 문서의 Progress checkbox를 갱신한다.
7. 사용자가 다음 Stage 진행을 명시적으로 요청할 때만 넘어간다.

한 Stage의 검증이 실패하면 다음으로 넘어가지 않는다. 여러 Stage를 한 commit으로
합치지 않는다.

모든 Stage가 끝나면 이 문서를 삭제한다. 단계별 What/Why/Verification은 git
히스토리에 남으므로 따로 보관할 이유가 없다. 다만 §7 "하지 않기로 한 것"은 계획이
끝난 뒤에도 유효하므로 `template/README.md`로 옮긴 다음 삭제한다. 그 목록이
사라지면 듀얼코어나 STM32Cube 통짜 같은 논의가 근거 없이 다시 시작된다.

## 9. 전체 완료 조건

- `setup.py`가 첫 설정 한 번만 돌고, 다시 실행하면 거부한다.
- 지원 밖 MCU는 저장소를 바꾸기 전에 이유와 함께 실패하고, 그 목록이
  `docs/unsupported-mcu.md`에 근거와 함께 있다.
- 쓰지 않는 명령과 ignore 규칙이 남지 않는다.
- 템플릿이 빈 설정으로 출하되고, 첫 명령이 칩 선택이다.
- 첫 설정이 그 패밀리의 ST 라이브러리 목록을 `docs/`에 남긴다.
- 템플릿에서만 쓰는 것이 `template/` 한 폴더에 모여 있고, 체크리스트의 삭제
  안내가 한 줄이다. `CLAUDE.md`는 아예 복사되지 않는다.
- 루트에 `tools/`와 `tests/`가 없어 프로젝트가 두 이름을 자기 것으로 쓸 수 있다.
- CI 워크플로가 생성된 프로젝트에서 실행되지 않는다.
- 새 보드 추가 절차가 문서 한 곳에 있고, 그대로 따라 build가 된다.
- 프로젝트 이름을 바꾸면 build/flash/debug 경로가 함께 바뀌고, `clean`이 모든
  산출물을 지운다.
- README 양 언어의 지원 범위가 실제 `setup.py`/build 동작과 일치한다.
