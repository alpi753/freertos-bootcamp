/* Çok küçük bir test çatısı: CHECK başarısız olursa dosya:satır yazar ve sayar. */
#ifndef UNIT_H
#define UNIT_H
#include <stdio.h>

extern int g_checks, g_fails;

#define CHECK(cond) do { g_checks++; if (!(cond)) { g_fails++; \
    printf("  FAIL %s:%d: %s\n", __FILE__, __LINE__, #cond); } } while (0)

#define CHECK_EQ_U(a, b) do { unsigned long _a = (unsigned long)(a), _b = (unsigned long)(b); \
    g_checks++; if (_a != _b) { g_fails++; \
    printf("  FAIL %s:%d: %s == %lu, beklenen %lu\n", __FILE__, __LINE__, #a, _a, _b); } } while (0)

typedef void (*test_fn)(void);
void run_case(const char *id, const char *name, test_fn fn);
#endif
