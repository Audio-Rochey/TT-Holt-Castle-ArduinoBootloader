/* TerrainTronics Holt / CH32V006, PD2 onboard LED.
 * Requires the stock WCH CH32V006 Arduino board settings.
 * TT-Bootload v0.4 selects USER mode and resets to run this sketch.
 * Manual RESET enters TT-Bootload's 3-second UART entry window.
 */
#include <Arduino.h>

static void ttBootloadOnManualReset()
{
  const uint32_t resetFlags = RCC->RSTSCKR;
  RCC->RSTSCKR |= RCC_RMVF; // Clear accumulated flags on EVERY application start.

  // A pin reset requests BOOT. Exclude power-on and software reset to avoid
  // repeatedly entering BOOT when the bootloader hands control to this app.
  if ((resetFlags & RCC_PINRSTF) &&
      !(resetFlags & (RCC_SFTRSTF | RCC_PORRSTF))) {
    __asm__ volatile("csrci mstatus, 8" ::: "memory");
    FLASH->KEYR = 0x45670123u;
    FLASH->KEYR = 0xCDEF89ABu;
    FLASH->BOOT_MODEKEYR = 0x45670123u;
    FLASH->BOOT_MODEKEYR = 0xCDEF89ABu;
    FLASH->STATR |= FLASH_STATR_BOOT_MODE;
    FLASH->CTLR |= FLASH_CTLR_LOCK;
    __asm__ volatile("fence rw, rw" ::: "memory");
    NVIC_SystemReset();
    for (;;) {} // Wait for the requested reset.
  }
}

void setup()
{
  ttBootloadOnManualReset(); // Keep this FIRST, before your application setup.
  pinMode(PD2, OUTPUT);
}

void loop()
{
  digitalWrite(PD2, HIGH);
  delay(250);
  digitalWrite(PD2, LOW);
  delay(250);
}
