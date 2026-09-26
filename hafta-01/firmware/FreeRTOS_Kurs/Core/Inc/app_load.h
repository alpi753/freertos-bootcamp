/**
 * @file    app_load.h
 * @brief   S4/S5 CPU yükü (TSK-03; tasarım §7.2).
 *
 * Bekleme döngüsü DEĞİL, gerçek bir hesaplama (xorshift) döngüsüdür. Açılışta
 * kesmeler kapalıyken kalibre edilir: 1 ms'de kaç tur döndüğü ölçülür. Her
 * çalıştırmanın gerçek süresi ayrıca ölçülür ve CAL çerçevesinde raporlanır;
 * kesmeler araya girerse gerçek süre hedeften uzun çıkar.
 */
#ifndef APP_LOAD_H
#define APP_LOAD_H

#include <stdint.h>

void     cpu_load_calibrate(void);          /* açılışta bir kez (görev bağlamı) */
void     cpu_load_run(uint32_t target_us);  /* ≈ target_us boyunca hesap yapar */
uint32_t cpu_load_iters_per_ms(void);

#endif /* APP_LOAD_H */
