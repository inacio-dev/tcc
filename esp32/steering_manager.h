/**
 * @file steering_manager.h
 * @brief Steering Control Manager for F1 Cockpit (ESP32)
 *
 * Manages an LPD3806-600BM-G5-24C incremental rotary encoder for steering control.
 * Provides smooth steering input from -100% (left) to +100% (right).
 *
 * Encoder Specifications:
 * - Model: LPD3806-600BM-G5-24C
 * - Type: Incremental rotary encoder
 * - Resolution: 600 pulses per revolution (PPR)
 * - Output: AB phase quadrature (2-channel)
 * - Operating Voltage: 5-24V DC
 * - Output Type: NPN open collector
 *
 * ESP32 Pinout:
 * - Encoder CLK (A): GPIO 12 (D12) - Fio Verde
 * - Encoder DT (B):  GPIO 13 (D13) - Fio Branco
 * - Encoder VCC: 5V (or 3.3V with pull-ups) - Fio Vermelho
 * - Encoder GND: GND - Fio Preto
 *
 * Hardware Components Required:
 * - Capacitor: 100nF (0.1µF) ceramic X7R between GPIO 12 and GND (anti-bounce filter)
 * - Capacitor: 100nF (0.1µF) ceramic X7R between GPIO 13 and GND (anti-bounce filter)
 * - Resistor: 10kΩ pull-up (OPTIONAL - ESP32 has internal pull-ups enabled in code)
 *
 * Notes:
 * - Capacitors should be placed as close as possible to ESP32 pins
 * - Internal pull-ups are enabled via INPUT_PULLUP, external resistors not required
 * - Use ceramic X7R capacitors (better thermal stability than Y5V)
 * - Center position is at 300 pulses (half of 600 PPR encoder)
 * - LPD3806 provides 600 pulses per full rotation for precise steering control
 *
 * @author F1 RC Car Project
 * @date 2025-10-13
 */

#ifndef STEERING_MANAGER_H
#define STEERING_MANAGER_H

#include <Arduino.h>

class SteeringManager {
private:
    // Pin definitions (ESP32 GPIO)
    static const int PIN_ENCODER_CLK = 12;  // CLK (A)
    static const int PIN_ENCODER_DT = 13;   // DT (B)

    // Encoder configuration
    static const int PULSES_PER_REV = 600;
    static const int CENTER_POSITION = 300;  // Center = 0% steering
    static const int MAX_POSITION = 600;     // Full right = +100%
    static const int MIN_POSITION = 0;       // Full left = -100%

    // State variables
    volatile long encoder_position;  // Raw encoder count
    volatile int last_clk;           // Last CLK state
    int current_value;               // -100 to +100%

    // Static instance for ISR
    static SteeringManager* instance;

    // Interrupt service routine
    static void IRAM_ATTR encoder_isr();

public:
    SteeringManager();

    /**
     * @brief Initialize steering encoder
     */
    void begin();

    /**
     * @brief Update steering state (call in main loop)
     */
    void update();

    /**
     * @brief Get current steering value
     * @return Steering percentage (-100 to +100%)
     */
    int get_value() const;

    /**
     * @brief Reset steering to center position
     */
    void reset();
};

#endif // STEERING_MANAGER_H
