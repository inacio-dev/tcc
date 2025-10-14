/**
 * @file steering_manager.cpp
 * @brief Steering Control Manager Implementation (ESP32)
 *
 * Simple and reliable encoder reading using CLK-based interrupts
 *
 * @author F1 RC Car Project
 * @date 2025-10-13
 */

#include "steering_manager.h"

// Initialize static instance pointer
SteeringManager* SteeringManager::instance = nullptr;

SteeringManager::SteeringManager()
    : encoder_position(0),  // Start at 0, not CENTER_POSITION
      last_clk(HIGH),
      current_value(0),
      calibration(EEPROM_STEERING_ADDR, true) {  // true = bipolar (-100% to +100%)
    instance = this;
}

void SteeringManager::begin() {
    // Initialize calibration
    calibration.begin();

    // Configure encoder pins as inputs with pull-up resistors
    pinMode(PIN_ENCODER_CLK, INPUT_PULLUP);
    pinMode(PIN_ENCODER_DT, INPUT_PULLUP);

    // Read initial CLK state
    last_clk = digitalRead(PIN_ENCODER_CLK);

    // Attach interrupt only to CLK pin
    attachInterrupt(digitalPinToInterrupt(PIN_ENCODER_CLK), encoder_isr, CHANGE);

    // Start at position 0 (calibration will define center)
    encoder_position = 0;
    current_value = 0;

    Serial.println("[Steering] Initialized - GPIO12,13");
    Serial.print("[Steering] Starting position: ");
    Serial.println(encoder_position);
}

void IRAM_ATTR SteeringManager::encoder_isr() {
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

            // Update last CLK state
            instance->last_clk = clk_value;
        }
    }
}

void SteeringManager::update() {
    // Update calibration if in calibration mode
    if (calibration.is_in_calibration_mode()) {
        calibration.update_calibration(encoder_position);
    }

    // Convert encoder position to percentage using calibration (bipolar: -100% to +100%)
    current_value = calibration.map_to_percent(encoder_position);

    // Ensure value is within valid range
    current_value = constrain(current_value, -100, 100);
}

int SteeringManager::get_value() const {
    return current_value;
}

long SteeringManager::get_raw_position() const {
    return encoder_position;
}

void SteeringManager::reset() {
    encoder_position = 0;  // Reset to 0, calibration defines center
    current_value = 0;
}

void SteeringManager::start_calibration() {
    calibration.start_calibration();
    Serial.println("[Steering] Calibration mode started");
}

bool SteeringManager::save_calibration(int32_t left_val, int32_t center_val, int32_t right_val) {
    // encoder_calibration expects: (min, max, center)
    // We have: (left, center, right)
    // So pass: (left as min, right as max, center as center)
    return calibration.save_calibration(left_val, right_val, center_val);
}

bool SteeringManager::is_calibrating() const {
    return calibration.is_in_calibration_mode();
}
