/* TerrainTronics Holt startup hook. Built into the board core, not the sketch.
 * Requires TT-Bootload v0.4, which clears flags and software-resets into USER.
 */
#if defined(TT_HOLT_BOARD)
#include "ch32v00X.h"
#include "hw_config.h"

#ifndef TT_BOOT_DISABLE_IRQ
#define TT_BOOT_DISABLE_IRQ() __asm__ volatile("csrci mstatus, 8" ::: "memory")
#endif
#ifndef TT_BOOT_FENCE
#define TT_BOOT_FENCE() __asm__ volatile("fence rw, rw" ::: "memory")
#endif

/* A strong replacement for WCH's weak pre_init(). main() calls this before
 * setup(). Keep WCH's normal hardware initialization on the application path.
 */
void pre_init(void)
{
    const uint32_t flags = RCC->RSTSCKR;
    RCC->RSTSCKR |= RCC_RMVF;
    if ((flags & RCC_PINRSTF) && !(flags & (RCC_SFTRSTF | RCC_PORRSTF))) {
        TT_BOOT_DISABLE_IRQ();
        FLASH->KEYR = 0x45670123u;
        FLASH->KEYR = 0xCDEF89ABu;
        FLASH->BOOT_MODEKEYR = 0x45670123u;
        FLASH->BOOT_MODEKEYR = 0xCDEF89ABu;
        FLASH->STATR |= FLASH_STATR_BOOT_MODE;
        FLASH->CTLR |= FLASH_CTLR_LOCK;
        TT_BOOT_FENCE();
        NVIC_SystemReset();
        for (;;) {}
    }
    hw_config_init();
}
#endif
