import importlib.util
import json
import shutil
import struct
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("holt_install", ROOT / "install_macos.py")
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


@unittest.skipUnless(shutil.which("g++"), "host C++ compiler required")
class VariantTests(unittest.TestCase):
    def test_digital_enum_and_analog_indexes(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)
            variant = ROOT / "overlay/variants/CH32VM00X/HoltCastle"
            (path / "pins_arduino.h").write_text('''
#pragma once
#include <stdint.h>
#include "variant_HoltCastle.h"
// WCH declares its digital names AFTER including the variant header.
enum {D0,D1,D2,D3,D4,D5,D6,D7,D8,D9,D10,D11,D12,D13,D14,D15,D16,D17};
#define PIN_A0 192
#define PIN_A1 193
#define PIN_A2 194
#define PIN_A3 195
#define PIN_A4 196
#define PIN_A5 197
#define PIN_A6 198
#define PIN_A7 199
enum PinName {PA_1,PA_2,PC_0,PC_1,PC_2,PC_3,PC_4,PC_5,PC_6,PC_7,
              PD_0,PD_1,PD_2,PD_3,PD_4,PD_5,PD_6,PD_7};
extern const PinName digitalPin[];
extern const uint32_t analogInputPin[];
''')
            (path / "test.cpp").write_text('''
#include <cassert>
#include "pins_arduino.h"
PinName physical(unsigned pin) {
    return digitalPin[pin >= 192 ? analogInputPin[pin-192] : pin];
}
int main() {
    assert(physical(D0)==PD_0); assert(physical(D1)==PC_2);
    assert(physical(D2)==PC_1); assert(physical(D3)==PD_3);
    assert(physical(D4)==PD_4); assert(physical(D5)==PC_5);
    assert(physical(D6)==PC_7); assert(physical(D7)==PC_6);
    assert(physical(D8)==PC_0); assert(physical(LED_BUILTIN)==PD_2);
    assert(physical(PA2)==PA_2); assert(physical(PA1)==PA_1);
    assert(physical(PC4)==PC_4); assert(physical(PD3)==PD_3);
    assert(physical(PD4)==PD_4); assert(physical(PD5)==PD_5);
    assert(physical(PD6)==PD_6); assert(physical(PD1)==PD_1);
    assert(physical(PD7)==PD_7);
}
''')
            subprocess.run(["g++", "-Wall", "-Wextra", "-Werror", "-I"+str(path),
                            "-I"+str(variant), str(variant / "variant_HoltCastle.cpp"),
                            str(path / "test.cpp"), "-o", str(path / "test")], check=True,
                           capture_output=True)
            subprocess.run([str(path / "test")], check=True)


class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.core = self.base / "wch"
        self.destination = self.base / "hardware/TerrainTronics/ch32"
        fixture = {
            "boards.txt": "wch.name=Original WCH board\n",
            "platform.txt": "name=WCH\nrecipe.c.combine.pattern=-Wl,--whole-archive\n",
            "cores/arduino/main.cpp": "int main() { pre_init(); setup(); }\n",
            "cores/arduino/board.c": "WEAK void pre_init(void) { hw_config_init(); }\n",
            "system/CH32VM00X/SRC/Ld/Link.ld": "FLASH (rx) : ORIGIN = 0x00000000, LENGTH = 62K\n",
            "system/CH32VM00X/SRC/Peripheral/inc/ch32v00X.h": "/* vendor header */\n",
            "variants/CH32VM00X/CH32V006K8/PeripheralPins.c": "/* preserved pin map */\n",
            "variants/CH32VM00X/CH32V006K8/PinNamesVar.h": "/* preserved definitions */\n",
        }
        for name, text in fixture.items():
            p = self.core / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text)
        self.uploader = self.base / "tt-upload"
        self.uploader.write_bytes(b"\xcf\xfa\xed\xfe" + struct.pack("<I", 0x0100000C))

    def tearDown(self):
        self.tmp.cleanup()

    def install(self, replace=False):
        with patch.object(installer.subprocess, "run", return_value=
                          subprocess.CompletedProcess([], 0, "--port --baud", "")):
            return installer.install(self.core, self.uploader, self.destination, replace)

    def test_install_preserves_original_and_includes_hook(self):
        original = (self.core / "boards.txt").read_bytes()
        destination = self.install()
        self.assertEqual((self.core / "boards.txt").read_bytes(), original)
        self.assertIn("TT_HOLT_BOARD", (destination / "boards.txt").read_text())
        self.assertTrue((destination / "cores/arduino/tt_bootload_hook.c").is_file())
        self.assertTrue((destination / "variants/CH32VM00X/HoltCastle/PeripheralPins.c").is_file())
        self.assertEqual((destination / "tools/ttupload/macos-arm64/tt-upload").read_bytes(), self.uploader.read_bytes())
        self.assertEqual(json.loads((destination / installer.MARKER).read_text())["host"], "macos-arm64")

    def test_refuses_existing_unmanaged_directory(self):
        self.destination.mkdir(parents=True)
        with self.assertRaisesRegex(ValueError, "Destination exists"):
            self.install(replace=True)

    def test_reinstall_managed_directory(self):
        self.install()
        self.install(replace=True)

    def test_refuses_modified_link_origin(self):
        p = self.core / "system/CH32VM00X/SRC/Ld/Link.ld"
        p.write_text(p.read_text().replace("0x00000000", "0x08000000"))
        with self.assertRaisesRegex(ValueError, "stock V006"):
            self.install()

    def test_rejects_non_arm64_uploader(self):
        self.uploader.write_bytes(b"not a Mach-O")
        with self.assertRaisesRegex(ValueError, "arm64"):
            installer.validate_uploader(self.uploader)

    def test_requires_hook_retention_in_link_recipe(self):
        (self.core / "platform.txt").write_text("name=WCH\n")
        with self.assertRaisesRegex(ValueError, "whole-archive"):
            self.install()


