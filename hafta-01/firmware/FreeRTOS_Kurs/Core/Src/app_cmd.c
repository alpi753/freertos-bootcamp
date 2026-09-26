/**
 * @file    app_cmd.c
 * @brief   Komut ayrıştırıcı ve durum tablosu (saf C, TC-U05).
 */
#include "app_cmd.h"
#include <string.h>

cmd_t cmd_parse(const char *line)
{
    cmd_t c = { CMD_UNKNOWN, 0 };

    if (strcmp(line, "CMD,START") == 0) { c.id = CMD_START; return c; }
    if (strcmp(line, "CMD,STOP")  == 0) { c.id = CMD_STOP;  return c; }
    if (strcmp(line, "CMD,DUMP")  == 0) { c.id = CMD_DUMP;  return c; }

    if (strncmp(line, "CMD,SCN,", 8) == 0) {
        const char *a = line + 8;
        /* tam olarak tek bir rakam, 0..5 */
        if (a[0] >= '0' && a[0] <= '5' && a[1] == '\0') {
            c.id = CMD_SCN; c.arg = (uint8_t)(a[0] - '0');
        } else {
            c.id = CMD_BAD_ARG;
        }
    }
    return c;
}

cmd_result_t cmd_check(cmd_t cmd, run_state_t st)
{
    switch (cmd.id) {
    case CMD_SCN:
    case CMD_START:   return (st == RUN_RUNNING) ? RES_NAK_BUSY : RES_ACK;
    case CMD_STOP:    return (st == RUN_RUNNING) ? RES_ACK : RES_NAK_STATE;
    case CMD_DUMP:    return (st == RUN_STOPPED) ? RES_ACK : RES_NAK_STATE;
    case CMD_BAD_ARG: return RES_NAK_ARG;
    default:          return RES_NAK_CMD;
    }
}

const char *cmd_nak_text(cmd_result_t r)
{
    switch (r) {
    case RES_NAK_BUSY:  return "BUSY";
    case RES_NAK_STATE: return "STATE";
    case RES_NAK_ARG:   return "ARG";
    case RES_NAK_CMD:   return "CMD";
    default:            return 0;
    }
}
