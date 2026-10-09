#pragma once

#define ADC_MODULE_ENABLED
#define UART_MODULE_ENABLED
#define SPI_MODULE_ENABLED
#define I2C_MODULE_ENABLED
#define TIM_MODULE_ENABLED

/* D0..D8 are provided by WCH's digital-pin enum, not macros here.
 * The array starts in connector order so those enum values map correctly. */
#define PA1 PIN_A1
#define PA2 PIN_A0
#define PC0 8
#define PC1 2
#define PC2 1
#define PC3 12
#define PC4 PIN_A2
#define PC5 5
#define PC6 7
#define PC7 6
#define PD0 0
#define PD1 16
#define PD2 PIN_A3
#define PD3 PIN_A4
#define PD4 PIN_A7
#define PD5 PIN_A5
#define PD6 PIN_A6
#define PD7 17
#define PD5_ALT1 (PD5 | ALT1)
#define PD6_ALT1 (PD6 | ALT1)
#define NUM_DIGITAL_PINS 18
#define NUM_ANALOG_INPUTS 8
#define ADC_RESOLUTION 12

/* Connector ordering is defined in digitalPin[]. LED is separate from D0. */
#define LED_BUILTIN PD2
#define HOLT_KEEPALIVE PC4
#define USER_BTN PNUM_NOT_DEFINED
#define SERIAL_UART_INSTANCE 1
#define PIN_SERIAL_RX PD6
#define PIN_SERIAL_TX PD5
#define PIN_WIRE_SDA D2
#define PIN_WIRE_SCL D1
#define PIN_SPI_SS D8
#define PIN_SPI_MOSI D7
#define PIN_SPI_MISO D6
#define PIN_SPI_SCK D5
#define TIMER_TONE TIM2
#define TIMER_SERVO TIM1

#ifdef __cplusplus
#define SERIAL_PORT_MONITOR Serial
#define SERIAL_PORT_HARDWARE Serial
#endif
