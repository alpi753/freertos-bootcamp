/**
 * @file    app_config.h
 * @brief   Derleme zamanı sabitleri, senaryo tablosu ve test bayrakları.
 */
#ifndef APP_CONFIG_H
#define APP_CONFIG_H

#include <stdint.h>

/* ---- Kuyruk ve zaman aşımları (tasarım §5, §7) ------------------------- */
/* TXQ_DEPTH aşağıda, test bayraklarından sonra tanımlıdır. */
#define BTN_SEND_TIMEOUT_MS    10u   /* QUE-03 */
#define UART_TX_TIMEOUT_MS     20u   /* bir çerçeve hatta ~5,6 ms; 20 ms = güvenli üst sınır */
#define UART_RX_POLL_MS        10u   /* kuyruk boşken komutların en geç işlenme süresi */
#define RX_RING_SIZE           128u  /* 2'nin kuvveti olmalı */
#define CMD_LINE_MAX           63u   /* MSG-07 */

/* ---- Senaryolar (tasarım §6, gereksinim §6) ---------------------------- */
typedef struct {
    uint16_t period_ms;   /* 0 = telemetri kapalı */
    uint16_t load_us;     /* TelemetryTask içindeki CPU işi (adım 8) */
} scn_cfg_t;

#define SCN_COUNT  6u
extern const scn_cfg_t SCN_TABLE[SCN_COUNT];

/* ---- Test bayrakları (test planı §3). Ölçüm derlemelerinde HEPSİ 0. ---- */
#ifndef TEST_FORCE_QFULL
#define TEST_FORCE_QFULL   0
#endif
#ifndef TEST_MEAS_CAP
#define TEST_MEAS_CAP      0
#endif
#ifndef TEST_LONG_FRAME
#define TEST_LONG_FRAME    0
#endif
#ifndef TEST_STACK_OVF
#define TEST_STACK_OVF     0
#endif
/* QUE-04: kuyruk derinliği derleme zamanı sabiti. TC-T13'te bilerek küçültülür. */
#if TEST_FORCE_QFULL
#define TXQ_DEPTH   2u
#define QFULL_TX_DELAY_MS  50u   /* UartTxTask her çerçeveden sonra bekler → kuyruk dolar */
#else
#define TXQ_DEPTH  16u
#endif

/* VER çerçevesindeki bit maskesi (tasarım §9) */
#define APP_TEST_FLAGS  ((TEST_FORCE_QFULL ? 1u : 0u) | (TEST_MEAS_CAP ? 2u : 0u) | \
                         (TEST_LONG_FRAME  ? 4u : 0u) | (TEST_STACK_OVF ? 8u : 0u) | \
                         (TEST_STACK_OVF == 2 ? 0x10u : 0u))
/* TEST_STACK_OVF: 1 = büyük taşma (1 KB dizi, TCB'yi de bozar), 2 = küçük taşma
 * (stack yalnızca dipteki koruma desenine kadar kullanılır). TC-T18a / T18b. */

#endif /* APP_CONFIG_H */
