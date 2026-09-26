# Test Sonuçları — Hafta 01

Test tanımları: [`specs/03-test-plan.md`](specs/03-test-plan.md). Her satır bir test koşusudur; bir test tekrarlanırsa yeni satır eklenir, eskisi silinmez.

| TC | Tarih | Commit | Derleme | Sonuç | Kanıt | Not |
|---|---|---|---|---|---|---|
| TC-R03 (yalnızca `.gitignore` maddesi) | 2026-09-25 | 617d98b | — | GEÇTİ | `git status --short` çıktısında `.metadata/`, `Debug/`, `Release/` yok; `git check-ignore -v` üç yolu da `.gitignore` kuralıyla eşleştiriyor | Uygulama adımı 1 çıkış testi. R03'ün diğer maddeleri adım 10'da. |
| TC-R02 | 2026-09-26 | 0196d42 + çalışma dizini | — | KALDI | `.ioc` diff ve üretilen kod: C-1 ✓ (EXTI15_10 öncelik 6), C-2 ✓ etkin / öncelik 5, C-3 ✓ DMA1_Ch7 / öncelik 5, C-4 ✓ (PSC 79, ARR 0xFFFFFFFF), **C-5 ✗ örnekleme `ADC_SAMPLETIME_2CYCLES_5`**, **C-6 ✗ `defaultTask` hâlâ oluşturuluyor**, C-7 ✓ (heap 16384, stack check 2, malloc hook, run-time stats, task tag) | Düzeltme sonrası tekrar koşulacak. USART2/DMA önceliği 5: ISR-01'i sağlıyor, tasarımdaki 6'dan farklı. |
| TC-R02 (tekrar) | 2026-09-26 | adım 2 commit'i | Debug | GEÇTİ | C-1 EXTI15_10 öncelik 6 ✓; C-2 USART2 kesmesi, öncelik 6 ✓; C-3 DMA1_Ch7 Normal/Byte, öncelik 6 ✓; C-4 TIM2 PSC 79, ARR 0xFFFFFFFF ✓; C-5 ADC1 sıcaklık kanalı, `ADC_SAMPLETIME_640CYCLES_5` ✓; C-6 3 görev (40/32/24, stack 384/256/512 word, Static), `defaultTask` yok ✓; C-7 heap 16384, stack check 2, malloc hook, run-time stats, task tag ✓; C-8 `USE_NEWLIB_REENTRANT` 1 ✓. Derleme hatasız. `FreeRTOS_Kurs.map`: `StartUartTxTask` → `app_uart_tx.o` (main.o'daki `__weak` gövde atıldı), `StartTelemetryTask` → `app_telemetry.o`, `StartButtonTask` → `app_button.o` | İlk koşuda bulunan C-5/C-6 düzeltildi; görev adı `Telemetry` → `TelemetryTask`. |
