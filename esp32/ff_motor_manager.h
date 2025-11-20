/**
 * @file ff_motor_manager.h
 * @brief Force Feedback Motor Manager (ESP32)
 *
 * Controls a DC motor via BTS7960 H-Bridge driver for steering force feedback.
 * Provides bidirectional control with PWM intensity (0-100%).
 *
 * Hardware: BTS7960 43A Dual H-Bridge Motor Driver
 *
 * Pinout (ESP32 → BTS7960):
 * - GPIO 16 (D16) → RPWM (Right PWM - clockwise rotation)
 * - GPIO 17 (D17) → LPWM (Left PWM - counter-clockwise rotation)
 * - GPIO 18 (D18) → R_EN (Right enable - HIGH to activate)
 * - GPIO 19 (D19) → L_EN (Left enable - HIGH to activate)
 * - GND → GND (common ground)
 *
 * BTS7960 Power:
 * - VCC (5V logic) → 5V from ESP32 or external power
 * - B+ / B- → Motor terminals
 * - Vcc motor → Motor power supply (6V-27V, depending on motor specs)
 *
 * @author F1 RC Car Project
 * @date 2025-10-14
 */

#ifndef FF_MOTOR_MANAGER_H
#define FF_MOTOR_MANAGER_H

#include <Arduino.h>

class FFMotorManager {
private:
    // BTS7960 Pin Configuration
    static const int PIN_RPWM = 16;  // GPIO16 - Right PWM (clockwise)
    static const int PIN_LPWM = 17;  // GPIO17 - Left PWM (counter-clockwise)
    static const int PIN_R_EN = 18;  // GPIO18 - Right enable
    static const int PIN_L_EN = 19;  // GPIO19 - Left enable

    // PWM Configuration
    static const int PWM_CHANNEL_R = 0;  // PWM channel for RPWM
    static const int PWM_CHANNEL_L = 1;  // PWM channel for LPWM
    static const int PWM_FREQ = 1000;    // 1kHz PWM frequency
    static const int PWM_RESOLUTION = 8; // 8-bit resolution (0-255)

    // Current motor state
    int current_intensity;
    String current_direction;

public:
    FFMotorManager();

    /**
     * @brief Initialize BTS7960 pins and PWM channels
     */
    void begin();

    /**
     * @brief Set motor force and direction
     * @param direction "LEFT", "RIGHT", or "NEUTRAL"
     * @param intensity 0-100 (percentage)
     */
    void set_force(String direction, int intensity);

    /**
     * @brief Stop motor immediately
     */
    void stop();

    /**
     * @brief Get current motor intensity
     * @return Current intensity (0-100%)
     */
    int get_intensity() const;

    /**
     * @brief Get current motor direction
     * @return Current direction ("LEFT", "RIGHT", "NEUTRAL")
     */
    String get_direction() const;

private:
    /**
     * @brief Convert 0-100% to PWM duty cycle (0-255)
     * @param intensity Percentage (0-100)
     * @return PWM value (0-255)
     */
    int intensity_to_pwm(int intensity);
};

#endif
