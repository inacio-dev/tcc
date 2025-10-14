/**
 * @file throttle_manager.h
 * @brief Throttle Control Manager for F1 Cockpit (ESP32)
 *
 * Manages an LPD3806-600BM-G5-24C incremental rotary encoder for throttle control.
 * Provides smooth throttle input from 0% to 100%.
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
 * - Encoder CLK (A): GPIO 25 (D25) - Fio Verde
 * - Encoder DT (B):  GPIO 26 (D26) - Fio Branco
 * - Encoder VCC: 5V (or 3.3V with pull-ups) - Fio Vermelho
 * - Encoder GND: GND - Fio Preto
 *
 * Hardware Components Required:
 * - Capacitor: 100nF (0.1µF) ceramic X7R between GPIO 25 and GND (anti-bounce filter)
 * - Capacitor: 100nF (0.1µF) ceramic X7R between GPIO 26 and GND (anti-bounce filter)
 * - Resistor: 10kΩ pull-up (OPTIONAL - ESP32 has internal pull-ups enabled in code)
 *
 * Notes:
 * - Capacitors should be placed as close as possible to ESP32 pins
 * - Internal pull-ups are enabled via INPUT_PULLUP, external resistors not required
 * - Use ceramic X7R capacitors (better thermal stability than Y5V)
 * - LPD3806 provides 600 pulses per full rotation for precise throttle control
 *
 * @author F1 RC Car Project
 * @date 2025-10-13
 */

#ifndef THROTTLE_MANAGER_H
#define THROTTLE_MANAGER_H

#include <Arduino.h>
#include "encoder_calibration.h"

class ThrottleManager {
private:
    // Pin definitions (ESP32 GPIO)
    static const int PIN_ENCODER_CLK = 25;  // CLK (A)
    static const int PIN_ENCODER_DT = 26;   // DT (B)

    // Encoder configuration
    static const int PULSES_PER_REV = 600;
    static const int MAX_POSITION = 600;  // Full rotation = 100% throttle
    static const int MIN_POSITION = 0;    // Zero rotation = 0% throttle

    // State variables
    volatile long encoder_position;  // Raw encoder count (changed to long for unlimited range)
    volatile int last_clk;          // Last CLK state
    int current_value;              // 0-100%

    // Calibration
    EncoderCalibration calibration;

    // Static instance for ISR
    static ThrottleManager* instance;

    // Interrupt service routine
    static void IRAM_ATTR encoder_isr();

public:
    ThrottleManager();

    /**
     * @brief Initialize throttle encoder
     */
    void begin();

    /**
     * @brief Update throttle state (call in main loop)
     */
    void update();

    /**
     * @brief Get current throttle value
     * @return Throttle percentage (0-100%)
     */
    int get_value() const;

    /**
     * @brief Get raw encoder position (for calibration)
     */
    long get_raw_position() const;

    /**
     * @brief Reset throttle to zero position
     */
    void reset();

    /**
     * @brief Start calibration mode
     */
    void start_calibration();

    /**
     * @brief Save calibration with min/max values
     */
    bool save_calibration(int32_t min_val, int32_t max_val);

    /**
     * @brief Check if in calibration mode
     */
    bool is_calibrating() const;
};

#endif // THROTTLE_MANAGER_H
