#include "pins_arduino.h"

// D0..D8 must occupy indexes 0..8 because WCH declares those names in an enum.
const PinName digitalPin[] = {
    PD_0, PC_2, PC_1, PD_3, PD_4, PC_5, PC_7, PC_6, PC_0,
    PD_2, PA_2, PA_1, PC_3, PC_4, PD_5, PD_6, PD_1, PD_7
};
const uint32_t analogInputPin[] = {10, 11, 13, 9, 3, 14, 15, 4};
