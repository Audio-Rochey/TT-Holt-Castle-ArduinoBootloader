/* SINGLE EDITABLE C FILE - TerrainTronics CH32V006 UART bootloader v0.4.
 * Settings and firmware logic are below. WCH Flash support is appended at
 * the end so this project compiles exactly one C translation unit.
 * MounRiver Studio 2 project: CH32V00X_IAP.wvproj.
 * See ../README.md for BOOT installation, limitations and attribution.
 */
/* TerrainTronics CH32V006 UART phrase bootloader v0.4, 2026-10-09.
 * Based on WCH CH32V00X USART_IAP startup, UART and Flash mechanisms.
 * Power-on BOOT: listen for TT_ENTER_IAP for three seconds, then run APP.
 * Full key: stay in IAP. Blank APP: stay in IAP even without the key.
 * No PC0 check. Manual reset entry requires the application startup hook.
 * UART: PD5 TX, PD6 RX, 460800 8N1. No interrupts used by this loader.
 * Protocol is the WCH example's AA55 command framing, with bounded reads.
 * The supplied Python uploader is the tested host implementation.
 * This is boot-region firmware, NOT an Arduino sketch.
 */
#include "ch32v00X.h"
/* TerrainTronics UART bootloader, 2026-10-09. CH32V006 only. */
#ifndef TT_BOOT_CONFIG_H
#define TT_BOOT_CONFIG_H
#define TT_BOOT_WINDOW_MS 3000u
#define TT_ENTRY_PHRASE "TT_ENTER_IAP"
#define TT_UART_BAUD 460800u
#define TT_CLOCK_HZ 24000000u
#define TT_TICKS_PER_MS (TT_CLOCK_HZ / 8u / 1000u)
#define TT_APP_BASE 0x08000000u
#define TT_APP_SIZE (62u * 1024u)
#define TT_PACKET_TIMEOUT_MS 250u
#endif

#ifndef TT_PHRASE_MATCH_H
#define TT_PHRASE_MATCH_H
#include <stdint.h>

/* Prefix fallback handles repeated starts, noise, and overlapping matches.
   No allocation, interrupts, or blocking reads. Returns 1 on a full match. */
static inline int tt_phrase_feed(uint8_t *matched, uint8_t byte)
{
    static const char phrase[] = TT_ENTRY_PHRASE;
    unsigned n = *matched;
    while (n && byte != (uint8_t)phrase[n]) {
        unsigned candidate = n - 1;
        for (; candidate; --candidate) {
            unsigned j = 0;
            while (j < candidate && phrase[j] == phrase[n - candidate + j]) ++j;
            if (j == candidate) break;
        }
        n = candidate;
    }
    if (byte == (uint8_t)phrase[n]) ++n;
    if (n == sizeof(phrase) - 1) { *matched = 0; return 1; }
    *matched = (uint8_t)n;
    return 0;
}
#endif


static uint32_t page[64]; /* word-aligned 256-byte Flash programming buffer */
static uint8_t payload[68];
static uint32_t program_addr, verify_addr, received;
static uint16_t used;
static uint8_t erased, flushed, verified;

/* Startup calls SystemInit. Keep external pins Hi-Z except UART.
   Use HSI directly, 24 MHz, one Flash wait state; no GPIO_IPD_Unused(). */
void SystemInit(void)
{
    FLASH->ACTLR = FLASH_ACTLR_LATENCY_1;
    RCC->CTLR |= 1u;
    RCC->CFGR0 &= 0x68FF0000u;
    RCC->CTLR = (RCC->CTLR & 0xFED6FFFBu) | (1u << 20);
    RCC->CTLR &= 0xFFFBFFFFu;
    RCC->CFGR0 &= 0xFFFEFFFFu;
    RCC->INTR = 0x009D0000u;
}

static void uart_init(void)
{
    RCC->PB2PCENR |= RCC_PB2Periph_GPIOD | RCC_PB2Periph_USART1;
    /* Change only PD5/PD6. PD5 alternate push-pull, PD6 input pull-up. */
    GPIOD->CFGLR = (GPIOD->CFGLR & ~0x0FF00000u) | 0x08B00000u;
    GPIOD->BSHR = 1u << 6;
    USART1->CTLR1 = 0;
    USART1->CTLR2 = 0;
    USART1->CTLR3 = 0;
    USART1->BRR = (TT_CLOCK_HZ + TT_UART_BAUD / 2u) / TT_UART_BAUD;
    USART1->CTLR1 = 0x200Cu;
    /* HCLK/8, no interrupt, free-running 32-bit count. */
    SysTick->CTLR = 0;
    SysTick->SR = 0;
    SysTick->CNT = 0;
    SysTick->CMP = 0xFFFFFFFFu;
    SysTick->CTLR = 1;
}

static int rx(uint8_t *b)
{
    uint32_t status = USART1->STATR;
    if (status & (0x20u | 0x0Fu)) {
        uint8_t data = (uint8_t)USART1->DATAR; /* clears RX/error flags */
        if (status & 0x0Fu) return -1;
        *b = data;
        return 1;
    }
    return 0;
}

static int expired(uint32_t start, uint32_t ms)
{
    return (uint32_t)(SysTick->CNT - start) >= ms * TT_TICKS_PER_MS;
}

static void tx(uint8_t b)
{
    while (!(USART1->STATR & 0x80u)) {}
    USART1->DATAR = b;
}
static void ack(uint8_t error)
{
    tx(0xAA); tx(0x55); tx(0); tx(error); tx(0x55); tx(0xAA);
}
/* v0.4: restore USER mapping with a software reset. Stock Arduino applications
   linked at zero are supported; their BIN is still programmed at 0x08000000. */
