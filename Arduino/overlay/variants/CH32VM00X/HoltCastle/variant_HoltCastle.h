#pragma once

#define ADC_MODULE_ENABLED
#define UART_MODULE_ENABLED
#define SPI_MODULE_ENABLED
#define I2C_MODULE_ENABLED
#define TIM_MODULE_ENABLED

/* Physical CH32V006F8 pins, with the WCH core's analog pin encoding. */
#define PA1 PIN_A1
#define PA2 PIN_A0
#define PC0 2
#define PC1 3
#define PC2 4
#define PC3 5
#define PC4 PIN_A2
#define PC5 7
#define PC6 8
#define PC7 9
#define PD0 10
#define PD1 11
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

/* Connector aliases from HoltCastle006PG3p0 schematic. LED is separate from D0. */
#define D0 PD0
#define D1 PC2
#define D2 PC1
#define D3 PD3
#define D4 PD4
#define D5 PC5
#define D6 PC7
#define D7 PC6
#define D8 PC0
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
