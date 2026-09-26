/**
 * @file    app_uart_tx.c
 * @brief   UartTxTask gövdesi (tasarım §7).
 *
 * ŞU AN İSKELET: görev yalnızca kendi tag'ini ayarlar ve bekler.
 * Asıl davranış uygulama adımı 4 (kuyruk + UartTxTask) içinde yazılacak.
 */
#include "FreeRTOS.h"
#include "task.h"
#include "app_tasks.h"

void StartUartTxTask(void *argument)
{
    (void)argument;
    APP_SET_OWN_TAG(APP_TAG_UART_TX);

    for (;;) {
        vTaskDelay(pdMS_TO_TICKS(1000));
    }
}
