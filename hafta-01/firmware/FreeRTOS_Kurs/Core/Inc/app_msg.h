/**
 * @file    app_msg.h
 * @brief   Ortak TX kuyruğu ve kuyruk öğesi (QUE-01; tasarım §5).
 *
 * Kuyruğa YALNIZCA TelemetryTask (TEL) ve ButtonTask (BTN) yazar.
 * Kontrol/döküm çerçevelerini UartTxTask doğrudan gönderir (tasarım §1).
 */
#ifndef APP_MSG_H
#define APP_MSG_H

#include <stdint.h>
#include "app_frame.h"

typedef enum { MSG_TEL = 1, MSG_BTN = 2 } msg_type_t;

typedef struct {
    uint8_t  type;              /* msg_type_t */
    uint8_t  scn;               /* 0..5 */
    uint16_t event_id;          /* BTN için; TEL'de 0 (TIM-02b) */
    char     frame[FRAME_LEN];  /* hazır, dolgulu, '\n' ile biten çerçeve */
} tx_item_t;                    /* 68 bayt */

#ifndef UNIT_TEST
#include "FreeRTOS.h"
#include "queue.h"
extern QueueHandle_t g_txq;
#endif

#endif /* APP_MSG_H */
