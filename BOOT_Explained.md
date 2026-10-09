# Understanding the CH32V006 BOOT area

## Two places for two different jobs

On the 62 KiB CH32V006 variant targeted by this project:

| Storage | Physical address | Capacity | Purpose in this project |
| --- | --- | --- | --- |
| User Flash | `0x08000000` | 62 KiB / 63,488 bytes | Customer application or Arduino sketch |
| System Flash / BOOT | `0x1FFF0000` | 3,328 bytes | Three-second UART bootloader |

WCH supplies a boot program in System Flash at the factory. Its programming tools can install a custom IAP loader there, as demonstrated by WCH's USART_IAP example. Our compiled loader occupies 2,588 bytes.

## Why the linker says zero

The CPU starts execution at its reset mapping. When BOOT is selected, BOOT memory is mapped to address zero for execution. That is why `firmware/source/CH32V00X_IAP/Ld/Link.ld` says:

```ld
FLASH (rx) : ORIGIN = 0x00000000, LENGTH = 3328
```

The linker is describing the execution address. The programmer uses the physical BOOT storage address, `0x1FFF0000`. These addresses have different roles; do not change the linker origin to the programming address just because the utility asks for that address.

The supplied `firmware/TT_Bootload_Arduino_3s.bin` needs `0x1FFF0000` specified by the programmer. The application remains at its normal physical address, `0x08000000`. `make` can also generate a physical-address HEX in the local `build/` directory.

## What determines which program runs

The power-on start setting is an option byte. Configure it to BOOT so the custom loader runs first. WCH's SDK calls the selection `OB_PowerON_Start_Mode_BOOT`. Preserve other option-byte fields when changing it.

After three seconds without the phrase, this revision selects USER mode and
requests a software reset. User Flash is then mapped at address zero, matching
the stock WCH Arduino linker. The application BIN is programmed physically at
0x08000000. No Arduino application linker changes are needed.

On the tested Holt, an external reset entered the application immediately even
with BOOT reselected. The application startup hook checks the PINRSTF flag,
clears accumulated reset flags, selects BOOT and performs a software reset.
TT-Bootload handles the UART wait; the application does not start UART or wait
for the phrase. The included blink example demonstrates the hook. A TT Arduino
board core can eventually include it automatically in startup.

Receiving TT_ENTER_IAP cancels the three-second application-start timeout.
The loader stays in IAP until a verified upload finishes or the device resets.
The host's --enter-only option deliberately leaves it in IAP.

## Where to read more

1. **CH32V00X Reference Manual** (the newer V002/V004/V005/V006/V007 family):
   https://www.wch-ic.com/downloads/CH32V00XRM_PDF.html
   Look for memory mapping, System FLASH/BOOT, Flash control, user option bytes, and boot/start-mode control. Search the PDF for `BOOT`, `0x1FFF0000`, `BOOT_MODEKEYR` and `0x0020`. Use this family manual rather than the older V003-only manual.

2. **CH32V006/V005 datasheet**:
   https://www.wch-ic.com/downloads/CH32V006DS0_PDF.html
   Look for the Flash/storage description and the 3,328-byte System Flash region. Confirm the user-Flash capacity for your exact part.

3. **WCH's official SDK and examples**:
   https://github.com/openwch/ch32v002_004_005_006_007/tree/main/EVT/EXAM/USART_IAP
   Start with the IAP installation PDF, then `CH32V00X_IAP/Ld/Link.ld` and `CH32V00X_IAP/User/main.c`. A pinned copy of the installation PDF is included in `Docs/WCH_USART_IAP_Installation.pdf`.

4. **WCH's BOOT-as-user example**:
   https://github.com/openwch/ch32v002_004_005_006_007/tree/main/EVT/EXAM/FLASH/BootAsUser
   This illustrates a different use of BOOT storage: reclaiming it for application code. It is useful background, but is not the configuration goal for a separate resident bootloader. Its explanatory PDF is included in `Docs/WCH_BOOT_As_User_Flash.pdf`.

The WCH download pages use JavaScript; open them in a regular browser to download the PDFs. The SDK PDFs are Chinese, so the English reference manual is the best place to begin.
