/**
 * @file ff_motor_manager.cpp
 * @brief Force Feedback Motor Manager Implementation (ESP32)
 *
 * BTS7960 H-Bridge control for steering force feedback motor.
 * Supports bidirectional rotation with PWM intensity control.
 *
 * @author F1 RC Car Project
 * @date 2025-10-14
 */

#include "ff_motor_manager.h"

FFMotorManager::FFMotorManager()
    : current_intensity(0),
      current_direction("NEUTRAL") {
}

void FFMotorManager::begin() {
    // Configure enable pins as outputs
    pinMode(PIN_R_EN, OUTPUT);
    pinMode(PIN_L_EN, OUTPUT);

    // Configure PWM pins
    pinMode(PIN_RPWM, OUTPUT);
    pinMode(PIN_LPWM, OUTPUT);

    // Setup PWM channels
    ledcSetup(PWM_CHANNEL_R, PWM_FREQ, PWM_RESOLUTION);
    ledcSetup(PWM_CHANNEL_L, PWM_FREQ, PWM_RESOLUTION);

    // Attach PWM channels to pins
    ledcAttachPin(PIN_RPWM, PWM_CHANNEL_R);
    ledcAttachPin(PIN_LPWM, PWM_CHANNEL_L);

    // Enable both H-bridge sides (always enabled for this application)
    digitalWrite(PIN_R_EN, HIGH);
    digitalWrite(PIN_L_EN, HIGH);

    // Start with motor stopped
    stop();

    Serial.println("[FF Motor] Initialized - GPIO16,17,18,19");
    Serial.println("[FF Motor] BTS7960 enabled and ready");
}

void FFMotorManager::set_force(String direction, int intensity) {
    // Constrain intensity to valid range
    intensity = constrain(intensity, 0, 100);

    // Update current state
    current_intensity = intensity;
    current_direction = direction;

    // Convert intensity to PWM value (0-255)
    int pwm_value = intensity_to_pwm(intensity);

    if (direction == "LEFT") {
        // Counter-clockwise rotation (LPWM active, RPWM off)
        ledcWrite(PWM_CHANNEL_L, pwm_value);
        ledcWrite(PWM_CHANNEL_R, 0);
    }
    else if (direction == "RIGHT") {
        // Clockwise rotation (RPWM active, LPWM off)
        ledcWrite(PWM_CHANNEL_R, pwm_value);
        ledcWrite(PWM_CHANNEL_L, 0);
    }
    else {  // NEUTRAL
        // Stop motor
        ledcWrite(PWM_CHANNEL_R, 0);
        ledcWrite(PWM_CHANNEL_L, 0);
    }
}

void FFMotorManager::stop() {
    // Set both PWM channels to 0
    ledcWrite(PWM_CHANNEL_R, 0);
    ledcWrite(PWM_CHANNEL_L, 0);

    // Update state
    current_intensity = 0;
    current_direction = "NEUTRAL";
}

int FFMotorManager::get_intensity() const {
    return current_intensity;
}

String FFMotorManager::get_direction() const {
    return current_direction;
}

int FFMotorManager::intensity_to_pwm(int intensity) {
    // Map 0-100% to 0-255 PWM duty cycle
    return map(intensity, 0, 100, 0, 255);
}
