/* TC-U02: sıcaklık dönüşümü (TSK-08) */
#include <stdlib.h>
#include "unit.h"
#include "app_temp.h"

/* Elle hesaplanmış örnekler. Kalibrasyon: CAL1=1000 @30 °C, CAL2=1300 @110 °C, 3,0 V.
 * 3,0 V'da ölçülen raw doğrudan kalibrasyon ölçeğindedir. */
static void u02_temp(void)
{
    CHECK_EQ_U(temp_x10_from_raw(1000, 1000, 1300, 30, 110, 3000, 3000), 300);   /* 30,0 °C */
    CHECK_EQ_U(temp_x10_from_raw(1300, 1000, 1300, 30, 110, 3000, 3000), 1100);  /* 110,0 °C */
    CHECK_EQ_U(temp_x10_from_raw(1150, 1000, 1300, 30, 110, 3000, 3000), 700);   /* 70,0 °C */
    /* 3,3 V'da raw=1000 → 3,0 V ölçeğinde 1100 → (100·80·10)/300 + 300 = 566,6 → 566 */
    int16_t t = temp_x10_from_raw(1000, 1000, 1300, 30, 110, 3000, 3300);
    CHECK(abs(t - 566) <= 1);
    /* 30 °C altı: negatif fark doğru işlenmeli (ör. 20 °C) */
    CHECK_EQ_U(temp_x10_from_raw(962, 1000, 1300, 30, 110, 3000, 3000) + 0, 199);   /* 19,9 °C (962→-38·800/300=-101,3→-101) */
}

void test_temp_all(void)
{
    run_case("U02", "sicaklik donusumu", u02_temp);
}
