/**
 * @file    app_uart_tx.c
 * @brief   UartTxTask gövdesi (tasarım §7).
 *
 * ŞU AN İSKELET: tag'i ayarlar, açılış öz-testlerini koşar ve bekler.
 * Asıl davranış uygulama adımı 4 (kuyruk + UartTxTask) içinde yazılacak.
 */
#include "FreeRTOS.h"
#include "task.h"
#include "app_tasks.h"
#include "app_selftest.h"

void StartUartTxTask(void *argument)
{
    (void)argument;
    APP_SET_OWN_TAG(APP_TAG_UART_TX);

    /* Açılış öz-testleri (T19, T20). En düşük öncelikli görevde: diğer görevleri bekletmez. */
    app_selftest_run();

    for (;;) {
        vTaskDelay(pdMS_TO_TICKS(1000));
    }
}
