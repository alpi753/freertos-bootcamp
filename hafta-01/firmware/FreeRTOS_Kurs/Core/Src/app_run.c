/**
 * @file    app_run.c
 * @brief   Koşu durumu, senaryo tablosu, sayaçlar ve TX kuyruğu.
 */
#include <string.h>
#include "app_run.h"
#include "app_config.h"
#include "app_msg.h"
#include "app_meas.h"

const scn_cfg_t SCN_TABLE[SCN_COUNT] = {
    {   0,    0 },   /* S0  telemetri kapalı        */
    { 100,    0 },   /* S1  10 Hz                   */
    {  20,    0 },   /* S2  50 Hz                   */
    {  10,    0 },   /* S3  100 Hz                  */
    {  10, 2000 },   /* S4  100 Hz + ≈2 ms CPU işi  */
    {  10, 5000 },   /* S5  100 Hz + ≈5 ms CPU işi  */
};

QueueHandle_t g_txq;

volatile run_state_t    g_run_state = RUN_IDLE;
volatile uint8_t        g_run_scn   = 0;          /* SCN-03: açılışta S0 */
volatile uint32_t       g_run_id    = 0;
volatile run_counters_t g_cnt;

static TaskHandle_t s_tel_task;

void app_rtos_objects_create(void)
{
    g_txq = xQueueCreate(TXQ_DEPTH, sizeof(tx_item_t));
    configASSERT(g_txq != NULL);                   /* SYS-03 */
    vQueueAddToRegistry(g_txq, "txQueue");         /* hata ayıklayıcıda adıyla görünsün */
}

void run_register_telemetry(TaskHandle_t h) { s_tel_task = h; }

void run_set_scenario(uint8_t scn)
{
    if (scn < SCN_COUNT) g_run_scn = scn;
}

void run_start(void)
{
    taskENTER_CRITICAL();
    memset((void *)&g_cnt, 0, sizeof g_cnt);
    meas_reset();                                  /* kayıtlar ve olay sayacı */
    g_frame_err = 0;                               /* SUM'daki diğer sayaçlar gibi koşu başına */
    g_run_id++;
    g_run_state = RUN_RUNNING;
    taskEXIT_CRITICAL();
    if (s_tel_task) xTaskNotifyGive(s_tel_task);
}

void run_stop(void)
{
    g_run_state = RUN_STOPPED;
}

void run_qhw_update(void)
{
    UBaseType_t used = uxQueueMessagesWaiting(g_txq);
    taskENTER_CRITICAL();
    if (used > g_cnt.q_hw) g_cnt.q_hw = (uint8_t)used;
    taskEXIT_CRITICAL();
}
