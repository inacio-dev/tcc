/**
 * @file gear_manager.h
 * @brief Gear Shift Manager for F1 Cockpit (ESP32)
 *
 * Manages two push buttons for gear shifting (up/down).
 * Implements debouncing for reliable button detection.
 *
 * ESP32 Pinout:
 * - Gear Up Button:   GPIO 32 (D32)
 * - Gear Down Button: GPIO 33 (D33)
 * - Button GND:       GND
 *
 * Hardware Components Required:
 * - Capacitor: 100nF (0.1µF) ceramic X7R between GPIO 32 and GND (debounce filter)
 * - Capacitor: 100nF (0.1µF) ceramic X7R between GPIO 33 and GND (debounce filter)
 * - Resistor: 10kΩ pull-up (OPTIONAL - ESP32 has internal pull-ups enabled in code)
 *
 * Notes:
 * - Capacitors should be placed as close as possible to ESP32 pins
 * - Internal pull-ups are enabled via INPUT_PULLUP, external resistors not required
 * - Use ceramic X7R capacitors (better thermal stability than Y5V)
 * - Buttons are active LOW (pressed = LOW, released = HIGH)
 * - Software debounce: 50ms implemented in code for additional reliability
 *
 * @author F1 RC Car Project
 * @date 2025-10-13
 */

#ifndef GEAR_MANAGER_H
#define GEAR_MANAGER_H

#include <Arduino.h>

class GearManager {
private:
    // Pin definitions (ESP32 GPIO)
    static const int PIN_GEAR_UP = 32;    // Gear up button
    static const int PIN_GEAR_DOWN = 33;  // Gear down button

    // Debounce configuration
    static const unsigned long DEBOUNCE_DELAY = 50;  // 50ms debounce

    // Button states
    int gear_up_state;
    int last_gear_up_state;
    unsigned long last_gear_up_time;

    int gear_down_state;
    int last_gear_down_state;
    unsigned long last_gear_down_time;

    // Press detection flags
    bool gear_up_pressed;
    bool gear_down_pressed;

    /**
     * @brief Read button with debouncing
     * @param pin Button pin to read
     * @param last_state Previous button state
     * @param last_time Last state change time
     * @return true if button press detected
     */
    bool read_button(int pin, int& last_state, unsigned long& last_time);

public:
    GearManager();

    /**
     * @brief Initialize gear shift buttons
     */
    void begin();

    /**
     * @brief Update button states (call in main loop)
     */
    void update();

    /**
     * @brief Check if gear up button was pressed
     * @return true if pressed (single-shot detection)
     */
    bool is_gear_up_pressed();

    /**
     * @brief Check if gear down button was pressed
     * @return true if pressed (single-shot detection)
     */
    bool is_gear_down_pressed();

    /**
     * @brief Reset all button states
     */
    void reset();
};

#endif // GEAR_MANAGER_H
