/**
 * @file throttle_manager.cpp
 * @brief Throttle Control Manager Implementation (ESP32)
 *
 * Simple and reliable encoder reading using CLK-based interrupts
 *
 * @author F1 RC Car Project
 * @date 2025-10-13
 */

#include "throttle_manager.h"

// Initialize static instance pointer
ThrottleManager* ThrottleManager::instance = nullptr;

ThrottleManager::ThrottleManager()
    : encoder_position(0),
      last_clk(HIGH),
      current_value(0),
      calibration(EEPROM_THROTTLE_ADDR, false) {  // false = unipolar (0-100%)
    instance = this;
}

void ThrottleManager::begin() {
    // Initialize calibration
    calibration.begin();

    // Configure encoder pins as inputs with pull-up resistors
    pinMode(PIN_ENCODER_CLK, INPUT_PULLUP);
    pinMode(PIN_ENCODER_DT, INPUT_PULLUP);

    // Read initial CLK state
    last_clk = digitalRead(PIN_ENCODER_CLK);

    // Attach interrupt only to CLK pin
    attachInterrupt(digitalPinToInterrupt(PIN_ENCODER_CLK), encoder_isr, CHANGE);

    // Reset position
    encoder_position = 0;
    current_value = 0;

    Serial.println("[Throttle] Initialized - GPIO25,26");
}

void IRAM_ATTR ThrottleManager::encoder_isr() {
    if (instance != nullptr) {
        // Read current pin states
        int clk_value = digitalRead(instance->PIN_ENCODER_CLK);
        int dt_value = digitalRead(instance->PIN_ENCODER_DT);

        // Detect rotation direction based on CLK edge and DT state
        if (clk_value != instance->last_clk) {
            if (dt_value != clk_value) {
                // Clockwise rotation
                instance->encoder_position++;
            } else {
                // Counter-clockwise rotation
                instance->encoder_position--;
            }

            // NO constraining in calibration mode - let encoder count freely
            // Constraining will be done by calibration mapping in update()

            // Update last CLK state
            instance->last_clk = clk_value;
        }
    }
}

void ThrottleManager::update() {
    // Update calibration if in calibration mode
    if (calibration.is_in_calibration_mode()) {
        calibration.update_calibration(encoder_position);
    }

    // Convert encoder position to percentage using calibration
    current_value = calibration.map_to_percent(encoder_position);

    // Ensure value is within valid range
    current_value = constrain(current_value, 0, 100);
}

int ThrottleManager::get_value() const {
    return current_value;
}

long ThrottleManager::get_raw_position() const {
    return encoder_position;
}

void ThrottleManager::reset() {
    encoder_position = 0;
    current_value = 0;
}

void ThrottleManager::start_calibration() {
    calibration.start_calibration();
    Serial.println("[Throttle] Calibration mode started");
}

bool ThrottleManager::save_calibration(int32_t min_val, int32_t max_val) {
    return calibration.save_calibration(min_val, max_val, 0);
}

bool ThrottleManager::is_calibrating() const {
    return calibration.is_in_calibration_mode();
}
