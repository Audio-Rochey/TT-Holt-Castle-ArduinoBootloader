
#include <stdint.h>
#include <string.h>
#define FLASH_ACTLR_LATENCY_1 1u
#define RCC_PB2Periph_GPIOD 1u
#define RCC_PB2Periph_USART1 2u
#define RCC_RMVF 0x1000000u
#define Start_Mode_USER 0u
#define Start_Mode_BOOT 0x4000u
#define FLASH_COMPLETE 0
struct flash { uint32_t ACTLR; };
struct rcc {uint32_t CTLR, CFGR0, INTR, PB2PCENR, RSTSCKR;};
struct gpio {uint32_t CFGLR, BSHR;};
struct usart {uint32_t STATR,DATAR,CTLR1,CTLR2,CTLR3,BRR;};
struct tick {uint32_t CTLR,SR,CNT,CMP;};
static struct flash mock_flash;
static struct rcc mock_rcc;
static struct gpio mock_gpio;
static struct usart mock_usart;
static struct tick mock_tick;
#define FLASH (&mock_flash)
#define RCC (&mock_rcc)
#define GPIOD (&mock_gpio)
#define USART1 (&mock_usart)
#define SysTick (&mock_tick)
static uint32_t mock_start_mode = Start_Mode_BOOT;
static unsigned mock_reset_count;
static void SystemReset_StartMode(uint32_t mode) {mock_start_mode=mode;}
static void NVIC_SystemReset(void) {++mock_reset_count;}
static int FLASH_ROM_ERASE(uint32_t addr,uint32_t len) {memset((void*)(uintptr_t)addr,255,len); return 0;}
static int FLASH_ROM_WRITE(uint32_t addr,uint32_t *buf,uint32_t len) {memcpy((void*)(uintptr_t)addr,buf,len); return 0;}
