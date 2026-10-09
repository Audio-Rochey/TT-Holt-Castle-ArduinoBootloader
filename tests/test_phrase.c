#include <assert.h>
#include <stdio.h>
#define TT_HOST_TEST
#define main device_main
#include "../firmware/source/CH32V00X_IAP/User/main.c"
#undef main
static int feed(const char *s) {
    uint8_t m=0; int hits=0;
    for (; *s; ++s) hits += tt_phrase_feed(&m, (uint8_t)*s);
    return hits;
}
int main(void) {
    assert(feed("TT_ENTER_IAP")==1);
    assert(feed("TT_ENTER_IA")==0);
    assert(feed("T_ENTER_IAP")==0);
    assert(feed("TTT_ENTER_IAP")==1);
    assert(feed("TT_ENTER_XTT_ENTER_IAP")==1);
    assert(feed("noise\r\nTT_ENTER_IAP\nTT_ENTER_IAP")==2);
    assert(feed("TT_ENTER_IAX")==0);
    puts("Phrase matcher passed: exact, partial, noise, overlap, repeat.");
    return 0;
}
