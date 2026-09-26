/**
 * @file    app_fault.c
 * @brief   Ölümcül hata göstergesi. RTOS ve kesmeler kapalıyken de çalışır
 *          (bekleme DWT çevrim sayacıyla yapılır; HAL_Delay kullanılamaz).
 */
#include "app_fault.h"
#include "main.h"

void app_fault_blink(uint32_t hz)
{
    __disable_irq();
    const uint32_t half = SystemCoreClock / (2u * hz);
    for (;;) {
        HAL_GPIO_TogglePin(LD2_GPIO_Port, LD2_Pin);
        const uint32_t c0 = DWT->CYCCNT;
        while ((DWT->CYCCNT - c0) < half) { }
    }
}