static void run_app(void)
{
    /* Complete the final UART acknowledgement before resetting peripherals. */
    while (!(USART1->STATR & 0x40u)) {}
#ifndef TT_HOST_TEST
    __asm__ volatile ("csrci mstatus, 8" ::: "memory");
#endif
    /* Remove accumulated PIN/POR flags so the application's reset hook sees
       this handoff as a software reset and cannot loop back into BOOT. */
    RCC->RSTSCKR |= RCC_RMVF;
    SystemReset_StartMode(Start_Mode_USER);
#ifndef TT_HOST_TEST
    __asm__ volatile ("fence rw, rw" ::: "memory");
#endif
    NVIC_SystemReset();
#ifndef TT_HOST_TEST
    for (;;) {}
#endif
}
static int app_present(void)
{
    return *(volatile uint32_t *)TT_APP_BASE != 0xFFFFFFFFu;
}
static void clear_page(void)
{
    for (unsigned i = 0; i < 64; ++i) page[i] = 0xFFFFFFFFu;
}
static int write_page(void)
{
    if (program_addr >= TT_APP_BASE + TT_APP_SIZE) return 0;
    if (FLASH_ROM_WRITE(program_addr, page, 256) != FLASH_COMPLETE) return 0;
    /* Read-back check before acknowledging programming. */
    for (unsigned i = 0; i < 64; ++i)
        if (*(volatile uint32_t *)(program_addr + 4u*i) != page[i]) return 0;
    program_addr += 256;
    used = 0;
    clear_page();
    return 1;
}

/* All packet reads share one deadline: a partial packet cannot hang IAP. */
static int read_byte(uint8_t *b, uint32_t start)
{
    while (!expired(start, TT_PACKET_TIMEOUT_MS)) {
        int r = rx(b);
        if (r) return r > 0;
    }
    return 0;
}
static int packet(uint8_t *cmd, uint8_t *len)
{
    uint8_t b;
    uint16_t sum;
    uint32_t start = SysTick->CNT;
    if (!read_byte(&b, start) || b != 0x55) return 0;
    if (!read_byte(cmd, start) || !read_byte(len, start)) return 0;
    if (*len > 64) return 0;
    unsigned extra = (*cmd == 0x81 || *cmd == 0x82) ? 4u : 0u;
    unsigned count = extra;
    if (*cmd == 0x80 || *cmd == 0x82) count += *len;
    else if (*len != 0) return 0;
    sum = (uint16_t)*cmd + *len;
    for (unsigned i = 0; i < count; ++i) {
        if (!read_byte(&payload[i], start)) return 0;
        sum += payload[i];
    }
    if (!read_byte(&b, start) || b != (uint8_t)sum) return 0;
    if (!read_byte(&b, start) || b != (uint8_t)(sum >> 8)) return 0;
    if (!read_byte(&b, start) || b != 0x55) return 0;
    return read_byte(&b, start) && b == 0xAA;
}
static int command(uint8_t cmd, uint8_t len)
{
    switch (cmd) {
    case 0x81: /* Erase user Flash only; BOOT is outside this range. */
        erased = flushed = verified = 0;
        if (FLASH_ROM_ERASE(TT_APP_BASE, TT_APP_SIZE) != FLASH_COMPLETE) return 0;
        program_addr = verify_addr = TT_APP_BASE;
        used = 0;
        received = 0;
        clear_page();
        erased = 1;
        return 1;
    case 0x80:
        if (!erased || flushed || !len ||
            program_addr + used + len > TT_APP_BASE + TT_APP_SIZE) return 0;
        for (unsigned i = 0; i < len; ++i) {
            ((uint8_t *)page)[used++] = payload[i];
            if (used == 256 && !write_page()) return 0;
        }
        received += len;
        return 1;
    case 0x82:
        if (!erased || !len) return 0;
        if (!flushed) {
            if (used && !write_page()) return 0;
            flushed = 1;
        }
        if (verify_addr + len > TT_APP_BASE + received) return 0;
        for (unsigned i = 0; i < len; ++i) {
            if (*(volatile uint8_t *)(verify_addr + i) != payload[4u + i]) return 0;
        }
        verify_addr += len;
        verified = 1;
        return 1;
    case 0x83:
        if (!verified || verify_addr != TT_APP_BASE + received || !app_present()) return 0;
        ack(0);
        run_app();
        return 1;
    case 0x84: return 1; /* already in IAP */
    default: return 0;
    }
}

int main(void)
{
    uint8_t b, match = 0;
    uart_init();
    uint32_t start = SysTick->CNT;
    while (!expired(start, TT_BOOT_WINDOW_MS)) {
        int r = rx(&b);
        if (r < 0) match = 0;
        if (r > 0 && tt_phrase_feed(&match, b)) { ack(0); goto iap; }
    }
    if (app_present()) run_app();
    /* An erased application stays recoverable; silent until the key arrives. */
iap:
    match = 0;
    for (;;) {
        int r = rx(&b);
        if (r < 0) { match = 0; continue; }
        if (!r) continue;
        /* Repeated entry phrases re-ACK if the host missed the first reply. */
        if (tt_phrase_feed(&match, b)) ack(0);
        if (b == 0xAA) {
            uint8_t cmd, len;
            match = 0;
            if (packet(&cmd, &len)) ack(command(cmd, len) ? 0 : 1);
        }
    }
}

/* WCH FLASH SUPPORT - retained from pinned vendor SDK. */
#ifndef TT_HOST_TEST
/********************************** (C) COPYRIGHT  *******************************
 * File Name          : ch32v00X_flash.c
 * Author             : WCH
 * Version            : V1.0.3
 * Date               : 2026/08/12
 * Description        : This file provides all the FLASH firmware functions.
 *********************************************************************************
 * Copyright (c) 2021 Nanjing Qinheng Microelectronics Co., Ltd.
 * Attention: This software (modified or not) and binary are used for 
 * microcontroller manufactured by Nanjing Qinheng Microelectronics.
 *******************************************************************************/
#include <ch32v00X_flash.h>

/* Flash Access Control Register bits */
#define ACR_LATENCY_Mask           ((uint32_t)0xFFFFFFFC)

