# Yapay zekâ kullanımı

Bu haftanın çalışması Claude (Anthropic, Cowork modu) ile birlikte yürütüldü. Proje talimatı gereği sıra hep **Gereksinimler → Tasarım → Uygulama → Test → Kanıt** oldu.

## Kim ne yaptı

| İş | Kursiyer | Claude |
|---|---|---|
| Kursun tanımı, senaryolar (S0–S5), ölçüm noktaları (t₀–t₄) | Verdi (slayt tabloları) | — |
| Gereksinimler, tasarım, test planı | Gözden geçirdi, değişiklik istedi, onayladı | Taslakları yazdı, istenen değişiklikleri uyguladı |
| CubeMX yapılandırması (.ioc) | Yaptı | Adımları tarif etti, sonucu inceledi |
| Uygulama kodu (`app_*.c/h`, `USER CODE` bölümleri), PC arayüzü, test ve analiz araçları | İnceledi | Yazdı |
| Kartsız birim testleri | — | Yazdı, çalıştırdı, mutasyonla sınadı |
| Kart üstü testler (T, D) ve ölçüm kampanyası (E) | Karta yükledi, butona bastı, gözlemledi, çıktıları paylaştı | Test araçlarını yazdı, çıktıları değerlendirip kaydetti |
| Hata ayıklama | Hata ayıklayıcıda gözlem yaptı (ör. HardFault) | Neden analizi yaptı, düzeltmeyi yazdı |
| `gozlemler.md` | **Yalnızca kursiyer** | Dokunmadı (DOC-06) |
| Git commit'leri | Onay verdi | Attı (`Co-Authored-By: Claude` satırıyla) |

## Kursiyerin yön verdiği kararlar (örnekler)

- Gereksinimlerden "beklenen değer" tahminleri çıkarıldı: amaç tahmin etmek değil, ölçüp görmek.
- Aralık adları yeniden belirlendi (`d_EventToRun`, `d_ButtonExec`, …) ve görev değişimi (kesilme) ölçümleri eklendi.
- Buton her durumda algılanır; koşu dışında `event_id = 0` olur.
- Release'te 5,68 µs ölçülen ISR süresi (ölçüt ≤ 5 µs) sapma DEV-01 olarak kabul edildi.
- `frame_err` sayacı START'ta sıfırlanıyor.

## Yapay zekânın yaptığı ve düzeltilen hatalar

Hepsi [test-results.md](test-results.md)'de kayıtlıdır. Özetle:

- **CubeMX kısıtları:** "defaultTask silinebilir" ve "üç görev de As external olabilir" varsayımları yanlıştı. Görevler yeniden adlandırıldı; UartTxTask `As weak` oldu.
- **T09:** Test planı ISR süresini Debug derlemede değerlendiriyordu; bu yanlıştı, Release'e taşındı.
- **Derleme hatası:** `app_frame.c`'de eksik `#include "task.h"` bağlantı hatasına yol açtı. Denetimlere `-Werror=implicit-function-declaration` eklendi.
- **T18 ilk sürüm:** Test kodunu derleyici `-Os` ile sildi. Sonraki sürümde büyük taşma, FreeRTOS kontrolünden önce HardFault'a yol açtı (B-02). T18 ikiye ayrıldı.
- **Arayüzdeki "hat kaybı" formülü:** Sonda düşürülen TEL'leri göremiyordu (B-03).

## Doğrulama yaklaşımı

- Her gereksinimin bir testi var (test planı §9, izlenebilirlik tablosu).
- Kartsız testler "testin testi" ile sınandı: kodda bilerek hata oluşturulup testin bunu yakaladığı görüldü.
- **Ölçüm aracı ile sistem davranışı ayrıldı:** Geçti/kaldı ölçütleri yalnızca cetvelin doğruluğu içindir. Gecikme değerleri gözlemdir ve ne çıkarsa kaydedilir.
