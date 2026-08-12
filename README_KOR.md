# STM32 CMake 템플릿

[English](README.md) | [한국어](README_KOR.md)

STM32 펌웨어 개발을 바로 시작할 수 있는 VSCode + CMake + Make
템플릿입니다. `config.cmake`에 칩을 지정하고 스크립트 하나를 실행하면
빌드, 플래시, 디버깅이 가능한 프로젝트가 만들어집니다. HAL 및 LL
드라이버는 STMicroelectronics의 GitHub 저장소에서 submodule로 직접
가져옵니다.

예제 애플리케이션은 UART로 "Hello, World!"를 출력합니다.

## 자동으로 처리되는 작업

`MCU` 또는 `BOARD`를 설정하면 `tools/setup.py`가 다음 항목을 처리합니다.

- CMSIS 디바이스 헤더와 HAL/LL 드라이버가 들어 있는 ST 저장소를 찾아
  submodule로 추가
- Flash와 RAM의 시작 주소 및 크기, 디바이스 define(`STM32H743xx`) 결정
- 코어와 FPU에 맞는 컴파일러 플래그 결정

빌드 설정에는 패밀리별 값이 하드코딩되어 있지 않습니다. 저장소 이름은
`git ls-remote`로 GitHub에서 확인하고, 메모리 맵, 디바이스 define, 코어
정보는 해당 디바이스의 CMSIS-Pack에서 가져옵니다. 이 템플릿을 만든 뒤
새로운 STM32 패밀리가 추가되더라도 코드 변경 없이 사용할 수 있습니다.

`config.cmake`만 바꾸어 네 종류의 코어에 걸친 다음 다섯 부품에서
검증했습니다.

| MCU | 코어 | Flash | RAM |
|---|---|---|---|
| STM32H743IITx | Cortex-M7, 배정밀도 FPU | 2 MB | 128 KB (DTCM) |
| STM32F411RETx | Cortex-M4F | 512 KB | 128 KB |
| STM32G071RBTx | Cortex-M0+ | 128 KB | 36 KB |
| STM32U575ZITx | Cortex-M33, TrustZone | 2 MB | 768 KB |
| STM32C031C6Tx | Cortex-M0+ | 32 KB | 12 KB |

## GitHub 템플릿으로 사용하는 방법