/* Flash Control Register bits */
#define CR_PER_Set                 ((uint32_t)0x00000002)
#define CR_PER_Reset               ((uint32_t)0xFFFFFFFD)
#define CR_MER_Set                 ((uint32_t)0x00000004)
#define CR_MER_Reset               ((uint32_t)0xFFFFFFFB)
#define CR_OPTER_Set               ((uint32_t)0x00000020)
#define CR_OPTER_Reset             ((uint32_t)0xFFFFFFDF)
#define CR_STRT_Set                ((uint32_t)0x00000040)
#define CR_LOCK_Set                ((uint32_t)0x00000080)
#define CR_FLOCK_Set               ((uint32_t)0x00008000)
#define CR_PAGE_PG                 ((uint32_t)0x00010000)
#define CR_PAGE_ER                 ((uint32_t)0x00020000)
#define CR_PAGE_ER_Reset           ((uint32_t)0xFFFDFFFF)
#define CR_BUF_LOAD                ((uint32_t)0x00040000)
#define CR_BUF_RST                 ((uint32_t)0x00080000)
#define CR_BER32                   ((uint32_t)0x00800000)

/* FLASH Status Register bits */
#define SR_BSY                     ((uint32_t)0x00000001)
#define SR_WRPRTERR                ((uint32_t)0x00000010)
#define SR_EOP                     ((uint32_t)0x00000020)

/* FLASH Mask */
#define RDPRT_Mask                 ((uint32_t)0x00000002)
#define WRP0_Mask                  ((uint32_t)0x000000FF)
#define WRP1_Mask                  ((uint32_t)0x0000FF00)
#define WRP2_Mask                  ((uint32_t)0x00FF0000)
#define WRP3_Mask                  ((uint32_t)0xFF000000)

/* FLASH Keys */
#define RDP_Key                    ((uint16_t)0x00A5)
#define FLASH_KEY1                 ((uint32_t)0x45670123)
#define FLASH_KEY2                 ((uint32_t)0xCDEF89AB)

/* Delay definition */
#define EraseTimeout               ((uint32_t)0x10000000)
#define ProgramTimeout             ((uint32_t)0x10000000)

/* Flash Program Valid Address */
#define ValidAddrStart             (FLASH_BASE)

#if defined(CH32V002)
#define ValidAddrEnd               (FLASH_BASE + 0x4000)

#elif defined(CH32V004) || defined(CH32V005)
#define ValidAddrEnd               (FLASH_BASE + 0x8000)

#elif defined(CH32V006) || defined(CH32V007_M007)
#define ValidAddrEnd               (FLASH_BASE + 0xF800)

#endif

/* FLASH Size */
#define Size_256B                  0x100
#define Size_1KB                   0x400
#define Size_32KB                  0x8000

/********************************************************************************
 * @fn      FLASH_SetLatency
 *
 * @brief   Sets the code latency value.
 *
 * @param   FLASH_Latency - specifies the FLASH Latency value.
 *          FLASH_Latency_0 - FLASH Zero Latency cycle
 *          FLASH_Latency_1 - FLASH One Latency cycle
 *          FLASH_Latency_2 - FLASH Two Latency cycles
 *
 * @return  None
 */
void FLASH_SetLatency(uint32_t FLASH_Latency)
{
    uint32_t tmpreg = 0;

    tmpreg = FLASH->ACTLR;
    tmpreg &= ACR_LATENCY_Mask;
    tmpreg |= FLASH_Latency;
    FLASH->ACTLR = tmpreg;
}

/********************************************************************************
 * @fn      FLASH_Unlock
 *
 * @brief   Unlocks the FLASH Program Erase Controller.
 *
 * @return  None
 */
void FLASH_Unlock(void)
{
    /* Authorize the FPEC of Bank1 Access */
    FLASH->KEYR = FLASH_KEY1;
    FLASH->KEYR = FLASH_KEY2;
}

/********************************************************************************
 * @fn      FLASH_Lock
 *
 * @brief   Locks the FLASH Program Erase Controller.
 *
 * @return  None
 */
void FLASH_Lock(void)
{
    FLASH->CTLR |= CR_LOCK_Set;
}

/********************************************************************************
 * @fn      FLASH_ErasePage
 *
 * @brief   Erases a specified FLASH page(1KB).
 *
 * @param   Page_Address - The page address to be erased.
 *
 * @return  FLASH Status - The returned value can be: FLASH_BUSY, FLASH_ERROR_PG,
 *          FLASH_ERROR_WRP, FLASH_COMPLETE or FLASH_TIMEOUT.
 */
FLASH_Status FLASH_ErasePage(uint32_t Page_Address)
{
    FLASH_Status status = FLASH_COMPLETE;

    status = FLASH_WaitForLastOperation(EraseTimeout);

    if(status == FLASH_COMPLETE)
    {
        FLASH->CTLR &= (CR_OPTER_Reset & CR_PAGE_ER_Reset);
        FLASH->CTLR |= CR_PER_Set;
        FLASH->ADDR = Page_Address;
        FLASH->CTLR |= CR_STRT_Set;

        status = FLASH_WaitForLastOperation(EraseTimeout);

        FLASH->CTLR &= CR_PER_Reset;
    }

    return status;
}

/********************************************************************************
 * @fn      FLASH_EraseAllPages
 *
 * @brief   Erases all FLASH pages.
 *
 * @return  FLASH Status - The returned value can be:FLASH_BUSY, FLASH_ERROR_PG,
 *          FLASH_ERROR_WRP, FLASH_COMPLETE or FLASH_TIMEOUT.
 */
FLASH_Status FLASH_EraseAllPages(void)
{
    FLASH_Status status = FLASH_COMPLETE;

    status = FLASH_WaitForLastOperation(EraseTimeout);
    if(status == FLASH_COMPLETE)
    {
        FLASH->CTLR &= (CR_OPTER_Reset & CR_PAGE_ER_Reset);
        FLASH->CTLR |= CR_MER_Set;
        FLASH->CTLR |= CR_STRT_Set;

        status = FLASH_WaitForLastOperation(EraseTimeout);

        FLASH->CTLR &= CR_MER_Reset;
    }

    return status;
}

