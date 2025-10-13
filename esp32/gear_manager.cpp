/**
 * @file gear_manager.cpp
 * @brief Gear Shift Manager Implementation (ESP32)
 *
 * @author F1 RC Car Project
 * @date 2025-10-13
 */

#include "gear_manager.h"

GearManager::GearManager()
    : gear_up_state(HIGH), last_gear_up_state(HIGH), last_gear_up_time(0),
      gear_down_state(HIGH), last_gear_down_state(HIGH), last_gear_down_time(0),
      gear_up_pressed(false), gear_down_pressed(false) {
}

void GearManager::begin() {
    // Configure button pins as inputs with pull-up resistors
    // Buttons are active LOW (pressed = LOW, released = HIGH)
    pinMode(PIN_GEAR_UP, INPUT_PULLUP);
    pinMode(PIN_GEAR_DOWN, INPUT_PULLUP);

    // Initialize button states
    gear_up_state = digitalRead(PIN_GEAR_UP);
    gear_down_state = digitalRead(PIN_GEAR_DOWN);
    last_gear_up_state = gear_up_state;
    last_gear_down_state = gear_down_state;

    Serial.println("[Gear] Initialized - GPIO32,33");
}

bool GearManager::read_button(int pin, int& last_state, unsigned long& last_time) {
    int reading = digitalRead(pin);
    bool pressed = false;
    unsigned long current_time = millis();

    // Check if button state changed
    if (reading != last_state) {
        // Check if debounce time has passed since last change
        if ((current_time - last_time) > DEBOUNCE_DELAY) {
            // Detect HIGH to LOW transition (button press)
            if (reading == LOW && last_state == HIGH) {
                pressed = true;
            }

            // Update state
            last_state = reading;
        }
        // Always update time on change
        last_time = current_time;
    }

    return pressed;
}

void GearManager::update() {
    // Reset press flags
    gear_up_pressed = false;
    gear_down_pressed = false;

    // Read gear up button
    if (read_button(PIN_GEAR_UP, last_gear_up_state, last_gear_up_time)) {
        gear_up_pressed = true;
    }

    // Read gear down button
    if (read_button(PIN_GEAR_DOWN, last_gear_down_state, last_gear_down_time)) {
        gear_down_pressed = true;
    }
}

bool GearManager::is_gear_up_pressed() {
    bool result = gear_up_pressed;
    gear_up_pressed = false;  // Single-shot detection
    return result;
}

bool GearManager::is_gear_down_pressed() {
    bool result = gear_down_pressed;
    gear_down_pressed = false;  // Single-shot detection
    return result;
}

void GearManager::reset() {
    gear_up_pressed = false;
    gear_down_pressed = false;
    last_gear_up_state = HIGH;
    last_gear_down_state = HIGH;
}
