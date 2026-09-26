/**
 * @file    app_cmd.h
 * @brief   PC → MCU komutları: ayrıştırma ve durum kontrolü (MSG-07/08; tasarım §7.5).
 *
 * Bu modül saf C'dir (HAL/FreeRTOS yok) ve PC'de test edilir (TC-U05).
 * Komutları uygulayan kod UartTxTask'tadır (app_uart_tx.c).
 */
#ifndef APP_CMD_H
#define APP_CMD_H

#include <stdint.h>

typedef enum { RUN_IDLE = 0, RUN_RUNNING = 1, RUN_STOPPED = 2 } run_state_t;

typedef enum {
    CMD_SCN, CMD_START, CMD_STOP, CMD_DUMP,
    CMD_BAD_ARG,     /* tanınan komut, geçersiz argüman */
    CMD_UNKNOWN,
} cmd_id_t;

typedef struct {
    cmd_id_t id;
    uint8_t  arg;    /* CMD_SCN için 0..5 */
} cmd_t;

typedef enum { RES_ACK, RES_NAK_BUSY, RES_NAK_STATE, RES_NAK_ARG, RES_NAK_CMD } cmd_result_t;

/** Tek bir satırı (sonundaki '\r' / '\n' temizlenmiş) ayrıştırır. */
cmd_t cmd_parse(const char *line);

/** Komut o durumda kabul edilir mi? (tasarım §7.5 tablosu) */
cmd_result_t cmd_check(cmd_t cmd, run_state_t state);

/** NAK sonucunun metni: "BUSY", "STATE", "ARG", "CMD" (ACK için NULL). */
const char *cmd_nak_text(cmd_result_t r);

#endif /* APP_CMD_H */