/********************************************************************************
 * @fn      FLASH_EraseOptionBytes
 *
 * @brief   Erases the FLASH option bytes.
 *
 * @return  FLASH Status - The returned value can be: FLASH_BUSY, FLASH_ERROR_PG,
 *          FLASH_ERROR_WRP, FLASH_COMPLETE or FLASH_TIMEOUT.
 */
FLASH_Status FLASH_EraseOptionBytes(void)
{
    FLASH_Status status = FLASH_COMPLETE;

    status = FLASH_WaitForLastOperation(EraseTimeout);
    if(status == FLASH_COMPLETE)
    {
        FLASH_Unlock();

        FLASH->OBKEYR = FLASH_KEY1;
        FLASH->OBKEYR = FLASH_KEY2;

        FLASH->CTLR &= (CR_OPTER_Reset & CR_PAGE_ER_Reset);
        FLASH->CTLR |= CR_OPTER_Set;
        FLASH->CTLR |= CR_STRT_Set;
        status = FLASH_WaitForLastOperation(EraseTimeout);

        FLASH->CTLR &= CR_OPTER_Reset;

        FLASH_Lock();
    }
    return status;
}

/*********************************************************************
 * @fn      FLASH_OptionBytePR
 *
 * @brief   Programs option bytes.
 *
 * @param   pbuf - data.
 *
 * @return  none
 */
void FLASH_OptionBytePR(u32* pbuf)
{
    uint8_t i;

    FLASH_EraseOptionBytes();
    FLASH_Unlock_Fast();
    FLASH_BufReset();

    for(i=0; i<4; i++)
    {
        FLASH_BufLoad((OB_BASE + 4*i), *pbuf++);
    }

    FLASH_ProgramPage_Fast(OB_BASE);
    FLASH_Lock_Fast();
}

/*********************************************************************
 * @fn      FLASH_EnableWriteProtection
 *
 * @brief   Write protects the desired sectors
 *
 * @param   FLASH_Pages - specifies the address of the pages to be write protected.
 *
 * @return  FLASH Status - The returned value can be: FLASH_BUSY, FLASH_ERROR_PG,
 *          FLASH_ERROR_WRP, FLASH_COMPLETE , FLASH_TIMEOUT or FLASH_RDP.
 */
FLASH_Status FLASH_EnableWriteProtection(uint32_t FLASH_Pages)
{
    uint8_t     WRP0_Data = 0xFF, WRP1_Data = 0xFF, WRP2_Data = 0xFF, WRP3_Data = 0xFF;
    uint32_t buf[4];
    uint8_t i;
    FLASH_Status status = FLASH_COMPLETE;

    if((FLASH->OBR & RDPRT_Mask) != (uint32_t)RESET)
    {
        status = FLASH_RDP;
    }
    else{
        FLASH_Pages = (uint32_t)(~FLASH_Pages);
        WRP0_Data = (uint8_t)(FLASH_Pages & WRP0_Mask);
        WRP1_Data = (uint8_t)((FLASH_Pages & WRP1_Mask) >> 8);
        WRP2_Data = (uint8_t)((FLASH_Pages & WRP2_Mask) >> 16);
        WRP3_Data = (uint8_t)((FLASH_Pages & WRP3_Mask) >> 24);

        status = FLASH_WaitForLastOperation(ProgramTimeout);

        if(status == FLASH_COMPLETE)
        {
            for(i=0; i<4; i++){
                buf[i] = *(uint32_t*)(OB_BASE + 4*i);
            }

            buf[2] = ((uint32_t)(((uint32_t)(WRP0_Data) & 0x00FF) + (((uint32_t)(~WRP0_Data) & 0x00FF) << 8) \
                   + (((uint32_t)(WRP1_Data) & 0x00FF) << 16) + (((uint32_t)(~WRP1_Data) & 0x00FF) << 24)));
            buf[3] = ((uint32_t)(((uint32_t)(WRP2_Data) & 0x00FF) + (((uint32_t)(~WRP2_Data) & 0x00FF) << 8) \
                   + (((uint32_t)(WRP3_Data) & 0x00FF) << 16) + (((uint32_t)(~WRP3_Data) & 0x00FF) << 24)));

            FLASH_OptionBytePR(buf);
        }
    }

    return status;
}

/*********************************************************************
 * @fn      FLASH_EnableReadOutProtection
 *
 * @brief   Enables the read out protection.
 *
 * @return  FLASH Status - The returned value can be: FLASH_BUSY, FLASH_ERROR_PG,
 *          FLASH_ERROR_WRP, FLASH_COMPLETE, FLASH_TIMEOUT or FLASH_RDP.
 */
FLASH_Status FLASH_EnableReadOutProtection(void)
{
    FLASH_Status status = FLASH_COMPLETE;
    uint32_t buf[4];
    uint8_t i;

    if((FLASH->OBR & RDPRT_Mask) != (uint32_t)RESET)
    {
        status = FLASH_RDP;
    }
    else{
        status = FLASH_WaitForLastOperation(EraseTimeout);
        if(status == FLASH_COMPLETE)
        {
            for(i=0; i<4; i++){
                buf[i] = *(uint32_t*)(OB_BASE + 4*i);
            }

            buf[0] = 0x000000FF + (buf[0] & 0xFFFF0000);
            FLASH_OptionBytePR(buf);
        }
    }

    return status;
}

/*********************************************************************
 * @fn      FLASH_UserOptionByteConfig
 *
 * @brief   Programs the FLASH User Option Byte - IWDG_SW / RST_STOP /
 *        RST_STDBY / OB_PowerON_Start_Mode.
 *
 * @param   OB_IWDG - Selects the IWDG mode
 *            OB_IWDG_SW - Software IWDG selected
 *            OB_IWDG_HW - Hardware IWDG selected
 *          OB_STDBY - Reset event when entering Standby mode.
 *            OB_STDBY_NoRST - No reset generated when entering in STANDBY.
 *            OB_STDBY_RST - Reset generated when entering in STANDBY.
 *          OB_RST - Selects the reset IO mode and Ignore delay time.
 *            OB_RST_NoEN - Reset IO disable.
 *            OB_RST_EN_DT12ms - Reset IO enable and  Ignore delay time 12ms.
 *            OB_RST_EN_DT1ms - Reset IO enable and  Ignore delay time 1ms.
 *            OB_RST_EN_DT128us - Reset IO enable and  Ignore delay time 128us.
 *          OB_PowerON_Start_Mode - Selects start mode after power on.
 *            OB_PowerON_Start_Mode_BOOT - Boot start after power on.
 *            OB_PowerON_Start_Mode_USER - User start after power on.
 *
 * @return  FLASH Status - The returned value can be: FLASH_BUSY, FLASH_ERROR_PG,
 *        FLASH_ERROR_WRP, FLASH_COMPLETE, FLASH_TIMEOUT or FLASH_RDP.
 */
