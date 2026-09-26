/**
 * @file    app_run.h
 * @brief   Koşu durumu, senaryo ve sayaçlar (tasarım §6).
 *
 * Durum yalnızca UartTxTask tarafından (komutlarla) değiştirilir; diğer
 * görevler ve ISR'lar okur. Sayaçlar SUM çerçevesinde raporlanır (MSG-06).
 */
#ifndef APP_RUN_H
#define APP_RUN_H

#include <stdint.h>
#include <stdbool.h>
#include "app_cmd.h"
#include "FreeRTOS.h"
#include "task.h"

typedef struct {
    uint32_t tel_sent;       /* kuyruğa yazılabilen TEL */
    uint32_t tel_dropped;    /* kuyruk dolu olduğu için düşürülen TEL (QUE-02) */
    uint16_t btn_dropped;    /* QUE-03 */
    uint16_t events;         /* koşuda kabul edilen buton olayı */
    uint16_t rec_overflow;   /* TIM-03 (adım 6) */
    uint16_t bounce_rej;     /* ISR-03 (adım 5) */
    uint8_t  q_hw;           /* kuyruk en yüksek doluluk (QUE-05) */
} run_counters_t;

extern volatile run_state_t     g_run_state;
extern volatile uint8_t         g_run_scn;
extern volatile uint32_t        g_run_id;     /* her START'ta +1: eski koşunun döngüsü kendini bitirir */
extern volatile run_counters_t  g_cnt;

static inline bool run_is_running(void) { return g_run_state == RUN_RUNNING; }

/** TelemetryTask kendini kaydeder: START onu bildirimle uyandırır. */
void run_register_telemetry(TaskHandle_t h);

/* Yalnızca UartTxTask çağırır */
void run_set_scenario(uint8_t scn);
void run_start(void);    /* sayaçları sıfırlar, RUNNING, TelemetryTask'ı uyandırır */
void run_stop(void);     /* STOPPED */

/** Kuyruğa başarılı yazmadan sonra çağrılır: en yüksek doluluğu günceller. */
void run_qhw_update(void);

/** TX kuyruğunu oluşturur. main.c USER CODE RTOS_QUEUES içinden, görevlerden ÖNCE. */
void app_rtos_objects_create(void);

#endif /* APP_RUN_H */
