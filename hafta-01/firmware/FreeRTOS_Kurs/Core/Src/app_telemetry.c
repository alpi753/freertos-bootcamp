/**
 * @file    app_telemetry.c
 * @brief   TelemetryTask gövdesi (tasarım §7).
 *
 * ŞU AN İSKELET: görev yalnızca kendi tag'ini ayarlar ve bekler.
 * Asıl davranış uygulama adımı 4 (kuyruk + UartTxTask) ve 8 (ADC, CPU yükü) içinde yazılacak.
 */
#include "FreeRTOS.h"
#include "task.h"
#include "app_tasks.h"

void StartTelemetryTask(void *argument)
{
    (void)argument;
    APP_SET_OWN_TAG(APP_TAG_TELEMETRY);

    for (;;) {
        vTaskDelay(pdMS_TO_TICKS(1000));
    }
}