FLASH_Status FLASH_UserOptionByteConfig(uint16_t OB_IWDG, uint16_t OB_STDBY, uint16_t OB_RST, uint16_t OB_PowerON_Start_Mode)
{
    FLASH_Status status = FLASH_COMPLETE;
    uint8_t UserByte;
    uint32_t buf[4];
    uint8_t i;

    if((FLASH->OBR & RDPRT_Mask) != (uint32_t)RESET)
    {
        status = FLASH_RDP;
    }
    else{
        UserByte = OB_IWDG | (uint16_t)(OB_STDBY | (uint16_t)(OB_RST | (uint16_t)(OB_PowerON_Start_Mode | 0xC2)));

        for(i=0; i<4; i++){
            buf[i] = *(uint32_t*)(OB_BASE + 4*i);
        }
        buf[0] = ((uint32_t)((((uint32_t)(UserByte) & 0x00FF) << 16) + (((uint32_t)(~UserByte) & 0x00FF) << 24))) + 0x00005AA5;

        FLASH_OptionBytePR(buf);
    }

    return status;
}

/*********************************************************************
 * @fn      FLASH_GetUserOptionByte
 *
 * @brief   Returns the FLASH User Option Bytes values.
 *
 * @return  The FLASH User Option Bytes values:IWDG_SW(Bit0), RST_STDBY(Bit2)
 *          , RST_MODE(Bit[3:4]) and START_MODE(Bit5).
 */
uint32_t FLASH_GetUserOptionByte(void)
{
    return (uint32_t)(FLASH->OBR >> 2);
}

/*********************************************************************
 * @fn      FLASH_GetWriteProtectionOptionByte
 *
 * @brief   Returns the FLASH Write Protection Option Bytes Register value.
 *
 * @return  The FLASH Write Protection Option Bytes Register value.
 */
uint32_t FLASH_GetWriteProtectionOptionByte(void)
{
    return (uint32_t)(FLASH->WPR);
}

/*********************************************************************
 * @fn      FLASH_GetReadOutProtectionStatus
 *
 * @brief   Checks whether the FLASH Read Out Protection Status is set or not.
 *
 * @return  FLASH ReadOut Protection Status(SET or RESET)
 */
FlagStatus FLASH_GetReadOutProtectionStatus(void)
{
    FlagStatus readoutstatus = RESET;
    if((FLASH->OBR & RDPRT_Mask) != (uint32_t)RESET)
    {
        readoutstatus = SET;
    }
    else
    {
        readoutstatus = RESET;
    }
    return readoutstatus;
}

/*********************************************************************
 * @fn      FLASH_ITConfig
 *
 * @brief   Enables or disables the specified FLASH interrupts.
 *
 * @param   FLASH_IT - specifies the FLASH interrupt sources to be enabled or disabled.
 *            FLASH_IT_ERROR - FLASH Error Interrupt.
 *            FLASH_IT_EOP - FLASH end of operation Interrupt.
 *            FLASH_IT_FWAKE - FLASH Wake Up Interrupt.
 *          NewState - new state of the specified Flash interrupts(ENABLE or DISABLE).
 *
 * @return  FLASH Prefetch Buffer Status (SET or RESET).
 */
void FLASH_ITConfig(uint32_t FLASH_IT, FunctionalState NewState)
{
    if(NewState != DISABLE)
    {
        FLASH->CTLR |= FLASH_IT;
    }
    else
    {
        FLASH->CTLR &= ~(uint32_t)FLASH_IT;
    }
}

/*********************************************************************
 * @fn      FLASH_GetFlagStatus
 *
 * @brief   Checks whether the specified FLASH flag is set or not.
 *
 * @param   FLASH_FLAG - specifies the FLASH flag to check.
 *            FLASH_FLAG_BSY - FLASH Busy flag
 *            FLASH_FLAG_WRPRTERR - FLASH Write protected error flag
 *            FLASH_FLAG_EOP - FLASH End of Operation flag
 *            FLASH_FLAG_FWAKE - FLASH Wake Up flag
 *            FLASH_FLAG_OPTERR - FLASH Option Byte error flag
 *
 * @return  The new state of FLASH_FLAG (SET or RESET).
 */
FlagStatus FLASH_GetFlagStatus(uint32_t FLASH_FLAG)
{
    FlagStatus bitstatus = RESET;

    if(FLASH_FLAG == FLASH_FLAG_OPTERR)
    {
        if((FLASH->OBR & (1<<0)) != (uint32_t)RESET)
        {
            bitstatus = SET;
        }
        else
        {
            bitstatus = RESET;
        }
    }
    else
    {
        if((FLASH->STATR & FLASH_FLAG) != (uint32_t)RESET)
        {
            bitstatus = SET;
        }
        else
        {
            bitstatus = RESET;
        }
    }
    return bitstatus;
}

/*********************************************************************
 * @fn      FLASH_ClearFlag
 *
 * @brief   Clears the FLASH's pending flags.
 *
 * @param   FLASH_FLAG - specifies the FLASH flags to clear.
 *            FLASH_FLAG_WRPRTERR - FLASH Write protected error flag
 *            FLASH_FLAG_EOP - FLASH End of Operation flag
 *            FLASH_FLAG_FWAKE - FLASH Wake Up flag
 *
 * @return  none
 */
