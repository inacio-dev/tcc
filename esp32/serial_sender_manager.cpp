/**
 * @file serial_sender_manager.cpp
 * @brief Serial Communication Manager Implementation (ESP32)
 *
 * @author F1 RC Car Project
 * @date 2025-10-13
 */

#include "serial_sender_manager.h"

SerialSenderManager::SerialSenderManager()
    : last_throttle(-1), last_brake(-1), last_steering(0) {
}

void SerialSenderManager::begin() {
    // Serial is already initialized in main setup()
    // Just log initialization
    Serial.println("[Serial] USB Serial Sender initialized - 115200 baud");
}

void SerialSenderManager::send_command(const String& command) {
    if (Serial) {
        Serial.println(command);
    }
}

void SerialSenderManager::send_throttle(int value) {
    // Only send if value changed (reduce serial traffic)
    if (value != last_throttle) {
        String command = "THROTTLE:" + String(value);
        send_command(command);
        last_throttle = value;
    }
}

void SerialSenderManager::send_brake(int value) {
    // Only send if value changed
    if (value != last_brake) {
        String command = "BRAKE:" + String(value);
        send_command(command);
        last_brake = value;
    }
}

void SerialSenderManager::send_steering(int value) {
    // Only send if value changed
    if (value != last_steering) {
        String command = "STEERING:" + String(value);
        send_command(command);
        last_steering = value;
    }
}

void SerialSenderManager::send_gear_up() {
    send_command("GEAR_UP");
}

void SerialSenderManager::send_gear_down() {
    send_command("GEAR_DOWN");
}

bool SerialSenderManager::is_connected() const {
    return Serial;
}