펌웨어 프로젝트마다 이 템플릿으로 새 저장소를 만드세요. 템플릿에서
생성한 저장소는 독립된 프로젝트입니다. 이 저장소의 커밋 이력을
물려받지 않고 하나의 새 커밋으로 시작하며, fork가 아니고, 나중에
템플릿이 변경되어도 자동으로 동기화되지 않습니다. 자세한 내용은 GitHub의
[템플릿 저장소 문서](https://docs.github.com/en/repositories/creating-and-managing-repositories/creating-a-repository-from-a-template)를
참고하세요.

`David-Nam/stm32-vscode-template` 자체를 일반 clone하는 것은 템플릿을
개선하려는 경우에만 적합합니다.

### GitHub 웹사이트에서 생성

1. GitHub에서 이 저장소의 메인 페이지를 엽니다.
2. **Use this template** > **Create a new repository**를 선택합니다.
3. 소유자, 프로젝트 이름, 공개 범위를 정합니다. 일반적인 펌웨어
   프로젝트에는 기본 브랜치만 필요하므로 보통 **Include all branches**는
   선택하지 않습니다.
4. **Create repository from template**을 선택합니다.
5. 생성된 새 저장소를 vendor submodule과 함께 clone합니다.

```sh
git clone --recurse-submodules git@github.com:OWNER/PROJECT.git
cd PROJECT
```

**Include all branches**를 선택하면 GitHub가 각 브랜치를 서로 관련 없는
이력으로 복사하므로, 복사된 브랜치 사이에는 pull request를 만들거나
merge할 수 없습니다.

이미 `--recurse-submodules` 없이 clone했다면 다음 명령으로 초기화합니다.

```sh
git submodule update --init --recursive
```

### GitHub CLI에서 생성

[`gh repo create`](https://cli.github.com/manual/gh_repo_create)로 같은 작업을
할 수 있습니다.

```sh
gh repo create OWNER/PROJECT \
  --template David-Nam/stm32-vscode-template \
  --private --clone
cd PROJECT
git submodule update --init --recursive
```

공개 저장소가 필요하면 `--private` 대신 `--public`을 사용하세요.
`gh repo create --clone`은 submodule까지 초기화하지 않으므로 마지막 명령은
여전히 필요합니다.

### 첫 프로젝트 설정 체크리스트

1. [필수 도구](#필수-도구)의 프로그램을 설치합니다.
2. `config.cmake`에서 타깃을 설정합니다. 이 파일에는 동작 예제로
   `CoreH743I` 값이 들어 있으므로 자신의 보드와 일치한다고 가정하면 안
   됩니다. 알려진 `BOARD`를 선택할 때는 `setup.py`가 MCU를 채울 수 있도록
   `MCU`를 비우세요. `MCU`를 직접 지정할 때는 기존 `BOARD`를 바꾸거나
   비우세요. 전체 초기화 목록은 [칩 또는 보드 변경](#칩-또는-보드-변경)을
   따르세요.
3. `ARM_TOOLCHAIN_BIN`을 설정합니다. VSCode를 사용한다면
   `.vscode/settings.json`에 중복으로 들어 있는 디버거 경로도 수정합니다.
4. `python3 tools/setup.py`를 실행한 뒤 `make`를 실행합니다.
5. H7이 아닌 타깃에서 OpenOCD를 사용한다면 `.vscode/launch.json`의
   `target/stm32h7x.cfg`를 해당 패밀리용 타깃 설정으로 바꿉니다.
6. 이 README의 제목과 개요를 새 펌웨어 프로젝트에 맞게 바꾸고, 사용자에게
   필요한 설정 안내만 유지합니다.
7. 필요하면 `CMakeLists.txt`의 `project(stm32-template ...)` 이름을
   바꿉니다. 이 경우 `.vscode/launch.json`의 `.elf` 경로도 함께 바꿉니다.
8. 설정된 `config.cmake`, `.gitmodules`, submodule 항목, `inc/` 아래에
   생성된 패밀리별 HAL 설정을 프로젝트의 일부로 커밋합니다.

템플릿의 이후 변경사항은 이미 생성된 저장소로 동기화되지 않습니다. 이
템플릿을 시작 시점의 스냅샷으로 생각하세요. 나중에 변경사항을 확인하려면
템플릿을 별도 remote로 추가한 뒤 필요한 변경만 복사하거나 cherry-pick하는
편이 좋습니다. 두 저장소의 이력이 서로 관련이 없으므로 브랜치를 바로
merge하는 방식은 대개 적합하지 않습니다.

## 필수 도구

아래 명령은 Apple Silicon 기반 macOS를 대상으로 합니다. CMake 프로젝트
자체는 다른 호스트에서도 사용할 수 있지만 Git, Python 3, CMake, Make,
Arm GNU Toolchain, 디버그 프로브 도구의 동등한 버전을 설치하고 toolchain 및
디버거 경로를 수정해야 합니다. Windows에서는 제공된 `Makefile`과 shell
helper를 사용하기 위해 WSL 또는 다른 Unix 계열 shell을 쓰는 것이 가장
간단합니다.

**Arm GNU Toolchain.** Homebrew의 `arm-none-eabi-gcc`는 newlib 없이
배포되므로 `printf`가 링크되지 않습니다. Arm 공식 릴리스를 사용하세요.

```sh
brew install --cask gcc-arm-embedded          # .pkg 설치에 sudo 필요
```

sudo 없이 설치하려면 같은 릴리스의 tarball을 풀어도 됩니다.

```sh
mkdir -p ~/.local/opt && cd ~/.local/opt
V=15.3.rel1
curl -LO "https://gitlab.arm.com/api/v4/projects/tooling%2Fgnu-toolchains-for-arm/packages/generic/gnu-toolchain/$V/arm-gnu-toolchain-$V-darwin-arm64-arm-none-eabi.tar.xz"
tar xf arm-gnu-toolchain-$V-darwin-arm64-arm-none-eabi.tar.xz
```

그다음 `config.cmake`의 `ARM_TOOLCHAIN_BIN`을 설치한 toolchain의 `bin`
디렉터리로 지정하세요. 해당 디렉터리를 `PATH`에 추가했다면 이 변수는
비워도 됩니다.

**그 밖의 도구:**

```sh
brew install cmake stlink       # stlink에는 st-flash와 st-util 포함
brew install open-ocd           # 선택 사항, OpenOCD 디버깅에만 필요
code --install-extension marus25.cortex-debug
```

`python3`, `git`, `make`도 필요합니다. `setup.py`를 처음 실행할 때는 ST
저장소 확인, CMSIS-Pack 데이터 다운로드, submodule 가져오기를 위한 네트워크
연결이 필요합니다. 설정을 마친 뒤의 빌드는 오프라인으로 실행됩니다.

## 빠른 시작

```sh
git clone --recurse-submodules <생성한 저장소 URL> PROJECT
cd PROJECT
$EDITOR config.cmake            # 예제 BOARD/MCU와 console 값을 교체
python3 tools/setup.py          # submodule을 가져오고 파생 값을 채움
make                            # 빌드
make flash                      # st-flash로 칩에 기록
```

그다음 console UART를 115200 8N1로 설정해 시리얼 터미널을 열고 보드를
reset합니다.

```sh
ls /dev/tty.*
screen /dev/tty.usbserial-XXXX 115200      # 종료: Ctrl-A K
```

```
Hello, World!
board  CoreH743I (STM32H743IITx)
sysclk 64000000 Hz, pclk1 64000000 Hz
tick: 1
tick: 2
```

## config.cmake

일반적으로 수정해야 하는 유일한 파일입니다. 일부 값은 사용자가 설정하고
나머지는 `tools/setup.py`가 채웁니다. 스크립트는 값이 **비어 있을 때만**
쓰기 때문에 직접 입력한 값은 유지됩니다. 파생 값을 다시 계산하려면 해당
값을 비운 뒤 `setup.py`를 다시 실행하세요.

### Toolchain

| 변수 | 설정 주체 | 의미 |
|---|---|---|
| `ARM_TOOLCHAIN_BIN` | 사용자 | Arm toolchain의 `bin` 디렉터리. 비우면 `PATH`에 있는 `arm-none-eabi-gcc`를 사용합니다. |

### 타깃

| 변수 | 설정 주체 | 의미 |
|---|---|---|
| `BOARD` | 사용자 | `setup.py --list-boards`에 나오는 이름 또는 자유 형식의 이름. `MCU`가 비어 있고 알려진 보드라면 `MCU`와 console pin을 채웁니다. |
| `MCU` | 사용자 또는 `BOARD` | 전체 부품 번호(예: `STM32H743IITx`). 끝에 온도 등급 숫자가 붙어도 됩니다(`STM32H743IIT6`). |

`MCU`를 직접 설정하는 방식은 모든 STM32에서 동작합니다. 보드 표는 일부
보드를 위한 단축 기능일 뿐입니다.

### 메모리

다음 값은 모두 CMSIS-Pack에서 채웁니다. 일반적으로 직접 수정할 필요가
없습니다.

| 변수 | 의미 |
|---|---|
| `FLASH_ORIGIN` | 보통 `0x08000000`. bootloader 뒤에 애플리케이션을 배치하려면 변경합니다. |
| `FLASH_SIZE` | 연속된 flash 크기. 서로 맞닿은 bank는 합치므로 STM32H743의 1 MB bank 두 개는 `2048K`가 됩니다. |
| `RAM_ORIGIN` | linker script에서 사용하는 RAM 블록의 시작 주소. |
| `RAM_SIZE` | 해당 블록의 크기. 서로 맞닿은 영역은 합치므로 STM32U575의 SRAM1+2+3은 `768K`가 됩니다. |
| `RAM_REGION` | 비어 있으면 pack에서 `0x20000000`에 배치한 영역을 선택합니다. 다른 영역을 사용하려면 이름을 지정합니다. |

`RAM_REGION`의 동작은 알아둘 필요가 있습니다. 기본값은 가장 큰 영역이
아닙니다. STM32H743의 경우 pack에는 `DTCMRAM`(128K), `RAM_D1`(512K),
`RAM_D2`(288K), `RAM_D3`(64K)가 들어 있는데, 가장 큰 영역을 고르는 것이
오히려 잘못인 경우가 많습니다. 모든 STM32에서 `0x20000000`에 있는 영역은
TCM 또는 main SRAM이며 reset 직후부터 사용할 수 있습니다. 반면 `RAM_D2`와
`RAM_D3`는 먼저 RCC clock을 활성화해야 하므로 바로 점프하면 프로그램이
멈춥니다. `setup.py`는 찾은 모든 영역을 출력합니다.

```cmake
set(RAM_REGION "RAM_D1")     # RAM_ORIGIN과 RAM_SIZE를 비운 뒤 setup.py 재실행
```

### Console

어떤 UART가 USB-serial bridge와 연결되는지는 보드 배선에 따라 달라지므로
자동으로 알아낼 수 없습니다. `setup.py pins`는 데이터시트에서 직접 찾기
번거로운 alternate-function 번호와 함께 칩에서 사용할 수 있는 pin을
보여 줍니다.

```
$ python3 tools/setup.py pins UART4
  UART4      TX PA0(AF8) PA12(AF6) PB9(AF8) PC10(AF8) PD1(AF8) PH13(AF8)
             RX PA1(AF8) PA11(AF6) PB8(AF8) PC11(AF8) PD0(AF8) PH14(AF8) PI9(AF8)
```

AF 번호가 같은 TX/RX 조합을 선택하세요. AF는 주변장치가 아니라 pin마다
정해진다는 점에 주의하세요. 예를 들어 UART4는 PH13에서 AF8이지만 PA12에서는
AF6입니다.

| 변수 | 의미 |
|---|---|
| `CONSOLE_UART` | 주변장치 instance(예: `UART4`, `USART2`, `LPUART1`). |
| `CONSOLE_TX` / `CONSOLE_RX` | `P<port><number>` 형식의 pin(예: `PH13`). |
| `CONSOLE_AF` | alternate-function 번호만 입력(예: `8`). `board.h`가 `GPIO_AF8_UART4`로 변환합니다. |
| `CONSOLE_BAUD` | 기본값 115200. HAL이 실제 PCLK에서 divisor를 계산하므로 PLL을 추가해도 올바른 값이 유지됩니다. |

### 보드 clock

| 변수 | 의미 |
|---|---|
| `HSE_HZ` | 보드에 실장된 crystal의 주파수. HAL에는 `HSE_VALUE`로 전달됩니다. |

이 값은 칩이 아니라 보드의 속성이므로 CMSIS-Pack은 알 수 없습니다. HAL
헤더의 기본값도 추정값입니다(STM32H7은 25 MHz). `SystemClock_Config`를
작성하기 전에는 사용하지 않지만, 값이 잘못된 상태에서 clock을 설정하면
system clock이 잘못 계산되고 console 출력이 깨집니다.

### 디바이스

| 변수 | 의미 |
|---|---|
| `FAMILY` | `H7`, `G0` 등. submodule 디렉터리 이름을 결정합니다. |
| `DEVICE_DEFINE` | 예: `STM32H743xx`. CMSIS 헤더와 startup 파일을 선택합니다. |
| `CPU_FLAGS` | 예: `-mcpu=cortex-m7 -mthumb -mfpu=fpv5-d16 -mfloat-abi=hard`. |

세 값은 모두 pack에서 가져옵니다. 특별한 설정이 필요하면 `CPU_FLAGS`를
직접 덮어쓸 수 있습니다.

### 추가 라이브러리

| 변수 | 의미 |
|---|---|
| `EXTRA_LIB_DIRS` | 컴파일할 디렉터리. 각 디렉터리의 `*.c`를 찾고 `Inc`/`Include`를 include path에 추가합니다. `setup.py add`가 관리합니다. |

### 작성 규칙

`tools/setup.py`는 행 단위 parser로 이 파일을 읽고 다시 쓰므로 한 줄짜리
일반 `set()` 형식을 사용해야 합니다.

- 한 줄에 `set()` 하나만 쓰고 여러 줄로 나누지 않기
- 값 안에 `)`를 넣지 않기
- `if()` / `foreach()`를 쓰지 않기: parser는 모든 `set()`을 조건과
  관계없이 읽으므로 잘못 해석할 수 있음
- 뒤쪽의 `#` 주석은 값 재작성 시에도 보존됨
- 빈 값은 `set(X "")` 또는 `set(X)`
- `$ENV{HOME}` 같은 CMake 표현식은 사용 가능: `setup.py`는 그대로 두고
  CMake가 확장함

## 칩 또는 보드 변경

`config.cmake`에는 동작하는 `CoreH743I` 예제가 들어 있습니다.
`setup.py --list-boards`에 있는 보드를 선택하려면 `BOARD`를 설정하고
`MCU`, console 필드, 파생 필드를 비우세요. `setup.py`는 `MCU`가 비어 있을
때만 보드 기본값을 채웁니다.

```cmake
set(BOARD "NUCLEO-F411RE")
set(MCU "")
set(FLASH_ORIGIN "")
set(FLASH_SIZE "")
set(RAM_ORIGIN "")
set(RAM_SIZE "")
set(RAM_REGION "")
set(FAMILY "")
set(DEVICE_DEFINE "")
set(CPU_FLAGS "")
set(CONSOLE_UART "")
set(CONSOLE_TX "")
set(CONSOLE_RX "")
set(CONSOLE_AF "")
```

MCU를 직접 지정하려면 `MCU`를 설정하고, `BOARD`는 알아보기 쉬운 이름으로
바꾸거나 비우세요. 같은 파생 필드를 비운 뒤 `setup.py pins`를 참고해
console 필드는 직접 설정합니다. 두 경우 모두 `HSE_HZ`를 검토하세요. 이
값은 보드 속성이므로 `setup.py`가 의도적으로 자동 계산하지 않습니다.

그다음 다시 생성하고 빌드합니다.

```sh
python3 tools/setup.py          # 새 패밀리를 가져오고 빈 값을 다시 채움
python3 tools/setup.py pins     # console pin 선택을 확인
make clean && make
```

예전 패밀리의 submodule은 남아 있습니다. 다시 사용할 계획이 없다면 아래
설명을 참고해 제거하세요.

`tools/try_board.sh`는 이 작업을 임시 복사본에서 모두 실행합니다. 칩을
실제 프로젝트에 반영하기 전에 가장 빠르게 확인할 수 있는 방법입니다.

```sh
tools/try_board.sh NUCLEO-F411RE
tools/try_board.sh "" STM32G071RBTx
```

## 라이브러리 추가

예제, BSP, middleware는 크기가 크고 대부분의 프로젝트에 필요하지 않으므로
기본으로 가져오지 않습니다.

```sh
python3 tools/setup.py add cube                 # 전체 STM32Cube<FAM> 저장소, shallow
python3 tools/setup.py add https://github.com/STMicroelectronics/stm32h7xx-nucleo-bsp
```

각 저장소는 `lib/` 아래에 들어가고 `EXTRA_LIB_DIRS`에 추가됩니다. 그 뒤
해당 디렉터리의 `*.c` 파일을 컴파일하고 `Inc`/`Include`를 include path에
추가합니다.

제거하려면 다음 명령을 사용합니다.

```sh
git rm lib/<name>          # --cached를 쓰면 .gitmodules 항목이 남으므로 사용 금지
```

그다음 `EXTRA_LIB_DIRS`에서도 해당 항목을 제거하세요.

## 빌드, 플래시, 디버그

```sh
make                # 필요하면 configure한 뒤 빌드
make clean
make flash          # st-flash --reset write build/stm32-template.bin <FLASH_ORIGIN>
```

출력 파일은 `build/` 아래에 생성됩니다. `.elf`, `.hex`, `.bin`, `.map`, 생성된
linker script와 `compile_commands.json`이 포함됩니다.

기본 build type은 `Debug`입니다. 이를 지정하지 않으면 CMake는 `-O`와 `-g`
모두 전달하지 않으므로 debugger에서 변수를 볼 수 없습니다.

```sh
cmake -S . -B build -DCMAKE_BUILD_TYPE=MinSizeRel     # 16 KB 대신 11 KB
```

`-g`에는 macro 정의가 들어 있지 않으므로 gdb에서 `print GPIO_PIN_13`은
실패합니다. 이 기능이 필요하면
`-DCMAKE_C_FLAGS_DEBUG="-g3 -O0"`로 빌드하세요.

### VSCode

Task는 **build**(기본 build task), **clean**, **flash**, **setup**이 있습니다.

디버깅에는 Cortex-Debug extension이 필요합니다. F5를 누르면 다음 구성을
선택할 수 있습니다.

- **Debug (st-util)** — 추가 설치 불필요, `st-util`은 `stlink`에 포함
- **Debug (OpenOCD)** — `brew install open-ocd` 필요
- **Attach (st-util, no reset)** — 실행 중인 타깃을 다시 프로그래밍하지 않고
  연결

두 launch 구성 모두 다시 빌드하고 프로그래밍한 뒤 `main`에서 멈춥니다.

제공된 OpenOCD launch 구성은 `target/stm32h7x.cfg`를 사용합니다. 선택한
타깃이 STM32H7이 아니라면 이 파일 이름을 바꾸세요. `st-util` 구성에는 이와
같은 패밀리별 설정이 없습니다.

`.vscode/settings.json`에는 `config.cmake`와 같은 toolchain 경로가
`cortex-debug.armToolchainPath`와 `cortex-debug.gdbPath`에 반복되어 있습니다.
VSCode 설정은 CMake 파일을 읽을 수 없으므로 toolchain을 옮기면 두 곳을 모두
수정해야 합니다.

## 애플리케이션 구성

`src/main.c`에는 패밀리, port, pin 이름이 직접 들어 있지 않습니다.
`config.cmake`의 값을 사용해 `cmake/board.h.in`으로부터 `build/board.h`를
생성합니다.

```c
#include "stm32h7xx_hal.h"
#define CONSOLE_UART              UART4
#define CONSOLE_AF                GPIO_AF8_UART4
#define CONSOLE_TX_PORT           GPIOH
#define CONSOLE_TX_PIN            GPIO_PIN_13
#define CONSOLE_TX_CLK_ENABLE()   __HAL_RCC_GPIOH_CLK_ENABLE()
```

두 드라이버 세트를 모두 컴파일한 뒤 `--gc-sections`가 사용하지 않는 부분을
제거합니다. HAL 및 LL object 123개가 들어가고, 예제는 그중 14개 symbol만
링크합니다. 필요한 LL 헤더를 직접 include하면 됩니다.

```c
#include "stm32h7xx_ll_gpio.h"
```

`USE_HAL_DRIVER`와 `USE_FULL_LL_DRIVER`가 모두 정의되어 있습니다.

### 예제가 의도적으로 선택한 동작

**PLL 없음.** STM32H743의 reset clock인 64 MHz HSI로 동작합니다. Clock
tree는 STM32마다 다르므로 reset 상태가 모든 칩에서 부팅되는 유일한
설정입니다. 더 높은 속도가 필요하면 직접 `SystemClock_Config`를 작성하세요.
`HSE_HZ`에는 제공된 `CoreH743I` 예제에 맞는 값이 들어 있으므로 자신의
보드에서는 다시 확인해야 합니다.

**`main.c`의 `SysTick_Handler`.** CMSIS startup 파일은 모든 handler를
무한 루프인 `Default_Handler`의 alias로 선언하고, HAL은 프로젝트가
`HAL_IncTick`을 호출할 것으로 기대합니다. 이 코드가 없으면 첫
`HAL_Delay`가 반환되지 않습니다. 다른 interrupt handler도 이 코드 옆에
추가하세요.

**`setvbuf(stdout, NULL, _IONBF, 0)`.** newlib은 `_isatty`에 stdout이
terminal인지 묻지만 `nosys`는 아니라고 답합니다. 따라서 이 설정이 없으면
stdout이 완전히 buffering되어 1 KB가 쌓일 때까지 아무것도 출력되지
않습니다. Buffering을 끄면 fault로 한 줄이 중간에 끊겨도 전송된 부분까지는
확인할 수 있습니다.

**`tick`과 `startup_error`는 file scope의 `volatile` 변수.** Console이
동작하지 않을 때는 점멸시킬 LED도 출력할 곳도 없으므로 debugger에서 이
변수를 읽어 "프로그램이 실행되지 않음"과 "실행 중이지만 UART 설정이
잘못됨"을 구분할 수 있습니다.

## 데이터 출처

| 항목 | 출처 |
|---|---|
| CMSIS core | `github.com/STMicroelectronics/cmsis-core` |
| 디바이스 헤더, startup | `github.com/STMicroelectronics/cmsis-device-<fam>` |
| HAL 및 LL 드라이버 | `github.com/STMicroelectronics/stm32<fam>xx-hal-driver` |
| 메모리 맵, 디바이스 define, core/FPU | `keil.com/pack/Keil.STM32<FAM>xx_DFP.pdsc` |
| Console pin과 AF 후보 | `github.com/STMicroelectronics/STM32_open_pin_data` |

마지막 두 항목은 `setup.py`만 읽으며, 찾은 내용은 `config.cmake`에
기록됩니다. 빌드할 때는 네트워크가 필요하지 않습니다.

CMSIS 헤더만으로는 충분하지 않습니다. Base address는 있지만 크기는 없고,
헤더의 `FLASH_SIZE`는 linker가 사용할 수 없는 flash size register의 runtime
read입니다. `FLASH_END`는 디바이스 *line*의 최댓값이므로 STM32H723 헤더는
512 KB 부품에서도 1 MB라고 표시합니다. ST는 일부 패밀리에만 완성된 linker
script를 제공합니다. CMSIS-Pack에는 CubeMX도 사용하는 실제 디바이스별
메모리 맵이 들어 있습니다.

## 제한 사항

- `setup.py`는 오프라인 fallback으로만 부품 번호에서 flash 크기를
  계산하며, 이 fallback은 STM32H7RS 또는 STM32N6 명명 규칙을 이해하지
  못합니다. Pack에 연결할 수 있으면 이 fallback은 사용하지 않습니다.
- 보드 표에는 네 항목만 있습니다. 다른 보드는 `MCU`와 console pin을 직접
  설정해야 하며, 번거로운 pin 확인은 `setup.py pins`가 처리합니다.
- linker script에는 RAM 영역 하나만 전달됩니다. STM32H7의 다른 SRAM이나
  외부 SDRAM을 사용하려면 `cmake/stm32_flash.ld.in`에 직접 추가해야 합니다.
- VSCode extension은 묻지 않고 `.vscode/*.json`을 다시 쓰기도 합니다. C/C++
  extension에서 C 파일의 Run 버튼을 누르면 host-clang task를 추가하고 기본
  build task를 바꿀 수 있습니다. 이를 막기 위해 여기서는
  `C_Cpp.debugShortcut`을 꺼 두었습니다. 커밋하기 전에 `git diff`를
  확인하세요.

## 라이선스

현재 이 저장소에는 프로젝트 라이선스가 명시되어 있지 않습니다. 다른
사람이 이 템플릿을 사용, 수정, 재배포할 수 있게 하려면 라이선스를 선택해
`LICENSE` 파일을 추가하세요. 각 STMicroelectronics submodule에는 해당
upstream 저장소의 라이선스가 그대로 적용됩니다. 프로젝트 수준의
라이선스가 vendor 라이선스를 대체하지 않습니다.