void FLASH_ClearFlag(uint32_t FLASH_FLAG)
{
    if(FLASH_FLAG == FLASH_FLAG_FWAKE)
    {
        FLASH->STATR &= ~FLASH_FLAG;
    }
    else
    {
        FLASH->STATR = FLASH_FLAG;
    }
}

/*********************************************************************
 * @fn      FLASH_GetStatus
 *
 * @brief   Returns the FLASH Status.
 *
 * @return  FLASH Status - The returned value can be: FLASH_BUSY, FLASH_ERROR_PG,
 *          FLASH_ERROR_WRP or FLASH_COMPLETE.
 */
FLASH_Status FLASH_GetStatus(void)
{
    FLASH_Status flashstatus = FLASH_COMPLETE;

    if((FLASH->STATR & FLASH_FLAG_BSY) == FLASH_FLAG_BSY)
    {
        flashstatus = FLASH_BUSY;
    }
    else
    {
        if((FLASH->STATR & FLASH_FLAG_WRPRTERR) != 0)
        {
            flashstatus = FLASH_ERROR_WRP;
        }
        else
        {
            flashstatus = FLASH_COMPLETE;
        }
    }
    return flashstatus;
}

/*********************************************************************
 * @fn      FLASH_GetBank1Status
 *
 * @brief   Returns the FLASH Bank1 Status.
 *
 * @return  FLASH Status - The returned value can be: FLASH_BUSY, FLASH_ERROR_PG,
 *          FLASH_ERROR_WRP or FLASH_COMPLETE.
 */
FLASH_Status FLASH_GetBank1Status(void)
{
    FLASH_Status flashstatus = FLASH_COMPLETE;

    if((FLASH->STATR & FLASH_FLAG_BANK1_BSY) == FLASH_FLAG_BSY)
    {
        flashstatus = FLASH_BUSY;
    }
    else
    {
        if((FLASH->STATR & FLASH_FLAG_BANK1_WRPRTERR) != 0)
        {
            flashstatus = FLASH_ERROR_WRP;
        }
        else
        {
            flashstatus = FLASH_COMPLETE;
        }
    }
    return flashstatus;
}

/*********************************************************************
 * @fn      FLASH_WaitForLastOperation
 *
 * @brief   Waits for a Flash operation to complete or a TIMEOUT to occur.
 *
 * @param   Timeout - FLASH programming Timeout
 *
 * @return  FLASH Status - The returned value can be: FLASH_BUSY, FLASH_ERROR_PG,
 *          FLASH_ERROR_WRP or FLASH_COMPLETE.
 */
FLASH_Status FLASH_WaitForLastOperation(uint32_t Timeout)
{
    FLASH_Status status = FLASH_COMPLETE;

    status = FLASH_GetBank1Status();
    while((status == FLASH_BUSY) && (Timeout != 0x00))
    {
        status = FLASH_GetBank1Status();
        Timeout--;
    }
    if(Timeout == 0x00)
    {
        status = FLASH_TIMEOUT;
    }
    return status;
}

/*********************************************************************
 * @fn      FLASH_WaitForLastBank1Operation
 *
 * @brief   Waits for a Flash operation on Bank1 to complete or a TIMEOUT to occur.
 *
 * @param   Timeout - FLASH programming Timeout
 *
 * @return  FLASH Status - The returned value can be: FLASH_BUSY, FLASH_ERROR_PG,
 *          FLASH_ERROR_WRP or FLASH_COMPLETE.
 */
FLASH_Status FLASH_WaitForLastBank1Operation(uint32_t Timeout)
{
    FLASH_Status status = FLASH_COMPLETE;

    status = FLASH_GetBank1Status();
    while((status == FLASH_FLAG_BANK1_BSY) && (Timeout != 0x00))
    {
        status = FLASH_GetBank1Status();
        Timeout--;
    }
    if(Timeout == 0x00)
    {
        status = FLASH_TIMEOUT;
    }
    return status;
}

/*********************************************************************
 * @fn      FLASH_Unlock_Fast
 *
 * @brief   Unlocks the Fast Program Erase Mode.
 *
 * @return  none
 */
void FLASH_Unlock_Fast(void)
{
    /* Authorize the FPEC of Bank1 Access */
    FLASH->KEYR = FLASH_KEY1;
    FLASH->KEYR = FLASH_KEY2;

    /* Fast program mode unlock */
    FLASH->MODEKEYR = FLASH_KEY1;
    FLASH->MODEKEYR = FLASH_KEY2;
}

/*********************************************************************
 * @fn      FLASH_Lock_Fast
 *
 * @brief   Locks the Fast Program Erase Mode.
 *
 * @return  none
 */
void FLASH_Lock_Fast(void)
{
    FLASH->CTLR |= CR_FLOCK_Set;
}

/*********************************************************************
 * @fn      FLASH_BufReset
 *
 * @brief   Flash Buffer reset.
 *
 * @return  none
 */
void FLASH_BufReset(void)
{
    FLASH->CTLR &= (CR_OPTER_Reset & CR_PAGE_ER_Reset);

    FLASH->CTLR |= CR_PAGE_PG;
    FLASH->CTLR |= CR_BUF_RST;
    while(FLASH->STATR & SR_BSY)
        ;
    FLASH->CTLR &= ~CR_PAGE_PG;
}

/*********************************************************************
 * @fn      FLASH_BufLoad
 *
 * @brief   Flash Buffer load(4Byte).
 *
 * @param   Address - specifies the address to be programmed.
 *          Data0 - specifies the data0 to be programmed.
 *
 * @return  none
 */
void FLASH_BufLoad(uint32_t Address, uint32_t Data0)
{
    if(((Address >= ValidAddrStart) && (Address < ValidAddrEnd)) || ((Address >= OB_BASE) && (Address < OB_BASE+0x100)))
    {
        FLASH->CTLR &= (CR_OPTER_Reset & CR_PAGE_ER_Reset);

        FLASH->CTLR |= CR_PAGE_PG;
        *(__IO uint32_t *)(Address) = Data0;
        FLASH->CTLR |= CR_BUF_LOAD;
        while(FLASH->STATR & SR_BSY)
            ;
        FLASH->CTLR &= ~CR_PAGE_PG;
    }
}

