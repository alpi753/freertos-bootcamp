/**
 * @file    app_tasks.h
 * @brief   Uygulama görevlerinin giriş fonksiyonları ve görev kimlikleri.
 *
 * Görevler CubeMX'te "As external" olarak tanımlıdır (tasarım §3 C-6, §5):
 * CubeMX yalnızca osThreadNew çağrısını ve extern bildirimini üretir,
 * gövdeler app_telemetry.c / app_button.c / app_uart_tx.c içindedir.
 */
#ifndef APP_TASKS_H
#define APP_TASKS_H

#include <stdint.h>

/* Görev kimlikleri (FreeRTOS application task tag).
 * Görev değiştirme kancaları hangi görevin CPU'ya girip çıktığını
 * bu değerle anlar (tasarım §8.2). 0 = idle, timer gibi "diğer" görevler. */
typedef enum {
    APP_TAG_OTHER     = 0,
    APP_TAG_TELEMETRY = 1,
    APP_TAG_BUTTON    = 2,
    APP_TAG_UART_TX   = 3,
} app_task_tag_t;

/* Görevin kendi tag'ini ayarlar; her görevin ilk satırında çağrılır. */
#define APP_SET_OWN_TAG(tag) \
    vTaskSetApplicationTaskTag(NULL, (TaskHookFunction_t)(uintptr_t)(tag))

void StartTelemetryTask(void *argument);
void StartButtonTask(void *argument);
void StartUartTxTask(void *argument);

#endif /* APP_TASKS_H */
