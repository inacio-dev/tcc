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
    : encoder_position(CENTER_POSITION),
      last_clk(HIGH),
      current_value(0) {
    instance = this;
}

void SteeringManager::begin() {
    // Configure encoder pins as inputs with pull-up resistors
    pinMode(PIN_ENCODER_CLK, INPUT_PULLUP);
    pinMode(PIN_ENCODER_DT, INPUT_PULLUP);

    // Read initial CLK state
    last_clk = digitalRead(PIN_ENCODER_CLK);

    // Attach interrupt only to CLK pin
    attachInterrupt(digitalPinToInterrupt(PIN_ENCODER_CLK), encoder_isr, CHANGE);

    // Reset to center position
    encoder_position = CENTER_POSITION;
    current_value = 0;

    Serial.println("[Steering] Initialized - GPIO12,13");
    Serial.print("[Steering] Center position: ");
    Serial.println(CENTER_POSITION);
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

            // Constrain position to valid range
            if (instance->encoder_position > MAX_POSITION) {
                instance->encoder_position = MAX_POSITION;
            } else if (instance->encoder_position < MIN_POSITION) {
                instance->encoder_position = MIN_POSITION;
            }

            // Update last CLK state
            instance->last_clk = clk_value;
        }
    }
}

void SteeringManager::update() {
    // Convert encoder position to percentage (-100 to +100%)
    // Center position (300) = 0%
    // Min position (0) = -100% (full left)
    // Max position (600) = +100% (full right)
    current_value = map(encoder_position, MIN_POSITION, MAX_POSITION, -100, 100);

    // Ensure value is within valid range
    current_value = constrain(current_value, -100, 100);
}

int SteeringManager::get_value() const {
    return current_value;
}

void SteeringManager::reset() {
    encoder_position = CENTER_POSITION;
    current_value = 0;
}
