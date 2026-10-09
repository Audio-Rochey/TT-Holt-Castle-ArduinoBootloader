
#define _GNU_SOURCE
#include <assert.h>
#include <sys/mman.h>
#include <stdio.h>
#define main device_main
#define TT_HOST_TEST
#include "../firmware/source/CH32V00X_IAP/User/main.c"
#undef main
int main(void) {
    void *memory=mmap((void*)(uintptr_t)TT_APP_BASE, TT_APP_SIZE,
        PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS|MAP_FIXED,-1,0);
    assert(memory!=(void*)-1);
    assert(!command(0x80,64)); /* must erase first */
    assert(command(0x81,0)); assert(!app_present());
    for(unsigned j=0;j<64;++j) payload[j]=(uint8_t)j;
    assert(command(0x80,64)); assert(used==64);
    assert(!app_present()); /* no premature write */
    for(unsigned k=0;k<3;++k) assert(command(0x80,64));
    assert(used==0); assert(program_addr==TT_APP_BASE+256);
    for(unsigned k=0;k<256;++k) assert(((uint8_t*)memory)[k]==(uint8_t)(k%64));
    payload[0]=42; assert(command(0x80,1));
    for(unsigned j=0;j<64;++j) payload[4+j]=(uint8_t)j;
    assert(!command(0x83,0));
    assert(command(0x82,64));
    assert(!command(0x83,0)); /* incomplete verification must not start APP */
    for(unsigned k=0;k<3;++k) assert(command(0x82,64));
    payload[4]=42; assert(command(0x82,1));
    assert(flushed); assert(program_addr==TT_APP_BASE+512);
    assert(((uint8_t*)memory)[256]==42);
    for(unsigned j=257;j<512;++j) assert(((uint8_t*)memory)[j]==255);
    assert(!command(0x80,1)); /* writes after verify prohibited */
    payload[4]=0; assert(!command(0x82,1)); /* padded tail is FF */
    assert(command(0x81,0));
    program_addr=TT_APP_BASE+TT_APP_SIZE;
    assert(!command(0x80,1)); assert(!write_page());
    assert(!command(0x82,0)); assert(!command(0xFE,0));
    mock_tick.CNT=8999999; assert(!expired(0,TT_BOOT_WINDOW_MS));
    mock_tick.CNT=9000000; assert(expired(0,TT_BOOT_WINDOW_MS));
    mock_tick.CNT=10; assert(expired(0xFFFFFFF0u,0));
    mock_tick.CNT=2990; assert(expired(0xFFFFFFF0u,1));
    mock_usart.STATR = 0x40u; /* TX complete */
    mock_rcc.RSTSCKR = 0x04000000u; /* prior pin reset */
    run_app();
    assert(mock_start_mode == Start_Mode_USER);
    assert(mock_reset_count == 1);
    assert(mock_rcc.RSTSCKR & RCC_RMVF);
    munmap(memory,TT_APP_SIZE);
    puts("Device logic passed: page boundaries, tail padding, verification, range, timeout, USER reset handoff.");
}