/*********************************************************************
 * @fn      FLASH_ErasePage_Fast
 *
 * @brief   Erases a specified FLASH page (1page = 256Byte).
 *
 * @param   Page_Address - The page address to be erased.
 *
 * @return  none
 */
void FLASH_ErasePage_Fast(uint32_t Page_Address)
{
    if((Page_Address >= ValidAddrStart) && (Page_Address < ValidAddrEnd))
    {
        FLASH->CTLR &= (CR_OPTER_Reset & CR_PAGE_ER_Reset);

        FLASH->CTLR |= CR_PAGE_ER;
        FLASH->ADDR = Page_Address;
        FLASH->CTLR |= CR_STRT_Set;
        while(FLASH->STATR & SR_BSY)
            ;
        FLASH->CTLR &= ~CR_PAGE_ER;
    }
}

/*********************************************************************
 * @fn      FLASH_EraseBlock_32K_Fast
 *
 * @brief   Erases a specified FLASH Block (1Block = 32KByte).
 *
 * @param   Block_Address - The block address to be erased.
 *          This function is only capable of erasing addresses
 *          in the range of 0x08000000~0x08008000.
 *
 * @return  none
 */
void FLASH_EraseBlock_32K_Fast(uint32_t Block_Address)
{
    FLASH->CTLR &= (CR_OPTER_Reset & CR_PAGE_ER_Reset);

    Block_Address &= 0xFFFF8000;

    FLASH->CTLR |= CR_BER32;
    FLASH->ADDR = Block_Address;
    FLASH->CTLR |= CR_STRT_Set;
    while(FLASH->STATR & SR_BSY)
        ;
    FLASH->CTLR &= ~CR_BER32;
}

/*********************************************************************
 * @fn      FLASH_ProgramPage_Fast
 *
 * @brief   Program a specified FLASH page (1page = 256Byte).
 *
 * @param   Page_Address - The page address to be programed.
 *
 * @return  none
 */
void FLASH_ProgramPage_Fast(uint32_t Page_Address)
{
    if(((Page_Address >= ValidAddrStart) && (Page_Address < ValidAddrEnd)) || (Page_Address == OB_BASE))
    {
        FLASH->CTLR &= (CR_OPTER_Reset & CR_PAGE_ER_Reset);

        FLASH->CTLR |= CR_PAGE_PG;
        FLASH->ADDR = Page_Address;
        FLASH->CTLR |= CR_STRT_Set;
        while(FLASH->STATR & SR_BSY)
            ;
        FLASH->CTLR &= ~CR_PAGE_PG;
    }
}

/*********************************************************************
 * @fn      SystemReset_StartMode
 *
 * @brief   Start mode after system reset.
 *
 * @param   Mode - Start mode.
 *            Start_Mode_USER - USER start after system reset
 *            Start_Mode_BOOT - Boot start after system reset
 *
 * @return  none
 */
void SystemReset_StartMode(uint32_t Mode)
{
    FLASH_Unlock();

    FLASH->BOOT_MODEKEYR = FLASH_KEY1;
    FLASH->BOOT_MODEKEYR = FLASH_KEY2;

    FLASH->STATR &= ~(1<<14);
    if(Mode == Start_Mode_BOOT){
        FLASH->STATR |= (1<<14);
    }

    FLASH_Lock();
}

/*********************************************************************
 * @fn      ROM_ERASE
 *
 * @brief   Select erases a specified FLASH .
 *
 * @param   StartAddr - Erases Flash start address(StartAddr%256 == 0).
 *          Cnt - Erases count.
 *          Erase_Size - Erases size select.The returned value can be:
 *            Size_32KB, Size_1KB, Size_256B.
 *
 * @return  none.
 */
static void ROM_ERASE(uint32_t StartAddr, uint32_t Cnt, uint32_t Erase_Size)
{
    FLASH->CTLR &= (CR_OPTER_Reset & CR_PAGE_ER_Reset);

    do{
        if(Erase_Size == Size_32KB)
        {
            FLASH->CTLR |= CR_BER32;
        }
        else if(Erase_Size == Size_1KB)
        {
            FLASH->CTLR |= CR_PER_Set;
        }
        else if(Erase_Size == Size_256B)
        {
            FLASH->CTLR |= CR_PAGE_ER;
        }

        FLASH->ADDR = StartAddr;
        FLASH->CTLR |= CR_STRT_Set;
        while(FLASH->STATR & SR_BSY)
            ;

        if(Erase_Size == Size_32KB)
        {
            FLASH->CTLR &= ~CR_BER32;
            StartAddr += Size_32KB;
        }
        else if(Erase_Size == Size_1KB)
        {
            FLASH->CTLR &= ~CR_PER_Set;
            StartAddr += Size_1KB;
        }
        else if(Erase_Size == Size_256B)
        {
            FLASH->CTLR &= ~CR_PAGE_ER;
            StartAddr += Size_256B;
        }
    }while(--Cnt);
}

/*********************************************************************
 * @fn      FLASH_ROM_ERASE
 *
 * @brief   Erases a specified FLASH .
 *
 * @param   StartAddr - Erases Flash start address(StartAddr%256 == 0).
 *          Length - Erases Flash start Length(Length%256 == 0).
 *          Recommended for FLASH erasing.
 *
 * @return  FLASH Status - The returned value can be: FLASH_ADR_RANGE_ERROR,
 *        FLASH_ALIGN_ERROR, FLASH_OP_RANGE_ERROR or FLASH_COMPLETE.
 */
