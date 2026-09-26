/**
 * @file    app_frame.c
 * @brief   64 baytlık çerçeve üretimi (MSG-01, MSG-02; tasarım §9).
 */
#include "app_frame.h"
#include <stdarg.h>
#include <stdio.h>
#include <string.h>

#if defined(DEBUG) && !defined(UNIT_TEST)
#include "FreeRTOS.h"
#include "task.h"                  /* configASSERT → taskDISABLE_INTERRUPTS() */
#define FRAME_ASSERT(x)  configASSERT(x)   /* Debug: hatada dur (MSG-02) */
#else
#define FRAME_ASSERT(x)  ((void)0)         /* Release / PC: say ve devam et */
#endif

volatile uint32_t g_frame_err = 0;

bool frame_vbuild(char out[FRAME_LEN], const char *fmt, va_list ap)
{
    /* Önce geçici tampona yaz: hata olursa çağıranın tamponu bozulmaz. */
    char tmp[FRAME_LEN + 32];
    int n = vsnprintf(tmp, sizeof tmp, fmt, ap);

    /* vsnprintf, tampon yetmese bile TAM uzunluğu döndürür; kesilme böyle anlaşılır. */
    if (n < 0 || n > (int)FRAME_PAYLOAD) {
        g_frame_err++;
        FRAME_ASSERT(0);
        return false;
    }
    memcpy(out, tmp, (size_t)n);
    memset(out + n, ' ', FRAME_PAYLOAD - (size_t)n);
    out[FRAME_LEN - 1] = '\n';
    return true;
}

bool frame_build(char out[FRAME_LEN], const char *fmt, ...)
{
    va_list ap;
    va_start(ap, fmt);
    bool ok = frame_vbuild(out, fmt, ap);
    va_end(ap);
    return ok;
}
