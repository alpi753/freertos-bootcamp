/**
 * @file    app_button.c
 * @brief   ButtonTask gövdesi (tasarım §7).
 *
 * ŞU AN İSKELET: görev yalnızca kendi tag'ini ayarlar ve bekler.
 * Asıl davranış uygulama adımı 5 (ButtonTask + ISR) içinde yazılacak.
 */
#include "FreeRTOS.h"
#include "task.h"
#include "app_tasks.h"

void StartButtonTask(void *argument)
{
    (void)argument;
    APP_SET_OWN_TAG(APP_TAG_BUTTON);

    for (;;) {
        vTaskDelay(pdMS_TO_TICKS(1000));
    }
}
