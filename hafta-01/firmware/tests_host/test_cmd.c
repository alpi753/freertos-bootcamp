/* TC-U05: komut ayrıştırıcı + durum tablosu (tasarım §7.5) */
#include "unit.h"
#include "app_cmd.h"

static cmd_result_t r(const char *line, run_state_t st) { return cmd_check(cmd_parse(line), st); }

static void u05_parse(void)
{
    cmd_t c = cmd_parse("CMD,SCN,3");
    CHECK(c.id == CMD_SCN && c.arg == 3);
    CHECK(cmd_parse("CMD,SCN,0").arg == 0);
    CHECK(cmd_parse("CMD,SCN,5").arg == 5);
    CHECK(cmd_parse("CMD,SCN,6").id  == CMD_BAD_ARG);
    CHECK(cmd_parse("CMD,SCN,9").id  == CMD_BAD_ARG);
    CHECK(cmd_parse("CMD,SCN,").id   == CMD_BAD_ARG);
    CHECK(cmd_parse("CMD,SCN,33").id == CMD_BAD_ARG);
    CHECK(cmd_parse("CMD,SCN,-1").id == CMD_BAD_ARG);
    CHECK(cmd_parse("CMD,START").id  == CMD_START);
    CHECK(cmd_parse("CMD,STOP").id   == CMD_STOP);
    CHECK(cmd_parse("CMD,DUMP").id   == CMD_DUMP);
    CHECK(cmd_parse("CMD,START ").id == CMD_UNKNOWN);   /* fazladan karakter kabul edilmez */
    CHECK(cmd_parse("cmd,start").id  == CMD_UNKNOWN);   /* büyük/küçük harf duyarlı */
    CHECK(cmd_parse("XYZ").id        == CMD_UNKNOWN);
    CHECK(cmd_parse("").id           == CMD_UNKNOWN);
}

static void u05_state_table(void)
{
    /* SCN */
    CHECK(r("CMD,SCN,2", RUN_IDLE)    == RES_ACK);
    CHECK(r("CMD,SCN,2", RUN_STOPPED) == RES_ACK);
    CHECK(r("CMD,SCN,2", RUN_RUNNING) == RES_NAK_BUSY);    /* MSG-08 */
    CHECK(r("CMD,SCN,9", RUN_IDLE)    == RES_NAK_ARG);
    /* START */
    CHECK(r("CMD,START", RUN_IDLE)    == RES_ACK);
    CHECK(r("CMD,START", RUN_STOPPED) == RES_ACK);
    CHECK(r("CMD,START", RUN_RUNNING) == RES_NAK_BUSY);
    /* STOP */
    CHECK(r("CMD,STOP", RUN_RUNNING)  == RES_ACK);
    CHECK(r("CMD,STOP", RUN_IDLE)     == RES_NAK_STATE);
    CHECK(r("CMD,STOP", RUN_STOPPED)  == RES_NAK_STATE);
    /* DUMP */
    CHECK(r("CMD,DUMP", RUN_STOPPED)  == RES_ACK);
    CHECK(r("CMD,DUMP", RUN_IDLE)     == RES_NAK_STATE);
    CHECK(r("CMD,DUMP", RUN_RUNNING)  == RES_NAK_STATE);
    /* bilinmeyen */
    CHECK(r("XYZ", RUN_IDLE)          == RES_NAK_CMD);
    /* NAK metinleri */
    CHECK(cmd_nak_text(RES_ACK) == 0);
    CHECK(cmd_nak_text(RES_NAK_BUSY)[0] == 'B');
}

void test_cmd_all(void)
{
    run_case("U05", "komut ayristirici", u05_parse);
    run_case("U05", "komut durum tablosu", u05_state_table);
}