@unittest.skipUnless(shutil.which("gcc") and shutil.which("ar"), "host C compiler required")
class HookTests(unittest.TestCase):
    def test_reset_paths_and_weak_override_retention(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)
            (path / "ch32v00X.h").write_text('''
#include <stdint.h>
struct mock_rcc { uint32_t RSTSCKR; };
struct mock_flash { uint32_t KEYR, BOOT_MODEKEYR, STATR, CTLR; };
extern struct mock_rcc mock_rcc;
extern struct mock_flash mock_flash;
#define RCC (&mock_rcc)
#define FLASH (&mock_flash)
#define RCC_RMVF (1u << 24)
#define RCC_PINRSTF (1u << 26)
#define RCC_PORRSTF (1u << 27)
#define RCC_SFTRSTF (1u << 28)
#define FLASH_STATR_BOOT_MODE (1u << 14)
#define FLASH_CTLR_LOCK (1u << 7)
#define TT_BOOT_DISABLE_IRQ() ((void)0)
#define TT_BOOT_FENCE() ((void)0)
void NVIC_SystemReset(void);
''')
            (path / "hw_config.h").write_text("void hw_config_init(void);\n")
            (path / "weak.c").write_text('''
#include "hw_config.h"
__attribute__((weak)) void pre_init(void) { hw_config_init(); }
''')
            (path / "test.c").write_text('''
#include <assert.h>
#include <setjmp.h>
#include "ch32v00X.h"
struct mock_rcc mock_rcc;
struct mock_flash mock_flash;
static jmp_buf reset;
static unsigned initialized, reset_count;
void hw_config_init(void) { ++initialized; }
void NVIC_SystemReset(void) { ++reset_count; longjmp(reset, 1); }
void pre_init(void);
static void skips_boot(uint32_t flags) {
    unsigned before = initialized;
    mock_rcc.RSTSCKR = flags;
    pre_init();
    assert(initialized == before + 1);
    assert(mock_rcc.RSTSCKR & RCC_RMVF);
    assert(reset_count == 0);
}
int main(void) {
    skips_boot(0);
    skips_boot(RCC_PORRSTF | RCC_PINRSTF);
    skips_boot(RCC_SFTRSTF);
    skips_boot(RCC_SFTRSTF | RCC_PINRSTF);
    unsigned before = initialized;
    mock_rcc.RSTSCKR = RCC_PINRSTF;
    if (!setjmp(reset)) { pre_init(); assert(0); }
    assert(initialized == before);
    assert(reset_count == 1);
    assert(mock_flash.KEYR == 0xCDEF89ABu);
    assert(mock_flash.BOOT_MODEKEYR == 0xCDEF89ABu);
    assert(mock_flash.STATR & FLASH_STATR_BOOT_MODE);
    assert(mock_flash.CTLR & FLASH_CTLR_LOCK);
    assert(mock_rcc.RSTSCKR & RCC_RMVF);
}
''')
            hook = ROOT / "overlay/cores/arduino/tt_bootload_hook.c"
            def run(args):
                subprocess.run(args, cwd=path, check=True, capture_output=True)
            run(["gcc", "-Wall", "-Wextra", "-Werror", "-DTT_HOLT_BOARD", "-I.", "-c", str(hook), "-o", "hook.o"])
            run(["gcc", "-c", "weak.c", "-o", "weak.o"])
            run(["ar", "rcs", "core.a", "weak.o", "hook.o"])
            run(["gcc", "test.c", "-Wl,--whole-archive", "core.a", "-Wl,--no-whole-archive", "-o", "test"])
            run([str(path / "test")])


if __name__ == "__main__":
    unittest.main()