FLASH_Status FLASH_ROM_ERASE( uint32_t StartAddr, uint32_t Length )
{
    uint32_t Addr0 = 0, Addr1 = 0, Length0 = 0, Length1 = 0;

    FLASH_Status status = FLASH_COMPLETE;

    if((StartAddr < ValidAddrStart) || (StartAddr >= ValidAddrEnd))
    {
        return FLASH_ADR_RANGE_ERROR;
    }

    if((StartAddr + Length) > ValidAddrEnd)
    {
        return FLASH_OP_RANGE_ERROR;
    }

    if((StartAddr & (Size_256B-1)) || (Length & (Size_256B-1)) || (Length == 0))
    {
        return FLASH_ALIGN_ERROR;
    }

    /* Authorize the FPEC of Bank1 Access */
    FLASH->KEYR = FLASH_KEY1;
    FLASH->KEYR = FLASH_KEY2;

    /* Fast program mode unlock */
    FLASH->MODEKEYR = FLASH_KEY1;
    FLASH->MODEKEYR = FLASH_KEY2;

    Addr0 = StartAddr;

    if(Length >= Size_32KB)
    {
        Length0 = Size_32KB - (Addr0 & (Size_32KB - 1));
        Addr1 = StartAddr + Length0;
        Length1 = Length - Length0;
    }
    else if(Length >= Size_1KB)
    {
        Length0 = Size_1KB - (Addr0 & (Size_1KB - 1));
        Addr1 = StartAddr + Length0;
        Length1 = Length - Length0;
    }
    else if(Length >= Size_256B)
    {
        Length0 = Length;
    }

    /* Erase 32KB */
    if(Length0 >= Size_32KB)//front
    {
        Length = Length0;
        if(Addr0 & (Size_32KB - 1))
        {
            Length0 = Size_32KB - (Addr0 & (Size_32KB - 1));
        }
        else
        {
            Length0 = 0;
        }

        ROM_ERASE((Addr0 + Length0), ((Length - Length0) >> 15), Size_32KB);
    }

    if(Length1 >= Size_32KB)//back
    {
        StartAddr = Addr1;
        Length = Length1;

        if((Addr1 + Length1) & (Size_32KB - 1))
        {
            Addr1 = ((StartAddr + Length1) & (~(Size_32KB - 1)));
            Length1 = (StartAddr + Length1) & (Size_32KB - 1);
        }
        else
        {
            Length1 = 0;
        }

        ROM_ERASE(StartAddr, ((Length - Length1) >> 15), Size_32KB);
    }

    /* Erase 1KB */
    if(Length0 >= Size_1KB) //front
    {
        Length = Length0;
        if(Addr0 & (Size_1KB - 1))
        {
            Length0 = Size_1KB - (Addr0 & (Size_1KB - 1));
        }
        else
        {
            Length0 = 0;
        }

        ROM_ERASE((Addr0 + Length0), ((Length - Length0) >> 10), Size_1KB);
    }

    if(Length1 >= Size_1KB) //back
    {
        StartAddr = Addr1;
        Length = Length1;

        if((Addr1 + Length1) & (Size_1KB - 1))
        {
            Addr1 = ((StartAddr + Length1) & (~(Size_1KB - 1)));
            Length1 = (StartAddr + Length1) & (Size_1KB - 1);
        }
        else
        {
            Length1 = 0;
        }

        ROM_ERASE(StartAddr, ((Length - Length1) >> 10), Size_1KB);
    }

    /* Erase 256B */
    if(Length0)//front
    {
        ROM_ERASE(Addr0, (Length0 >> 8), Size_256B);
    }

    if(Length1)//back
    {
        ROM_ERASE(Addr1, (Length1 >> 8), Size_256B);
    }

    FLASH->CTLR |= CR_FLOCK_Set;
    FLASH->CTLR |= CR_LOCK_Set;

    return status;
}

/*********************************************************************
 * @fn      FLASH_ROM_WRITE
 *
 * @brief   Writes a specified FLASH .
 *
 * @param   StartAddr - Writes Flash start address(StartAddr%256 == 0).
 *          Length - Writes Flash start Length(Length%256 == 0).
 *          pbuf - Writes Flash value buffer.
 *          Recommended for FLASH programming.
 *
 * @return  FLASH Status - The returned value can be: FLASH_ADR_RANGE_ERROR,
 *        FLASH_ALIGN_ERROR, FLASH_OP_RANGE_ERROR or FLASH_COMPLETE.
 */
FLASH_Status FLASH_ROM_WRITE( uint32_t StartAddr, uint32_t *pbuf, uint32_t Length )
{
    uint32_t i, adr;
    uint8_t size;

    FLASH_Status status = FLASH_COMPLETE;

    if((StartAddr < ValidAddrStart) || (StartAddr >= ValidAddrEnd))
    {
        return FLASH_ADR_RANGE_ERROR;
    }

    if((StartAddr + Length) > ValidAddrEnd)
    {
        return FLASH_OP_RANGE_ERROR;
    }

    if((StartAddr & (Size_256B-1)) || (Length & (Size_256B-1)) || (Length == 0))
    {
        return FLASH_ALIGN_ERROR;
    }
    adr = StartAddr;
    i = Length >> 8;

    /* Authorize the FPEC of Bank1 Access */
    FLASH->KEYR = FLASH_KEY1;
    FLASH->KEYR = FLASH_KEY2;

    /* Fast program mode unlock */
    FLASH->MODEKEYR = FLASH_KEY1;
    FLASH->MODEKEYR = FLASH_KEY2;

    FLASH->CTLR &= (CR_OPTER_Reset & CR_PAGE_ER_Reset);

    do{
        FLASH->CTLR |= CR_PAGE_PG;
        FLASH->CTLR |= CR_BUF_RST;
        while(FLASH->STATR & SR_BSY)
            ;
        size = 64;
        while(size)
        {
            *(uint32_t *)StartAddr = *(uint32_t *)pbuf;
            FLASH->CTLR |= CR_BUF_LOAD;
            while(FLASH->STATR & SR_BSY)
                ;
            StartAddr += 4;
            pbuf += 1;
            size -= 1;
        }

        FLASH->ADDR = adr;
        FLASH->CTLR |= CR_STRT_Set;
        while(FLASH->STATR & SR_BSY)
            ;
        FLASH->CTLR &= ~CR_PAGE_PG;
        adr += 256;
    }while(--i);

    FLASH->CTLR |= CR_FLOCK_Set;
    FLASH->CTLR |= CR_LOCK_Set;

    return status;
}

#endif /* TT_HOST_TEST */
