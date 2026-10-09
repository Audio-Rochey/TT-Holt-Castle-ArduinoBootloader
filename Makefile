# Stock GCC or WCH RISC-V GCC. No libc or WCH interrupt extension needed.
PREFIX ?= riscv64-unknown-elf-
CC = $(PREFIX)gcc
OBJCOPY = $(PREFIX)objcopy
SIZE = $(PREFIX)size
CFLAGS = -march=rv32ec_zicsr -mabi=ilp32e -Os -ffreestanding -fno-builtin -ffunction-sections -fdata-sections -Wall -Wextra -DCH32V006 -Ifirmware/source/CH32V00X_IAP/User -Ifirmware/source/CH32V00X_IAP/Core -Ifirmware/source/CH32V00X_IAP/Peripheral/inc
LDFLAGS = -nostdlib -Wl,--gc-sections,-Map=build/TT_Bootload_Arduino_3s.map -Tfirmware/source/CH32V00X_IAP/Ld/Link.ld
SOURCES = firmware/source/CH32V00X_IAP/User/main.c firmware/source/CH32V00X_IAP/Startup/startup.S
all: build/TT_Bootload_Arduino_3s.bin build/TT_Bootload_Arduino_3s_BOOT.hex
build/TT_Bootload_Arduino_3s.elf: $(SOURCES) firmware/source/CH32V00X_IAP/Ld/Link.ld firmware/source/CH32V00X_IAP/User/ch32v00X_conf.h
	mkdir -p build
	$(CC) $(CFLAGS) $(SOURCES) $(LDFLAGS) -o $@
	$(SIZE) $@
build/TT_Bootload_Arduino_3s.bin: build/TT_Bootload_Arduino_3s.elf
	$(OBJCOPY) -O binary $< $@
	python3 -c 'from pathlib import Path; n=Path("$@").stat().st_size; print("BOOT bytes:",n,"/ 3328"); assert n <= 3328'
build/TT_Bootload_Arduino_3s_BOOT.hex: build/TT_Bootload_Arduino_3s.elf
	$(OBJCOPY) --change-addresses 0x1fff0000 -O ihex $< $@
test:
	gcc -std=c99 -Wall -Wextra -Werror -Wno-int-to-pointer-cast -Itests/mocks -Ifirmware/source/CH32V00X_IAP/User tests/test_phrase.c -o /tmp/tt_test_phrase
	/tmp/tt_test_phrase
	gcc -std=c99 -Wall -Wextra -Werror -Wno-int-to-pointer-cast -Itests/mocks -Ifirmware/source/CH32V00X_IAP/User tests/test_device.c -o /tmp/tt_test_device
	/tmp/tt_test_device
	python3 -m unittest discover -s tests -v
clean:
	rm -rf build
.PHONY: all test clean

