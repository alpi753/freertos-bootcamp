/**
 * @file    app_uart_tx.c
 * @brief   UartTxTask (en düşük öncelik) — UART'ın TEK sahibi (tasarım §1, §7.4, §7.5).
 *
 *  - TX kuyruğunu FIFO sırasıyla tüketir, her çerçeveyi USART2 DMA ile gönderir
 *    ve TC (Transmission Complete) kesmesini bekler (TSK-06).
 *  - PC'den gelen komut satırlarını işler (RX kesmesi → ring buffer → burada).
 *  - Kontrol/döküm çerçevelerini (VER, ACK/NAK, SUM, END) kuyruğa koymadan
 *    doğrudan gönderir; böylece ölçtüğümüz kuyruk bozulmaz.
 */
#include <stdarg.h>
#include <string.h>
#include "main.h"
#include "FreeRTOS.h"
#include "task.h"
#include "queue.h"
#include "app_tasks.h"
#include "app_config.h"
#include "app_msg.h"
#include "app_run.h"
#include "app_cmd.h"
#include "app_selftest.h"

#if defined(__has_include)
#  if __has_include("build_info.h")
#    include "build_info.h"          /* derleme öncesi adımda üretilir (tasarım §9) */
#  endif
#endif
#ifndef BUILD_GIT_HASH
#define BUILD_GIT_HASH "nogit"
#endif
#ifdef DEBUG
#define BUILD_TYPE "Debug"
#else
#define BUILD_TYPE "Release"
#endif

extern UART_HandleTypeDef huart2;

static TaskHandle_t s_self;
static volatile uint32_t s_tx_errors;     /* DMA başlatılamadı / TC zaman aşımı */

/* ---- RX: tek üretici (ISR) / tek tüketici (görev) ring buffer ---------- */
static uint8_t           s_rx_byte;
static uint8_t           s_rx_ring[RX_RING_SIZE];
static volatile uint16_t s_rx_head;       /* ISR yazar */
static volatile uint16_t s_rx_tail;       /* görev yazar */
static volatile uint32_t s_rx_overflow;

static void rx_arm(void) { (void)HAL_UART_Receive_IT(&huart2, &s_rx_byte, 1); }

void HAL_UART_RxCpltCallback(UART_HandleTypeDef *h)
{
    if (h->Instance != USART2) return;
    uint16_t next = (uint16_t)((s_rx_head + 1u) & (RX_RING_SIZE - 1u));
    if (next != s_rx_tail) { s_rx_ring[s_rx_head] = s_rx_byte; s_rx_head = next; }
    else                   { s_rx_overflow++; }
    rx_arm();                                  /* bir sonraki bayt için yeniden kur */
}

void HAL_UART_ErrorCallback(UART_HandleTypeDef *h)
{
    if (h->Instance != USART2) return;
    rx_arm();                                  /* taşma/gürültü hatasından sonra alımı sürdür */
}

/* ---- TX: DMA + TC ------------------------------------------------------- */
void HAL_UART_TxCpltCallback(UART_HandleTypeDef *h)
{
    /* HAL bunu DMA bittikten SONRA, son baytın stop biti hattan çıkınca (TC) çağırır. */
    if (h->Instance != USART2) return;
    BaseType_t hpw = pdFALSE;
    vTaskNotifyGiveFromISR(s_self, &hpw);
    portYIELD_FROM_ISR(hpw);
}

/** 64 baytlık çerçeveyi gönderir ve hattan tamamen çıkana kadar BLOKLANARAK bekler. */
static void uart_send_frame(const char *frame)
{
    if (HAL_UART_Transmit_DMA(&huart2, (uint8_t *)frame, FRAME_LEN) != HAL_OK) {
        s_tx_errors++;
        return;
    }
    if (ulTaskNotifyTake(pdTRUE, pdMS_TO_TICKS(UART_TX_TIMEOUT_MS)) == 0u) {
        s_tx_errors++;
    }
}

