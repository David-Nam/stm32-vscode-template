/* Stage 3 build proof: exercises the HAL and an LL driver so both are known to
 * compile and link. Stage 4 replaces this with the hello world app.
 */
#include "board.h"
#include "stm32h7xx_ll_rcc.h"

int main(void)
{
    static LL_RCC_ClocksTypeDef clocks;

    HAL_Init();                          /* stm32h7xx_hal.c */
    LL_RCC_GetSystemClocksFreq(&clocks); /* stm32h7xx_ll_rcc.c */

    for (;;) {
        HAL_Delay(1000);
    }
}
