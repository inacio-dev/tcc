/**
 * @file brake_manager.h
 * @brief Brake Control Manager for F1 Cockpit (ESP32)
 *
 * Manages an LPD3806-600BM-G5-24C incremental rotary encoder for brake control.
 * Provides smooth brake input from 0% to 100%.
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
 * - Encoder CLK (A): GPIO 27 (D27) - Fio Verde
 * - Encoder DT (B):  GPIO 14 (D14) - Fio Branco
 * - Encoder VCC: 5V (or 3.3V with pull-ups) - Fio Vermelho
 * - Encoder GND: GND - Fio Preto
 *
 * Hardware Components Required:
 * - Capacitor: 100nF (0.1µF) ceramic X7R between GPIO 27 and GND (anti-bounce filter)
 * - Capacitor: 100nF (0.1µF) ceramic X7R between GPIO 14 and GND (anti-bounce filter)
 * - Resistor: 10kΩ pull-up (OPTIONAL - ESP32 has internal pull-ups enabled in code)
 *
 * Notes:
 * - Capacitors should be placed as close as possible to ESP32 pins
 * - Internal pull-ups are enabled via INPUT_PULLUP, external resistors not required
 * - Use ceramic X7R capacitors (better thermal stability than Y5V)
 * - LPD3806 provides 600 pulses per full rotation for precise brake control
 *
 * @author F1 RC Car Project
 * @date 2025-10-13
 */

#ifndef BRAKE_MANAGER_H
#define BRAKE_MANAGER_H

#include <Arduino.h>

class BrakeManager {
private:
    // Pin definitions (ESP32 GPIO)
    static const int PIN_ENCODER_CLK = 27;  // CLK (A)
    static const int PIN_ENCODER_DT = 14;   // DT (B)

    // Encoder configuration
    static const int PULSES_PER_REV = 600;
    static const int MAX_POSITION = 600;  // Full rotation = 100% brake
    static const int MIN_POSITION = 0;    // Zero rotation = 0% brake

    // State variables
    volatile int encoder_position;  // Raw encoder count
    volatile int last_clk;          // Last CLK state
    int current_value;              // 0-100%

    // Static instance for ISR
    static BrakeManager* instance;

    // Interrupt service routine
    static void IRAM_ATTR encoder_isr();

public:
    BrakeManager();

    /**
     * @brief Initialize brake encoder
     */
    void begin();

    /**
     * @brief Update brake state (call in main loop)
     */
    void update();

    /**
     * @brief Get current brake value
     * @return Brake percentage (0-100%)
     */
    int get_value() const;

    /**
     * @brief Reset brake to zero position
     */
    void reset();
};

#endif // BRAKE_MANAGER_H
