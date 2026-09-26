/**
 * @file    app_fault.h
 * @brief   Ölümcül hata göstergesi (tasarım §10): kesmeleri kapatır, LD2'yi yakıp söndürür.
 *   Stack taşması  → 10 Hz (SYS-05)
 *   malloc hatası  →  2 Hz
 */
#ifndef APP_FAULT_H
#define APP_FAULT_H
#include <stdint.h>
void app_fault_blink(uint32_t hz) __attribute__((noreturn));
#endif
