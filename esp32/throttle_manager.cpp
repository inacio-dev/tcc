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
      current_value(0) {
    instance = this;
}

void ThrottleManager::begin() {
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

void ThrottleManager::update() {
    // Convert encoder position to percentage (0-100%)
    current_value = map(encoder_position, MIN_POSITION, MAX_POSITION, 0, 100);

    // Ensure value is within valid range
    current_value = constrain(current_value, 0, 100);
}

int ThrottleManager::get_value() const {
    return current_value;
}

void ThrottleManager::reset() {
    encoder_position = 0;
    current_value = 0;
}
