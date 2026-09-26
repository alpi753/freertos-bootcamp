/**
 * @file    app_meas.h
 * @brief   Olay başına t₀…t₄ ölçüm kayıtları (TIM-02, TIM-02a/b, TIM-03; tasarım §8).
 *
 * Kayıtlar koşu boyunca yalnızca RAM'de tutulur; STOP'tan sonra DUMP ile
 * REC çerçeveleri olarak gönderilir (TIM-05). Modül saf C'dir (HAL/FreeRTOS
 * yok) ve PC'de test edilir (tests_host/test_meas.c).
 *
 * Yazanlar: ISR (t₀), ButtonTask (t₁, t₂, kayıp), UartTxTask (t₃),
 * UART TC kesmesi (t₄). Her alanı tek bir yazar değiştirir.
 */
#ifndef APP_MEAS_H
#define APP_MEAS_H

#include <stdint.h>
#include <stdbool.h>
#include "app_config.h"

#if TEST_MEAS_CAP
#define MEAS_CAP  4u      /* TC-T15: kapasite taşmasını denemek için */
#else
#define MEAS_CAP  64u     /* TIM-03: en az 64 olay */
#endif

/* Kayıt durumu (REC çerçevesindeki "lost" alanı) */
#define MEAS_OK          0u   /* t₀…t₄ tam */
#define MEAS_LOST_QUEUE  1u   /* xQueueSend başarısız: zincir t₂'de bitti (TIM-02a) */
#define MEAS_INCOMPLETE  2u   /* beklenmeyen: damgalardan biri eksik (ör. TC zaman aşımı) */

/* have bit maskesi */
#define MEAS_HAVE_T0  0x01u
#define MEAS_HAVE_T1  0x02u
#define MEAS_HAVE_T2  0x04u
#define MEAS_HAVE_T3  0x08u
#define MEAS_HAVE_T4  0x10u
#define MEAS_HAVE_ALL 0x1Fu

typedef struct {
    uint16_t event_id;        /* 1'den başlar, her koşuda sıfırlanır */
    uint8_t  scn;
    uint8_t  lost_queue;      /* 1: kuyruğa yazılamadı */
    volatile uint8_t  have;   /* hangi damgalar alındı */
    uint32_t t[5];            /* t₀…t₄ [µs, TIM2] */
} meas_rec_t;

/** REC çerçevesi için hazırlanmış değerler */
typedef struct {
    uint16_t event_id;
    uint8_t  scn;
    uint32_t t0;
    uint32_t d[4];            /* t1-t0, t2-t1, t3-t2, t4-t3; REC_DELTA_MAX'a doyurulmuş */
    uint8_t  lost;            /* MEAS_OK / MEAS_LOST_QUEUE / MEAS_INCOMPLETE */
} meas_rec_view_t;

/** START: tüm kayıtları ve sayaçları sıfırlar. */
void     meas_reset(void);

/** ISR (yalnızca koşuda): yeni olay açar ve olay numarasını döndürür (1, 2, …).
 *  Kapasite doluysa olay yine numaralanır ama kaydedilmez (rec_overflow++). */
uint16_t meas_event_begin(uint32_t t0, uint8_t scn);

/** Damga yaz. event_id == 0 (koşu dışı) veya kapasite dışı ise hiçbir şey yapmaz. */
void     meas_stamp(uint16_t event_id, unsigned idx, uint32_t t);
void     meas_mark_lost(uint16_t event_id);

uint16_t meas_events(void);        /* koşuda kabul edilen olay sayısı */
uint16_t meas_count(void);         /* kaydedilen olay sayısı (≤ MEAS_CAP) */
uint16_t meas_overflow(void);      /* kapasite yüzünden kaydedilemeyen olay */

/** i. kaydı REC çerçevesine hazır hâle getirir (i < meas_count()). */
bool     meas_view(uint16_t i, meas_rec_view_t *out);

#endif /* APP_MEAS_H */
