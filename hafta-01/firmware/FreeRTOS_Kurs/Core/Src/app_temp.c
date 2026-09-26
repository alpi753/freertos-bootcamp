/**
 * @file    app_temp.c
 * @brief   Dahili sıcaklık sensörü okuma ve dönüşümü (TSK-08).
 */
#include "app_temp.h"

int16_t temp_x10_from_raw(uint16_t raw, uint16_t cal1, uint16_t cal2,
                          int32_t cal1_temp_c, int32_t cal2_temp_c,
                          uint32_t vref_cal_mv, uint32_t vdda_mv)
{
    /* Ölçümü kalibrasyon gerilimi ölçeğine çevir (3,3 V → 3,0 V) */
    int32_t raw_cal = (int32_t)((uint32_t)raw * vdda_mv / vref_cal_mv);
    int32_t t_x10 = (raw_cal - (int32_t)cal1) * (cal2_temp_c - cal1_temp_c) * 10
                    / ((int32_t)cal2 - (int32_t)cal1)
                    + cal1_temp_c * 10;
    return (int16_t)t_x10;
}

#ifndef UNIT_TEST
#include "main.h"
#include "stm32l4xx_ll_adc.h"   /* TEMPSENSOR_CAL* sabitleri */

extern ADC_HandleTypeDef hadc1;

void temp_init(void)
{
    (void)HAL_ADCEx_Calibration_Start(&hadc1, ADC_SINGLE_ENDED);
}

int16_t temp_read_x10(void)
{
    if (HAL_ADC_Start(&hadc1) != HAL_OK) return INT16_MIN;
    if (HAL_ADC_PollForConversion(&hadc1, 2) != HAL_OK) { HAL_ADC_Stop(&hadc1); return INT16_MIN; }
    uint16_t raw = (uint16_t)HAL_ADC_GetValue(&hadc1);
    HAL_ADC_Stop(&hadc1);
    return temp_x10_from_raw(raw, *TEMPSENSOR_CAL1_ADDR, *TEMPSENSOR_CAL2_ADDR,
                             TEMPSENSOR_CAL1_TEMP, TEMPSENSOR_CAL2_TEMP,
                             TEMPSENSOR_CAL_VREFANALOG, APP_VDDA_MV);
}
#endif
