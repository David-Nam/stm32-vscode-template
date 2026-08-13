/* Hello world over the console UART.
 *
 * Runs on the reset clock (HSI, no PLL). That is deliberate: the clock tree
 * differs on every STM32, so staying at the reset state is the one setting
 * that boots everywhere. The baud rate is derived from the live PCLK by the
 * HAL, so it stays correct once you do configure a PLL.
 */
#include <stdio.h>
#include "board.h"
#ifdef RTOS_FREERTOS
#include "FreeRTOS.h"
#include "task.h"
#endif

static UART_HandleTypeDef console;

/* Nothing to blink and nothing to print on when the console itself fails, so
 * park the reason here where a debugger can read it. */
volatile uint32_t startup_error;

static void console_init(void)
{
    CONSOLE_TX_CLK_ENABLE();
    CONSOLE_RX_CLK_ENABLE();
    CONSOLE_UART_CLK_ENABLE();

    GPIO_InitTypeDef gpio = {
        .Mode = GPIO_MODE_AF_PP,
        .Pull = GPIO_PULLUP,
        .Speed = GPIO_SPEED_FREQ_VERY_HIGH,
        .Alternate = CONSOLE_AF,
    };
    gpio.Pin = CONSOLE_TX_PIN;
    HAL_GPIO_Init(CONSOLE_TX_PORT, &gpio);
    gpio.Pin = CONSOLE_RX_PIN;
    HAL_GPIO_Init(CONSOLE_RX_PORT, &gpio);

    console.Instance = CONSOLE_UART;
    console.Init.BaudRate = CONSOLE_BAUD;
    console.Init.WordLength = UART_WORDLENGTH_8B;
    console.Init.StopBits = UART_STOPBITS_1;
    console.Init.Parity = UART_PARITY_NONE;
    console.Init.Mode = UART_MODE_TX_RX;
    console.Init.HwFlowCtl = UART_HWCONTROL_NONE;
    console.Init.OverSampling = UART_OVERSAMPLING_16;
    if (HAL_UART_Init(&console) != HAL_OK) {
        startup_error = 1;
        for (;;) {
        }
    }
}

/* The CMSIS startup file aliases every handler to Default_Handler, which is an
 * infinite loop. HAL_Delay and every HAL timeout count on this one, so without
 * it the first HAL_Delay never returns. Add further IRQ handlers here.
 * With an RTOS the kernel owns this vector and HAL_IncTick moves to the tick
 * hook below. */
#ifndef RTOS_FREERTOS
void SysTick_Handler(void)
{
    HAL_IncTick();
}
#endif

/* newlib routes printf and puts through here. */
int _write(int fd, char *data, int len)
{
    (void)fd;
    if (HAL_UART_Transmit(&console, (uint8_t *)data, len, HAL_MAX_DELAY) != HAL_OK) {
        return -1;
    }
    return len;
}

/* TODO: PLL setup goes here when you need more than the reset clock. The
 * crystal frequency is HSE_HZ in config.cmake, which reaches the HAL as
 * HSE_VALUE -- the header's own default is 25 MHz and would be wrong here. */

/* File scope and volatile so a debugger can watch it when the UART is silent. */
volatile uint32_t tick;

#ifdef RTOS_FREERTOS
/* The kernel tick and the HAL tick are the same 1 kHz SysTick interrupt, so
 * HAL_Delay and every HAL timeout keep working once the scheduler runs. */
void vApplicationTickHook(void)
{
    HAL_IncTick();
}

/* configCHECK_FOR_STACK_OVERFLOW: this task wrote past its stack. Its own
 * state is already gone and printing from here would only spread the damage,
 * so park with the name where a debugger can read it. */
volatile char *overflowed_task;

void vApplicationStackOverflowHook(TaskHandle_t task, char *name)
{
    (void)task;
    overflowed_task = name;
    taskDISABLE_INTERRUPTS();
    for (;;) {
    }
}

/* One task prints, on purpose: newlib's printf is not reentrant here, so a
 * second task calling it needs a mutex around every call. */
static void hello_task(void *arg)
{
    (void)arg;
    for (;;) {
        printf("tick: %lu   heap free: %u\r\n", (unsigned long)++tick,
               (unsigned)xPortGetFreeHeapSize());
        vTaskDelay(pdMS_TO_TICKS(1000));
    }
}
#endif

int main(void)
{
    SystemCoreClockUpdate();
    HAL_Init();
#ifdef RTOS_FREERTOS
    /* HAL_Init starts SysTick, but the vector belongs to the kernel now and
     * its handler only works once the scheduler is up. Park the timer until
     * vTaskStartScheduler re-arms it. Nothing ticks in between, so anything
     * that waits on HAL_Delay belongs in a task, not here. */
    SysTick->CTRL = 0;
#endif
    console_init();

    /* newlib asks _isatty whether stdout is a terminal. nosys says no, so it
     * would full-buffer and hold output back until 1 KB had piled up. Going
     * unbuffered also means a line that is cut short by a fault still shows
     * the part that got out. */
    setvbuf(stdout, NULL, _IONBF, 0);

    printf("\r\nHello, World!\r\n");
    printf("board  %s (%s)\r\n", BOARD_NAME, BOARD_MCU);
    printf("sysclk %lu Hz, pclk1 %lu Hz\r\n",
           (unsigned long)SystemCoreClock,
           (unsigned long)HAL_RCC_GetPCLK1Freq());

#ifdef RTOS_FREERTOS
    /* 512 words of stack: printf is the greedy part. Watch what a task really
     * uses with uxTaskGetStackHighWaterMark before trimming it. */
    if (xTaskCreate(hello_task, "hello", 512, NULL, tskIDLE_PRIORITY + 1, NULL) != pdPASS) {
        startup_error = 2;      /* FREERTOS_HEAP_KB in config.cmake is too small */
        for (;;) {
        }
    }
    vTaskStartScheduler();
    startup_error = 3;          /* only reached if the idle task would not fit */
    for (;;) {
    }
#else
    for (;;) {
        HAL_Delay(1000);
        printf("tick: %lu\r\n", (unsigned long)++tick);
    }
#endif
}