/** Kontrol çerçevesi: kuyruğa girmez, doğrudan gönderilir. */
static void send_ctrl(const char *fmt, ...) __attribute__((format(printf, 1, 2)));
static void send_ctrl(const char *fmt, ...)
{
    static char f[FRAME_LEN];
    va_list ap;
    va_start(ap, fmt);
    bool ok = frame_vbuild(f, fmt, ap);
    va_end(ap);
    if (ok) uart_send_frame(f);
}

static void send_ver(void)
{
    send_ctrl(FMT_VER, BUILD_GIT_HASH, BUILD_TYPE, (unsigned)APP_TEST_FLAGS);
}

static void send_sum(void)
{
    run_counters_t c = g_cnt;                  /* anlık kopya */
    send_ctrl(FMT_SUM, (unsigned)g_run_scn, (unsigned)c.events, c.tel_sent, c.tel_dropped,
              (unsigned)c.btn_dropped, (unsigned)c.q_hw, (unsigned)c.rec_overflow,
              (unsigned)c.bounce_rej, (unsigned)(g_frame_err & 0xFFFFu));
}

/** Kuyrukta kalan çerçeveleri gönderir (STOP'ta, ACK'ten önce). */
static void drain_queue(void)
{
    tx_item_t it;
    while (xQueueReceive(g_txq, &it, 0) == pdPASS) {
        uart_send_frame(it.frame);
    }
}

/* ---- Komutlar ----------------------------------------------------------- */
static void cmd_execute(const char *line)
{
    const cmd_t        c = cmd_parse(line);
    const cmd_result_t r = cmd_check(c, g_run_state);

    if (r != RES_ACK) {
        send_ctrl("NAK,%s", cmd_nak_text(r));
        return;
    }
    switch (c.id) {
    case CMD_SCN:
        run_set_scenario(c.arg);
        send_ctrl("ACK,SCN,S%u", (unsigned)g_run_scn);
        break;
    case CMD_START:
        run_start();
        send_ctrl("ACK,START,S%u", (unsigned)g_run_scn);
        break;
    case CMD_STOP:
        run_stop();
        drain_queue();                         /* koşunun son TEL/BTN'leri ACK'ten önce gitsin */
        send_ctrl("ACK,STOP");
        break;
    case CMD_DUMP:
        send_ctrl("ACK,DUMP,%u", 0u);          /* kayıt sayısı: adım 6'da */
        send_ver();
        /* REC/PRE (adım 6-7), CAL/MEM/RTS (adım 8) buraya eklenecek */
        send_sum();
        send_ctrl("END,DUMP");
        break;
    default:
        break;
    }
}

static void cmd_poll(void)
{
    static char     line[CMD_LINE_MAX + 1];
    static uint16_t len;
    static bool     too_long;

    while (s_rx_tail != s_rx_head) {
        char ch = (char)s_rx_ring[s_rx_tail];
        s_rx_tail = (uint16_t)((s_rx_tail + 1u) & (RX_RING_SIZE - 1u));

        if (ch == '\r') continue;
        if (ch == '\n') {
            line[len] = '\0';
            if (too_long)     send_ctrl("NAK,CMD");
            else if (len > 0) cmd_execute(line);
            len = 0; too_long = false;
        } else if (len < CMD_LINE_MAX) {
            line[len++] = ch;
        } else {
            too_long = true;                   /* satır sonuna kadar yut, sonra NAK */
        }
    }
}

/* ---- Görev -------------------------------------------------------------- */
void StartUartTxTask(void *argument)
{
    (void)argument;
    APP_SET_OWN_TAG(APP_TAG_UART_TX);
    s_self = xTaskGetCurrentTaskHandle();

    rx_arm();
    send_ver();                                /* MSG-09: açılışta ilk çerçeve */
    app_selftest_run();                        /* T19, T20 (~1 s) */

    for (;;) {
        cmd_poll();
        tx_item_t it;
        if (xQueueReceive(g_txq, &it, pdMS_TO_TICKS(UART_RX_POLL_MS)) == pdPASS) {
            uart_send_frame(it.frame);         /* FIFO: sırayla, biri bitmeden diğeri yok */
        }
    }
}
