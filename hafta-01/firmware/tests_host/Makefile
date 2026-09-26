# Kartsız birim testleri (test planı §5). Kullanım:  make test
# Firmware'in saf C modülleri PC'deki gcc ile, UNIT_TEST tanımlı olarak derlenir.
CC      ?= gcc
SRC_DIR := ../FreeRTOS_Kurs/Core/Src
INC_DIR := ../FreeRTOS_Kurs/Core/Inc
CFLAGS  := -std=c11 -Wall -Wextra -Werror -Wformat=2 -g -DUNIT_TEST -I$(INC_DIR) -I.
BUILD   := build

UUT     := $(SRC_DIR)/app_ts.c $(SRC_DIR)/app_frame.c $(SRC_DIR)/app_cmd.c $(SRC_DIR)/app_temp.c $(SRC_DIR)/app_meas.c
TESTS   := test_main.c test_ts.c test_frame.c test_cmd.c test_temp.c test_meas.c

$(BUILD)/run_tests: $(UUT) $(TESTS) unit.h $(wildcard $(INC_DIR)/app_*.h)
	@mkdir -p $(BUILD)
	$(CC) $(CFLAGS) $(UUT) $(TESTS) -o $@

.PHONY: test clean
test: $(BUILD)/run_tests
	@./$(BUILD)/run_tests

clean:
	rm -rf $(BUILD)
