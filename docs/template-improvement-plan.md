# STM32 CMake 템플릿 개선 계획

작성 기준: 2026-08-18

최종 갱신: 2026-08-19

## 1. 목적

이 문서는 CubeMX 기반 프로젝트를 별도의 형제 템플릿으로 분리한다는 전제에서,
현재 저장소를 가볍고 재현 가능한 `config.cmake` 기반 STM32 CMake 템플릿으로
정리하기 위한 구현 순서와 검증 기준을 정의한다.

이 계획의 핵심 목표는 기능 수를 무조건 늘리는 것이 아니다. 기존 단일 image의
안전성과 재현성을 먼저 보장한 뒤, 같은 구조를 여러 실행 image로 일반화한다.
다음 다섯 가지를 목표로 한다.

1. 타깃을 변경해도 이전 MCU의 설정이 섞이지 않는다.
2. MCU의 processor topology를 임의로 단순화하지 않고, 지원하지 않는 조합은 파일을
   변경하기 전에 명확하게 거부한다.
3. 같은 입력과 dependency lock은 같은 firmware를 만든다.
4. build, flash, debug 경로가 같은 target과 artifact를 사용한다.
5. single-core, bootloader/application, STM32H7 dual-core를 별도 템플릿이 아니라
   동일한 image-target build model로 표현한다.

## 2. 제품 범위

### 현재 보장 범위

- `config.cmake`를 사용자 설정의 시작점으로 사용
- 단일 Cortex-M 코어
- 내장 Flash
- non-secure 단일 image
- STM32 HAL1
- 하나의 주 RAM 영역
- Arm GNU Toolchain + CMake + Ninja
- bare-metal 또는 FreeRTOS
- Cortex-Debug 기반 VS Code build/flash/debug

### 이 계획에서 추가할 범위

- 하나의 project에서 하나 이상의 독립 실행 image 정의
- 기존 single-core application을 image 한 개로 표현
- 같은 코어의 bootloader + application multi-image build
- STM32H745/H747/H755/H757 계열의 Cortex-M7 + Cortex-M4 AMP build
- image별 startup, compile option, define, linker layout, artifact와 debug 정보
- image별 build/flash/debug와 project 전체 `build-all`/`flash-all`
- 여러 image를 하나의 배포용 HEX로 결합하는 선택 기능
- 공통 source와 core 간 shared-memory 영역의 명시적 선언 및 충돌 검사

여기서 `image`는 파일 확장자나 배포 파일 개수가 아니라 **독립적으로 컴파일되고
링크되는 실행 단위**를 뜻한다. 여러 image를 최종 HEX 하나로 합쳐도 build
관점에서는 복수 image다.

### 현재 계획에서 보류하거나 명시적으로 거부할 범위

- flashless MCU
- STM32C5/HAL2/CubeMX2 계열
- 별도 family adapter 없이는 공통 GPIO/UART 모델로 표현할 수 없는 MCU
- `.ioc` 해석, CubeMX code generation, 공식 ST VS Code extension 의존

TrustZone secure/non-secure pair는 multi-image 기반을 재사용할 수 있지만 SAU/IDAU,
secure gateway, secure boot와 debugger 연동이 추가로 필요하므로 이번 안정화 범위
이후의 별도 adapter 단계로 보류한다. flashless MCU는 외부 memory controller 초기화와
stage-1 loader가 board에 종속되므로 범용 MCU template의 자동 파생 대상으로 삼지 않는다.

현재 구현 단계에서 아직 활성화되지 않은 target과 명시적 비지원 범위는 조용히
오동작하게 두지 않고 `setup.py`에서 capability와 필요한 다음 단계를 설명하며 조기에
실패시키는 것을 원칙으로 한다.

## 3. 확인된 멀티코어와 image 모델

### Dual-core 자체는 image 개수를 결정하지 않는다

dual-core라는 사실만으로 image가 반드시 두 개가 되는 것은 아니다. 판단 기준은
코어 수가 아니라 processor topology와 실행 model이다.

- **동형 SMP**: 동일한 코어가 같은 주소 공간과 하나의 OS/runtime을 공유하면
  application ELF 하나를 두 코어가 실행할 수 있다. ESP32의 ESP-IDF FreeRTOS가 이
  방식이며 task affinity로 실행 코어를 지정한다.
- **이종 AMP**: 코어별 startup, vector table, compile option, linker layout과 boot
  address가 다르면 코어마다 독립 실행 image가 필요하다. STM32H745/H747의
  Cortex-M7 + Cortex-M4가 대표적이다.
- **보조 코어 미사용**: 두 번째 코어를 reset/stop 상태로 유지하면 사용자 image는
  하나일 수 있다.
- **제조사 관리 보조 코어**: 사용자가 application image 하나만 build하더라도 장치에는
  별도의 vendor firmware가 존재할 수 있다.

STM32H7 AMP에서 CM7과 CM4 image는 별도로 링크하지만 한 project와 한 repository에서
관리한다. flash 단계에서 두 HEX를 하나의 combined HEX로 합칠 수도 있다. 따라서
`dual-core template`을 별도로 복제하지 않고 `image target` 두 개와 이를 묶는 project
target으로 표현한다.

공식 근거:

- [Espressif ESP-IDF FreeRTOS SMP 문서](https://docs.espressif.com/projects/esp-idf/en/stable/esp32/api-reference/system/freertos_idf.html): 동일한 코어와 공유 memory를 사용하는 SMP 및 task affinity 설명
- [ST AN5361 — dual-core STM32H7 project](https://www.st.com/resource/en/application_note/dm00629855.pdf): root project 아래 core별 MCU subproject, build/debug configuration 설명
- [ST STM32CubeH7 user manual](https://www.st.com/resource/en/user_manual/dm00386433-getting-started-with-stm32cubeh7-for-stm32h7-series--stmicroelectronics.pdf): dual-core example의 `CM7`, `CM4`, `Common` 구조 설명
- [ST CubeIDE for VS Code dual-core 문서](https://dev.st.com/stm32cube-docs/stm32cubeide-vscode/1.0.1/en/docs/markup/tutorials/dual_core.html): core별 vector table, linker script, startup와 두 project 연결 방식 설명

### 이 템플릿에서 사용할 추상화

```text
project
├── image: application               # 기존 single-core와 동일
├── image: bootloader + application  # 같은 core, 다른 Flash slot
└── image: cm7 + cm4                 # 다른 core, core별 build context
```

image마다 최소한 다음 속성을 독립적으로 가진다.

- processor/core와 compiler flags
- device/core define
- startup와 vector table
- Flash/RAM linker region
- source/include/library target
- `.elf`, `.bin`, `.hex`, `.map`
- flash 및 debug configuration

project는 image 사이의 build 순서, memory overlap, shared region, boot 순서와 combined
artifact를 관리한다. 이 구조에서 single-core는 예외가 아니라 image가 하나인 가장 단순한
구성이다.

### CubeMX와 공식 ST VS Code extension의 경계

CubeMX `.ioc`와 현재 `config.cmake`는 같은 하드웨어 설정에 대해 서로 다른 source of
truth다. CubeMX code generation을 현재 템플릿에 부분적으로 섞으면 startup, HAL init,
middleware, linker와 `main`의 소유권이 충돌한다. 따라서 `.ioc`-first workflow는 형제
템플릿으로 분리한다.

공식 `STM32CubeIDE for Visual Studio Code` 확장은 단순한 파일 참조기만은 아니다.
empty CMake project 생성, CubeMX 생성 project의 import/discovery, firmware example
import, 기존 Eclipse 기반 CubeIDE project 변환, build/debug와 tool bundle 관리를
제공한다. 그러나 `.ioc`의 pin/clock/peripheral 시각 설정 자체를 VS Code 안에 다시
구현한 것은 아니며, 공식 project 생성 문서도 그 단계에서는 standalone CubeMX를
열도록 안내한다.

따라서 적용 원칙은 다음과 같다.

- 현재 lightweight `config.cmake` 템플릿은 ST extension pack에 의존하지 않는다.
- 현재 템플릿의 기본 extension recommendation에도 전체 ST pack을 추가하지 않는다.
- CubeMX 형제 템플릿은 standalone CubeMX를 source-of-truth editor로 사용한다.
- CubeMX 형제 템플릿에서는 import/discovery/build/debug가 필요할 때 ST extension을
  선택적으로 사용할 수 있다.
- ST extension이 설치되어 있어도 현재 템플릿을 CubeMX-owned project로 자동 변환하거나
  `.ioc`와 `config.cmake`의 양방향 동기화를 시도하지 않는다.

공식 근거:

- [ST 첫 project 생성 문서](https://dev.st.com/stm32cube-docs/stm32cubeide-vscode/latest/en/docs/markup/getting_started/first_project_creation.html): empty CMake 생성과 standalone CubeMX project import 절차
- [ST extension marketplace](https://marketplace.visualstudio.com/items?itemName=stmicroelectronics.stm32-vscode-extension): extension pack, project 생성, discovery, debug 및 bundle 기능
- [ST CMake 문서](https://dev.st.com/stm32cube-docs/stm32cubeide-vscode/latest/en/docs/markup/basic_concepts/cmake.html): CubeMX-owned CMake와 user-owned CMake 파일의 경계

## 4. 확인된 현재 기준선

- `python3 tools/setup.py --self-test`: 통과
- Arm GNU Toolchain 15.3.1 fresh build:
  - CoreH743I: 통과
  - NUCLEO-F411RE: 통과
  - NUCLEO-G071RB: 통과
- 실제 CMSIS-Pack 표본:
  - H743, F411, U575: 기본 정보 파생 성공
  - H745: 복수 processor를 보존하지 않고 마지막 Cortex-M4로 덮어쓴 뒤 build 실패
  - N657: 내장 Flash가 없어 현재 linker model에서 실패
- CMake `clean` 이후 `.bin`, `.hex`, `.map`이 남음
- 저장소에 자동 CI workflow가 없음

따라서 현재 build 기반은 유지할 수 있지만, processor context를 명시적으로 모델링하지
않은 채 dual-core 지원을 선언해서는 안 된다. fail-closed 검증과 재현성 기준선을 만든
뒤 single-image CMake를 image-target 구조로 일반화한다.

## 5. 우선순위 요약

| 순서 | 우선순위 | 단계 | 완료 결과 |
|---:|---|---|---|
| 1 | P0 | 테스트 임시 경로 안전화 | 테스트 도구가 기존 파일을 삭제할 수 없음 |
| 2 | P0 | 타깃 설정의 단일 source of truth | BOARD/MCU와 파생값이 원자적으로 일치 |
| 3 | P0 | MCU topology/capability와 입력 검증 | processor를 임의 선택하지 않고 topology를 보존 |
| 4 | P1 | Cube 경계와 library 연결 정리 | `add cube`와 재귀 source glob 제거 |
| 5 | P1 | dependency lock과 CI 기준선 | 대규모 CMake 변경 전 자동 회귀 검사 확보 |
| 6 | P1 | image-target CMake 기반 | 기존 single image를 일반화된 target 하나로 동일하게 build |
| 7 | P1 | bootloader/application multi-image | 같은 core의 두 image와 Flash layout/VTOR 계약 지원 |
| 8 | P1 | STM32H7 heterogeneous dual-core | CM7/CM4별 build context와 shared-memory/boot 계약 지원 |
| 9 | P1 | multi-image artifact/flash/debug | image별 및 전체 build/flash/debug와 combined HEX 제공 |
| 10 | P2 | build와 dependency 경량화 | clone 및 compile 비용 감소 |
| 11 | P2 | 설정 UX와 문서 마무리 | 첫 사용과 multi-image 설정이 짧고 모호하지 않음 |

Stage 1~5는 안전·회귀 기준선, Stage 6~9는 multi-image 확장 기준, Stage 10~11은
경량화와 사용성 개선으로 본다. 각 단계는 기존 single-image build를 계속 통과시켜야
하며, dual-core 기능 때문에 기본 사용 경로가 복잡해져서는 안 된다.

## 6. 단계별 구현 계획

## Stage 1 — 테스트 임시 경로 안전화

우선순위: P0

### What

- `try_board.py`의 고정 경로 생성과 선행 `shutil.rmtree()`를 제거한다.
- `tempfile.mkdtemp()`로 실행마다 새로운 디렉터리를 만든다.
- `TRY_DIR`을 사용할 때 resolve한 경로가 허용된 부모 아래인지 검증한다.
- 기본값은 tracked file만 복사하고, untracked file 포함은 명시적 option으로 둔다.
- 성공 시 자동 정리하고 `--keep`일 때만 경로를 보존한다.
- `argparse`를 사용해 알 수 없는 option과 잘못된 BOARD/MCU 문자열을 거부한다.

예상 변경 파일:

- `tools/try_board.py`
- `tests/test_try_board.py`
- `README.md`
- `README_KOR.md`

### Why

현재 구현은 사용자 입력으로 만든 경로를 무조건 삭제하므로 테스트 도구가 temp
root 밖의 기존 데이터를 제거할 수 있다. 다른 개선보다 먼저 제거해야 하는 안전
문제다.

### Verification

Self-verification:

```sh
python3 -m unittest tests.test_try_board
python3 tools/setup.py --self-test
python3 tools/try_board.py NUCLEO-G071RB --keep
git status --short
```

검증 항목:

- `..`, `/`, path separator가 들어간 입력이 실행 전에 거부됨
- 같은 BOARD 테스트를 병렬 실행해도 서로 다른 directory 사용
- 기존 directory를 준비해도 삭제하지 않음
- `--keep`이 없으면 정리되고, 있으면 출력된 위치가 남음
- 원본 working tree에 변경이 없음

On-chip verification: 필요 없음.

### Progress

- [x] Implemented
- [x] Self-verified
- [x] Reported
- [x] Chip-verified / N/A confirmed
- [ ] Committed by user

## Stage 2 — 타깃 설정의 단일 source of truth

우선순위: P0

### What

- 사용자 입력과 MCU/processor 파생값을 분리한다.
- `config.cmake`에는 BOARD/MCU와 project 공통 정책 같은 사용자 의도만 둔다.
- FAMILY, physical memory와 Pack provenance는 `generated/device.cmake`에 기록하고,
  CPU_FLAGS, core define, startup 같은 실행 속성은 이후 image별 generated config로
  분리할 수 있는 구조로 둔다.
- `setup.py target --board <name>`과 `setup.py target --mcu <part>` 중 하나로
  retarget을 원자적으로 수행한다.
- 알려진 BOARD와 MCU가 다르면 실패한다.
- 기존 파생값과 새 pack 결과가 다르면 조용히 유지하지 않고 diff를 출력한다.
- 수동 override는 이름이 분명한 별도 변수로 제공한다.
- 모든 검증과 network 조회가 성공한 뒤 임시 파일 + `os.replace()`로 기록한다.
- target 변경 시 기존 family submodule, HAL config와 기존 image 설정의 처리 방법을
  출력한다.

예상 변경 파일:

- `tools/setup.py`
- `config.cmake`
- `CMakeLists.txt`
- `cmake/stm32.cmake`
- `tests/test_target_config.py`
- `README.md`
- `README_KOR.md`

### Why

현재는 MCU만 변경하고 파생 필드를 비우지 않으면 이전 FAMILY, CPU flags, memory,
device define을 그대로 사용할 수 있다. 잘못된 타깃 firmware를 정상 build로
오인할 수 있으므로 가장 중요한 correctness 개선이다.

### Verification

Self-verification:

```sh
python3 -m unittest tests.test_target_config
python3 tools/setup.py --self-test
python3 tools/try_board.py NUCLEO-G071RB
python3 tools/try_board.py NUCLEO-F411RE
python3 tools/try_board.py CoreH743I
git diff --check
```

검증 항목:

- H743 → F411 → G071 순서로 변경해도 이전 family 값이 남지 않음
- BOARD/MCU 불일치가 file write와 submodule 작업 전에 실패
- network/git 실패를 주입해도 config가 부분 변경되지 않음
- 동일 target 재실행 결과가 byte-for-byte 동일
- device 및 processor 파생값의 provenance가 확인 가능

On-chip verification:

지원되는 실제 보드 중 최소 한 대에서 수행한다. NUCLEO-F411RE 예:

```sh
python3 tools/setup.py target --board NUCLEO-F411RE
cmake --preset default
cmake --build --preset default
cmake --build --preset flash
```

115200 8N1 terminal에서 다음을 확인하고 전체 log를 보관한다.

```text
Hello, World!
board  NUCLEO-F411RE (STM32F411RETx)
tick: 1
tick: 2
```

### Progress

- [ ] Implemented
- [ ] Self-verified
- [ ] Reported
- [ ] Chip-verified / N/A confirmed
- [ ] Committed by user

## Stage 3 — MCU topology/capability와 입력 검증

우선순위: P0

### What

- CMSIS-Pack의 모든 processor record를 이름, core, FPU/DSP, endian, memory context와
  함께 보존한다. 반복 record를 하나의 전역 변수로 덮어쓰지 않는다.
- processor가 하나면 기존 single-image 기본 context로 선택한다.
- processor가 여러 개면 장치 전체를 unsupported로 판정하지 않고 multi-core
  topology로 분류한다. image가 core context를 지정하지 않은 경우에만 모호성 오류로
  실패한다.
- internal Flash가 없는 target을 조기에 거부한다.
- SMP/AMP 여부를 Pack 정보만으로 단정하지 않고 family adapter metadata로 확정한다.
- TrustZone capability, HAL2, 지원하지 않는 core/family를 서로 다른 capability 상태로
  구분한다.
- 실제 part suffix를 고려해 PDSC part pattern과 입력 part number를 비교한다.
  예: `STM32U575ZIT6Q`.
- `RAM_REGION`은 RAM 후보에 포함된 이름만 허용한다.
- Flash/RAM size, origin, alignment와 CPU/FPU 조합을 검증한다.
- F1처럼 공통 console HAL 모델과 다른 family는 adapter를 구현하기 전까지 거부한다.
- README에 verified / expected / unsupported 표를 둔다.

예상 변경 파일:

- `tools/setup.py`
- `tests/fixtures/pdsc/*`
- `tests/test_pack_parser.py`
- `README.md`
- `README_KOR.md`

### Why

현재 H745는 여러 processor 중 마지막 M4로 전역 CPU 설정을 덮어쓴다. dual-core라서
실패해야 하는 것이 아니라 topology 정보를 잃고 잘못된 core/memory 조합을 만드는
것이 문제다. N657은 linker 구성 도중에야 실패한다. 두 경우 모두 config와 submodule을
일부 변경하기 전에 정확한 capability 결과를 내야 한다.

### Verification

Self-verification:

```sh
python3 -m unittest tests.test_pack_parser
python3 tools/setup.py --self-test
```

fixture matrix:

- positive: H743, F411, G071, U575
- topology positive: H745가 `CM7`과 `CM4` 두 processor context로 파싱됨
- ambiguity negative: H745에서 image core를 지정하지 않으면 명확한 오류
- unsupported negative: N657 flashless, HAL2 target
- normalization: `STM32U575ZIT6`, `STM32U575ZIT6Q`
- invalid: Flash를 `RAM_REGION`으로 지정, 잘못된 CPU/FPU 조합

모든 negative case는 다음을 만족해야 한다.

- network clone 또는 file write 전에 실패
- 원인을 설명하는 안정된 error code/message 제공
- working tree와 config가 unchanged

On-chip verification: 필요 없음. 이 단계는 topology를 보존하고 모호한 선택을
거부하는 host-side parser 계약만 확정한다. 실제 H745 실행은 Stage 8에서 검증한다.

### Progress

- [ ] Implemented
- [ ] Self-verified
- [ ] Reported
- [ ] Chip-verified / N/A confirmed
- [ ] Committed by user

## Stage 4 — Cube 경계와 library 연결 정리

우선순위: P1

### What

- `setup.py add cube`와 양 언어 README의 사용 예제를 제거한다.
- `.ioc.bak`, `.mxproject` 같은 CubeMX 전용 ignore는 형제 템플릿으로 이동한다.
- `/Debug/`, `/Release/` ignore가 필요하면 root에만 적용한다.
- 현재 템플릿이 `.ioc`를 사용하지 않는다는 점과 형제 CubeMX 템플릿 선택 기준을
  README 첫 부분에 짧게 표시한다.
- 현재 템플릿의 `.vscode/extensions.json`에는 전체 ST extension pack을 기본 추천으로
  추가하지 않는다. 형제 CubeMX 템플릿에서만 optional 도구로 설명한다.
- 임의 repository의 모든 `.c`를 재귀 glob하는 library 연결을 제거한다.
- 외부 library는 다음 중 하나로만 연결한다.
  - library가 제공하는 `CMakeLists.txt`를 `add_subdirectory()`로 연결
  - project가 source/include 목록을 명시한 manifest 또는 CMake target 제공
- clone/download와 build 연결을 별도 동작으로 분리한다.

예상 변경 파일:

- `tools/setup.py`
- `cmake/stm32.cmake`
- `config.cmake`
- `.gitignore`
- `README.md`
- `README_KOR.md`
- library fixture tests

### Why

전체 STM32Cube repository와 임의 library tree를 재귀 컴파일하면 example `main`,
HAL, startup, middleware가 중복된다. ST extension을 설치해도 이 source ownership
충돌이 해결되지는 않는다. CubeMX 분리 결정과도 맞지 않고, 현재 기능을 정상적인
library manager로 오해하게 만든다.

### Verification

Self-verification:

```sh
python3 -m unittest tests.test_library_integration
python3 tools/setup.py --help
python3 tools/try_board.py NUCLEO-G071RB
rg -n "add cube|EXTRA_LIB_DIRS|\.ioc|\.mxproject" .
```

검증 항목:

- `add cube`가 더 이상 지원 명령으로 노출되지 않음
- 현재 템플릿의 기본 extension recommendation에 ST extension pack이 없음
- 임의 repository clone만으로 source가 자동 추가되지 않음
- CMake target을 제공하는 fixture library 연결 성공
- 명시적 raw-source fixture 연결 성공
- 기존 대표 target build 통과

On-chip verification: 필요 없음.

### Progress

- [ ] Implemented
- [ ] Self-verified
- [ ] Reported
- [ ] Chip-verified / N/A confirmed
- [ ] Committed by user

## Stage 5 — dependency lock과 CI 기준선

우선순위: P1

### What

- dependency lock manifest를 추가한다.
- lock에 CMSIS-Core, CMSIS-device, HAL, FreeRTOS commit과 PDSC version/hash,
  toolchain version을 기록한다.
- `setup.py --frozen`은 lock과 다른 dependency를 받거나 갱신하지 않는다.
- 기존 submodule path가 expected origin/gitlink인지 검증한다.
- 개인 toolchain 경로는 tracked config에 기록하지 않고 환경 변수 또는 ignored
  `CMakeUserPresets.json`으로 이동한다.
- offline unit test와 online integration test를 분리한다.
- PR CI에 self-test, unit test, format/static check, representative single-image build
  matrix를 둔다.
- scheduled CI에서 live pack/pin-data/upstream 호환성을 확인한다.

최소 build/test matrix:

- H743 + FreeRTOS
- F411 + FreeRTOS
- G071 + FreeRTOS
- G071 + `RTOS=none`
- H745 `CM7`/`CM4` topology parser 검사
- H745 core 미지정 ambiguity와 N657 flashless expected-failure 검사

예상 변경 파일:

- dependency lock file
- `tools/setup.py`
- `.gitignore`
- `.github/workflows/*`
- `tests/*`
- `README.md`
- `README_KOR.md`

### Why

현재 최초 생성 시점의 default branch HEAD와 최신 PDSC를 사용하므로 같은 template
commit도 날짜에 따라 다른 dependency와 설정을 얻을 수 있다. 이후 image-target
CMake와 multi-image를 추가하려면 먼저 기존 single-image 동작을 자동으로 비교할
기준선이 필요하다.

### Verification

Self-verification:

```sh
python3 -m unittest discover -s tests -p 'test_*.py'
python3 tools/setup.py --self-test
python3 tools/setup.py --frozen --dry-run
python3 tools/try_board.py NUCLEO-G071RB
python3 tools/try_board.py NUCLEO-F411RE
python3 tools/try_board.py CoreH743I
```

CI 검증:

- clean clone에서 모든 PR job 통과
- network를 차단한 `--frozen` build 통과
- lock의 commit/hash를 변경하면 검증 실패
- H745 topology는 두 processor를 보존하고 core 미지정만 정해진 오류로 실패
- Windows/macOS/Linux self-test 결과 보관

On-chip verification: 필요 없음. CI는 Stage 2에서 승인된 hardware 결과를 대체하지
않는다.

### Progress

- [ ] Implemented
- [ ] Self-verified
- [ ] Reported
- [ ] Chip-verified / N/A confirmed
- [ ] Committed by user

## Stage 6 — image-target CMake 기반

우선순위: P1

### What

- 현재 전역 `add_executable()` 구성을 `stm32_add_image()` 같은 CMake 함수로 감싼다.
- 첫 단계에서는 image 한 개만 허용하고 기존 application을 `application` image로
  그대로 옮긴다.
- image target이 processor context, core define, CPU flags, startup, linker layout,
  source/include/library와 output name을 소유하게 한다.
- physical device 정보와 image 실행 정보를 분리한다.
- image별 generated config와 artifact directory를 만들되 기존 기본 target 이름과
  명령에는 호환 alias를 제공한다.
- HAL/CMSIS 공통 source는 공유할 수 있지만 core-specific compile option은 image
  target 밖의 전역 option으로 누출하지 않는다.
- `PROJECT_NAME`과 CMake target name을 분리해 여러 executable을 선언할 수 있게 한다.

개념 API:

```cmake
stm32_add_image(
    NAME application
    CORE AUTO
    STARTUP AUTO
    FLASH_REGION AUTO
    RAM_REGION AUTO
    SOURCES ${APP_SOURCES}
)
```

예상 변경 파일:

- `CMakeLists.txt`
- `cmake/stm32.cmake`
- `cmake/stm32_flash.ld.in`
- `config.cmake`
- `tools/setup.py`
- `tests/test_image_target.py`
- README 양 언어

### Why

multi-image와 STM32H7 dual-core를 바로 조건문으로 덧붙이면 전역 CPU flags, startup,
linker state가 다시 섞인다. 기존 single-image를 먼저 image target 하나로 표현하고
출력 동등성을 확인해야 이후 복수 image가 단순한 target 추가가 된다.

### Verification

Self-verification:

```sh
python3 -m unittest tests.test_image_target
python3 tools/try_board.py NUCLEO-G071RB
python3 tools/try_board.py NUCLEO-F411RE
python3 tools/try_board.py CoreH743I
cmake --build --preset default --target application
```

검증 항목:

- 한 configure에 application executable이 정확히 하나 생성됨
- 기존과 새 build의 vector address, entry symbol, CPU attributes와 주요 section이 일치
- image target 밖에서 `CPU_FLAGS`, startup, linker script가 전역 적용되지 않음
- 두 번째 image 선언은 아직 지원되지 않는다는 명확한 configure 오류
- 기존 `cmake --build --preset default` 사용법 유지

On-chip verification:

Stage 2에서 검증한 single-core 보드에 `application` image를 flash한다.

- reset 후 UART `Hello, World!`와 `tick` 확인
- debugger가 `application.elf`의 `main`에서 정지
- 변경 전 승인된 serial/debug 결과와 동작이 같음

### Progress

- [ ] Implemented
- [ ] Self-verified
- [ ] Reported
- [ ] Chip-verified / N/A confirmed
- [ ] Committed by user

## Stage 7 — bootloader/application multi-image

우선순위: P1

### What

- 한 configure에서 같은 processor context를 사용하는 image 여러 개를 허용한다.
- bootloader와 application이 physical Flash를 각자의 slot으로 나누어 사용하게 한다.
- 각 image가 Flash origin/size, RAM origin/size, vector alignment와 entry point를
  독립적으로 가진다.
- 모든 image와 reserved region의 범위 및 overlap을 configure 단계에서 검사한다.
- application의 VTOR 설정 주체와 bootloader jump 절차를 명시적 계약으로 고정한다.
- bootloader와 application을 각각 build/flash할 수 있게 한다.
- single-image 설정에는 추가 slot 선언을 요구하지 않는다.
- bootloader jump용 on-target fixture를 별도 test asset으로 둔다.

예상 변경 파일:

- `config.cmake`
- `cmake/stm32.cmake`
- `cmake/stm32_flash.ld.in`
- `tools/setup.py`
- `tests/test_flash_layout.py`
- `tests/on_target/bootloader/*`
- README 양 언어

### Why

bootloader/application은 서로 다른 core adapter 없이 multi-image layout과 image별
linking을 검증할 수 있는 가장 단순한 첫 소비자다. 현재 offset 기능은 Flash origin만
옮기고 전체 size를 유지하며 VTOR 계약도 없어 물리 Flash 끝을 넘을 수 있다.

### Verification

Self-verification:

```sh
python3 -m unittest tests.test_flash_layout
cmake --preset default -DSTM32_LAYOUT=bootloader-app
cmake --build --preset default --target bootloader application
arm-none-eabi-objdump -h build/images/bootloader/bootloader.elf
arm-none-eabi-objdump -h build/images/application/application.elf
```

검증 항목:

- 각 `.isr_vector`가 선언한 slot origin에 배치됨
- 두 image와 reserved region이 겹치지 않고 physical Flash 끝을 넘지 않음
- 정렬되지 않거나 겹치거나 범위를 벗어난 layout은 configure 단계에서 실패
- application vector address와 VTOR 계약이 일치
- 같은 source symbol이 두 image에 존재해도 link namespace가 충돌하지 않음

On-chip verification:

Stage에서 제공하는 NUCLEO-F411RE bootloader fixture를 사용한다.

```sh
cmake --build --preset default --target flash-bootloader
cmake --build --preset default --target flash-application
```

확인 항목:

- reset 후 bootloader가 application으로 jump
- UART에서 bootloader marker 뒤에 application `Hello, World!`와 `tick` 확인
- debugger에서 application 실행 중 `SCB->VTOR`가 application origin과 일치
- reset log, serial log, VTOR 값을 보고 자료로 보관

### Progress

- [ ] Implemented
- [ ] Self-verified
- [ ] Reported
- [ ] Chip-verified / N/A confirmed
- [ ] Committed by user

## Stage 8 — STM32H7 heterogeneous dual-core

우선순위: P1

### What

- STM32H745/H747/H755/H757 family adapter에서 Pack의 `CM7`과 `CM4` processor
  context를 각각 image에 연결한다.
- CM7과 CM4 image에 서로 다른 `-mcpu`, FPU option, `CORE_CM7`/`CORE_CM4`, startup,
  vector table, linker layout과 HAL config를 적용한다.
- `shared/` source는 물리적으로 한 번 관리하되 각 image context에서 별도로 컴파일한다.
- core-local Flash/RAM, shared RAM과 reserved region을 구분하고 overlap을 검사한다.
- shared-memory section과 HSEM/IPCC 같은 inter-core synchronization hook을 제공한다.
- CM7 D-cache가 켜진 경우 shared memory를 non-cacheable로 두거나 cache maintenance를
  요구하는 정책을 명시한다.
- 어느 core가 먼저 부팅되는지 하드코딩하지 않고 device boot option과 board adapter가
  선택한 boot/release/synchronization 정책을 manifest에 기록한다.
- 한 core만 사용하는 구성도 허용하되 미사용 core 상태를 명시한다.

예상 변경 파일:

- `tools/setup.py`
- `cmake/stm32.cmake`
- H7 dual-core family/board adapter
- `config.cmake` 또는 image config 예제
- `tests/test_dual_core.py`
- `tests/on_target/h745_dual_core/*`
- README 양 언어

### Why

ESP32식 SMP는 동일한 두 코어가 하나의 application과 OS를 공유하지만 STM32H7
dual-core는 Cortex-M7과 Cortex-M4가 독립적으로 부팅하고 링크되는 AMP다. 따라서
task affinity option 하나로 처리할 수 없지만, 별도 템플릿도 필요 없다. Stage 6의
image target 두 개에 core별 context와 inter-core 계약을 추가하면 된다.

### Verification

Self-verification:

```sh
python3 -m unittest tests.test_dual_core
python3 tools/setup.py target --board NUCLEO-H745ZI-Q
cmake --preset default
cmake --build --preset default --target cm7 cm4
arm-none-eabi-readelf -A build/images/cm7/cm7.elf
arm-none-eabi-readelf -A build/images/cm4/cm4.elf
```

검증 항목:

- CM7 ELF와 CM4 ELF의 CPU/FPU attributes, startup, vector와 define이 각각 정확함
- 두 image의 Flash/RAM region이 겹치지 않으며 선언된 shared region만 공유됨
- core 이름 누락, 중복 core 배정, 잘못된 startup/flags 조합은 configure 전에 실패
- 공통 source가 각 core option으로 독립 컴파일됨
- single-core H743/F411/G071 회귀 build가 계속 통과

On-chip verification:

NUCLEO-H745ZI-Q 또는 동등한 H745/H747 board에서 수행한다.

```sh
cmake --build --preset default --target flash-cm7
cmake --build --preset default --target flash-cm4
```

reset 후 다음을 확인한다.

- CM7과 CM4가 각각 고유 boot marker를 남김
- HSEM 또는 선택한 IPC를 통해 shared counter/message를 왕복
- 1000회 교환 동안 timeout/data mismatch가 없음
- CM7 cache policy를 바꾼 negative fixture가 검증에서 탐지됨
- 각 core를 독립 debug해 해당 ELF의 `main`에서 정지
- serial log, IPC count, debugger console과 option-byte/boot-mode 정보를 보관

### Progress

- [ ] Implemented
- [ ] Self-verified
- [ ] Reported
- [ ] Chip-verified / N/A confirmed
- [ ] Committed by user

## Stage 9 — multi-image artifact, flash, debug 일관성

우선순위: P1

### What

- image별 `.elf`, `.bin`, `.hex`, `.map`을 CMake build graph의 output/byproduct로
  등록한다.
- `build-all`, `flash-<image>`, `flash-all` target을 제공하고 boot manifest의 순서와
  reset 정책을 따른다.
- 여러 HEX를 주소 보존 방식으로 결합한 `combined.hex`를 선택적으로 만들며 overlap이
  있으면 실패한다. combined 파일은 배포 artifact일 뿐 image별 ELF를 대체하지 않는다.
- flash target이 실제 artifact에 의존하고, clean이 모든 image 및 combined artifact를
  제거하도록 한다.
- image 목록, 주소, hash, core, ELF path와 flash 순서를 machine-readable manifest로
  출력한다.
- VS Code task/launch를 manifest에서 생성하거나 해석해 image 하나 또는 dual-core
  compound debug를 선택할 수 있게 한다.
- 기존 single-image `build`, `flash`, F5 경로는 application image의 호환 alias로 둔다.
- custom command에 `VERBATIM`을 적용하고 Debug/Release/MinSizeRel preset을 제공한다.

예상 변경 파일:

- `CMakeLists.txt`
- `cmake/stm32.cmake`
- `CMakePresets.json`
- `.vscode/tasks.json`
- `.vscode/launch.json`
- artifact/manifest merge tool
- artifact tests

### Why

복수 image를 build하는 것과 최종 파일 하나를 배포하는 것은 다른 문제다. CMake가
image별 ELF를 유지하면서 combined HEX와 순서 있는 flash/debug를 조정해야 한다.
현재 single-image에서도 clean 후 `.bin`, `.hex`, `.map`이 남고 VS Code 경로가
하드코딩되어 있으므로 함께 바로잡는다.

### Verification

Self-verification:

```sh
python3 -m unittest tests.test_artifacts tests.test_image_manifest
cmake --preset default -DSTM32_LAYOUT=bootloader-app
cmake --build --preset default --target build-all
cmake --build --preset default --target clean
cmake --build --preset default --target flash-all -- -n
```

검증 항목:

- clean 후 모든 image의 `.elf/.bin/.hex/.map`과 combined artifact 제거
- artifact 하나만 삭제해도 flash dependency가 해당 생성 command를 다시 실행
- combined HEX를 다시 분리해 각 image HEX와 byte/address가 동일
- overlap fixture는 combined artifact 생성 전에 실패
- project rename 후 VS Code 설정을 수동 수정하지 않아도 manifest의 ELF를 사용
- space가 포함된 throwaway workspace와 fresh VS Code flash task 성공

On-chip verification:

single-core board와 Stage 8의 H745 board에서 각각 수행한다.

```text
VS Code → Run Task → flash-all
VS Code → Run and Debug → image 선택 또는 dual-core compound
```

확인 항목:

- single-image는 기존과 동일한 한 번의 flash/debug 경로 제공
- H745 `flash-all`이 manifest 순서대로 두 image를 program하고 reset
- compound debug에서 CM7/CM4가 각자의 ELF source와 symbol을 사용
- combined HEX 단독 program 후에도 개별 flash와 같은 UART/IPC 결과
- task log, debugger console, programmed address 목록을 보관

### Progress

- [ ] Implemented
- [ ] Self-verified
- [ ] Reported
- [ ] Chip-verified / N/A confirmed
- [ ] Committed by user

## Stage 10 — build와 dependency 경량화

우선순위: P2

### What

- 모든 HAL/LL source를 컴파일하는 방식에서 활성 module 또는 명시적 target 기반으로
  전환한다.
- CMSIS-Core와 FreeRTOS submodule의 shallow/on-demand 정책을 정한다.
- `RTOS=none`일 때 FreeRTOS를 clone하거나 초기화하지 않는다.
- 가벼운 범용 템플릿을 우선한다면 bare-metal을 기본값으로 바꿀지 결정한다.
- build step 수와 clone/download 크기를 CI metric으로 기록한다.

### Why

현재 Hello World build도 H743에서 약 135 step이 필요하고, 두 기본 submodule의 Git
history만 약 220 MB다. correctness와 회귀 검사를 먼저 확보한 뒤 최적화해야 한다.

### Verification

Self-verification:

```sh
python3 tools/try_board.py NUCLEO-G071RB
python3 tools/try_board.py NUCLEO-F411RE
python3 tools/try_board.py CoreH743I
du -sh .git/modules/lib/* lib/*
cmake --build --preset default --clean-first -v
```

검증 항목:

- 세 대표 target의 ELF size와 runtime 동작에 의도하지 않은 변화가 없음
- HAL/LL compile step 수 감소
- `RTOS=none` clone에서 FreeRTOS 불필요
- fresh clone의 download 크기와 시간이 기준선보다 감소

On-chip verification:

Stage 2에서 사용한 보드에서 bare-metal과 FreeRTOS를 각각 flash한다.

- bare-metal/FreeRTOS 두 build variant 모두 UART `Hello, World!` 출력
- bare-metal은 1초마다 `tick` 증가
- FreeRTOS는 `tick`과 free heap 출력
- Flash/RAM 사용량 before/after 비교 자료 보관

### Progress

- [ ] Implemented
- [ ] Self-verified
- [ ] Reported
- [ ] Chip-verified / N/A confirmed
- [ ] Committed by user

## Stage 11 — 설정 UX와 문서 마무리

우선순위: P2

### What

- console을 선택 기능으로 만들고 `CONSOLE=none`을 지원한다.
- 서로 다른 alternate function을 표현하도록 `CONSOLE_TX_AF`와 `CONSOLE_RX_AF`를
  분리한다.
- CMake target에 실제 C standard를 지정해 VS Code의 C17 설정과 일치시킨다.
- `PROJECT_NAME`과 output 이름을 한 곳에서 관리한다.
- Quick Start는 atomic target 명령을 중심으로 5분 이내 절차로 줄인다.
- 기본 Quick Start는 image-target 내부 구조를 몰라도 single-image project를 사용할 수
  있게 유지한다.
- 별도 advanced guide에 bootloader/application과 CM7/CM4 설정 예제를 제공한다.
- README에서 dual-core와 image 수를 동일시하지 않고 SMP 단일-image, AMP 복수-image,
  combined 배포 artifact의 차이를 설명한다.
- 긴 GitHub template 유지보수 설명은 별도 문서로 이동한다.
- README 첫 부분에 현재 템플릿과 CubeMX 형제 템플릿의 선택표를 둔다.
- “수정할 유일한 파일”을 “하드웨어 build 설정의 기준 파일”로 정확하게 바꾼다.
- English/Korean 문서의 heading, command, link parity를 CI에서 검사한다.

### Why

현재 Quick Start와 상세 retarget 절차가 다르고, project 이름·ELF·OpenOCD 설정을
여러 파일에서 수동으로 맞춰야 한다. 안정화 이후 첫 사용 경험과 문서의 약속을
실제 동작에 맞춘다.

### Verification

Self-verification:

```sh
python3 -m unittest tests.test_docs tests.test_console_config
python3 tools/try_board.py NUCLEO-G071RB
cmake --preset default
cmake --build --preset default
```

검증 시나리오:

- 새 사용자가 Quick Start만 따라 supported board build 성공
- single-image, bootloader/application, CM7/CM4 문서 예제가 실제 configure test를 통과
- console disabled build 성공
- TX/RX가 다른 AF인 fixture가 올바른 macro 생성
- project rename 후 build/flash/debug 경로가 함께 변경
- English/Korean command와 내부 link 검사 통과

On-chip verification:

- console enabled image에서 정상 UART 출력
- console disabled image가 UART 없이 main loop 또는 RTOS scheduler 진입
- debugger에서 `startup_error == 0` 확인

### Progress

- [ ] Implemented
- [ ] Self-verified
- [ ] Reported
- [ ] Chip-verified / N/A confirmed
- [ ] Committed by user

## 7. 단계 운영 규칙

각 Stage는 다음 순서로만 진행한다.

1. 현재 Stage 범위만 구현한다.
2. 문서에 정의한 self-verification을 실행한다.
3. 변경 파일, 실제 검증 명령과 출력, 남은 hardware 검증을 보고한다.
4. hardware 검증이 있으면 사용자가 실행한 결과를 확인한다.
5. 사용자가 결과를 승인한 뒤 사용자가 직접 stage/commit한다.
6. 이 문서의 Progress checkbox를 갱신한다.
7. 사용자가 다음 Stage 진행을 명시적으로 요청할 때만 넘어간다.

한 Stage의 검증이 실패하면 다음 Stage로 넘어가지 않는다. 여러 Stage를 하나의
commit으로 합치지 않는다.

## 8. 전체 완료 조건

- 타깃 변경으로 stale FAMILY/CPU/memory 값이 남을 수 없음
- CMSIS-Pack의 복수 processor가 덮어써지지 않고 device topology로 보존됨
- 현재 단계에서 지원하지 않는 target/context가 repository 변경 전에 명확하게 실패
- 테스트 도구가 기존 경로를 삭제하지 않음
- `setup.py add cube`와 암묵적 recursive library build가 없음
- 기존 single-core application이 image target 하나로 회귀 없이 build됨
- bootloader/application의 Flash slot, overlap, VTOR와 jump 계약이 검증됨
- STM32H7 CM7/CM4가 core별 flags/startup/linker/ELF로 build되고 실제 board에서 IPC 검증됨
- `.elf/.bin/.hex/.map`과 combined HEX 생성, clean/flash dependency가 CMake graph에 포함
- image별 및 전체 build, flash, debug가 manifest의 동일한 target/ELF/address를 사용
- dependency lock으로 offline frozen build 가능
- 대표 M0+/M4F/M7 single-image, bootloader/application, H7 CM7/CM4 build와 negative
  capability test가 CI에서 동작
- hardware 검증이 필요한 Stage의 log와 결과가 보관됨
- README가 SMP/AMP, 실행 image와 combined 배포 artifact를 정확히 구분함
- README의 현재 지원 범위와 실제 setup/build 동작이 일치
