/**
 * @file    app_temp.h
 * @brief   Dahili sıcaklık sensörü (ADC1, VTS) — TSK-08; tasarım §7.2.
 */
#ifndef APP_TEMP_H
#define APP_TEMP_H

#include <stdint.h>

/**
 * Ham ADC değerini 0,1 °C birimine çevirir (saf fonksiyon, TC-U02).
 * Fabrika kalibrasyonu vref_cal_mv (3,0 V) ile yapılmıştır; ölçüm vdda_mv ile yapılır.
 */
int16_t temp_x10_from_raw(uint16_t raw, uint16_t cal1, uint16_t cal2,
                          int32_t cal1_temp_c, int32_t cal2_temp_c,
                          uint32_t vref_cal_mv, uint32_t vdda_mv);

#ifndef UNIT_TEST
#define APP_VDDA_MV  3300u     /* tasarım DQ-2: 3,3 V sabit kabul */
void    temp_init(void);       /* ADC kalibrasyonu; görev başında bir kez */
int16_t temp_read_x10(void);   /* tek dönüşüm + polling; hata olursa INT16_MIN */
#endif

#endif /* APP_TEMP_H */
