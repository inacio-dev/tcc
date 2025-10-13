/**
 * @file serial_sender_manager.h
 * @brief Serial Communication Manager for ESP32
 *
 * Manages serial communication from ESP32 to client PC.
 * Sends cockpit control commands (throttle, brake, steering, gear shifts)
 * via USB serial connection at 115200 baud.
 *
 * Protocol Format:
 * - THROTTLE:<value>   (0-100%)
 * - BRAKE:<value>      (0-100%)
 * - STEERING:<value>   (-100 to +100%)
 * - GEAR_UP
 * - GEAR_DOWN
 *
 * ESP32 Serial Pins:
 * - TX0 (GPIO 1): Transmit to USB
 * - RX0 (GPIO 3): Receive from USB
 * - USB Serial: Hardware Serial (Serial object)
 *
 * @author F1 RC Car Project
 * @date 2025-10-13
 */

#ifndef SERIAL_SENDER_MANAGER_H
#define SERIAL_SENDER_MANAGER_H

#include <Arduino.h>

class SerialSenderManager {
private:
    // Serial configuration
    static const long BAUD_RATE = 115200;

    // Last sent values for change detection
    int last_throttle;
    int last_brake;
    int last_steering;

    /**
     * @brief Send command string via serial
     * @param command Command string to send
     */
    void send_command(const String& command);

public:
    SerialSenderManager();

    /**
     * @brief Initialize serial communication
     */
    void begin();

    /**
     * @brief Send throttle value
     * @param value Throttle percentage (0-100%)
     */
    void send_throttle(int value);

    /**
     * @brief Send brake value
     * @param value Brake percentage (0-100%)
     */
    void send_brake(int value);

    /**
     * @brief Send steering value
     * @param value Steering percentage (-100 to +100%)
     */
    void send_steering(int value);

    /**
     * @brief Send gear up command
     */
    void send_gear_up();

    /**
     * @brief Send gear down command
     */
    void send_gear_down();

    /**
     * @brief Check if serial connection is available
     * @return true if connected
     */
    bool is_connected() const;
};

#endif // SERIAL_SENDER_MANAGER_H
