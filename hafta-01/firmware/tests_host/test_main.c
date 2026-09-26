#include "unit.h"

int g_checks = 0, g_fails = 0;

void run_case(const char *id, const char *name, test_fn fn)
{
    int before = g_fails;
    fn();
    printf("[%s] %-6s %s\n", g_fails == before ? "GECTI" : "KALDI", id, name);
}

void test_ts_all(void);
void test_frame_all(void);
void test_cmd_all(void);
void test_temp_all(void);

int main(void)
{
    printf("== Kartsiz birim testleri ==\n");
    test_ts_all();
    test_frame_all();
    test_temp_all();
    test_cmd_all();
    printf("== %d kontrol, %d hata ==\n", g_checks, g_fails);
    return g_fails ? 1 : 0;
}
