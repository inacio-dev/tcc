/**
 * @file esp32.ino
 * @brief ESP32 Main Controller for F1 Cockpit
 *
 * This file orchestrates all cockpit hardware components for the F1-style
 * remote-controlled car project. It manages rotary encoders for throttle,
 * brake, and steering, plus gear shift buttons.
 *
 * Hardware: ESP32 DevKit V1 (or compatible)
 *
 * Components:
 * - 3x LPD3806-600BM-G5-24C Incremental Rotary Encoders (600 PPR)
 *   - Throttle: GPIO 25/26 (D25/D26)
 *   - Brake: GPIO 27/14 (D27/D14)
 *   - Steering: GPIO 12/13 (D12/D13)
 * - 2x Push Buttons (gear up/down)
 *   - Gear Up: GPIO 32 (D32)
 *   - Gear Down: GPIO 33 (D33)
 * - USB Serial communication to client PC (115200 baud)
 *
 * Features:
 * - Dual-core processing (Core 0: encoders, Core 1: serial transmission)
 * - Real-time encoder tracking with hardware interrupts
 * - USB Serial transmission (115200 baud)
 * - 240MHz clock speed (15x faster than Arduino Mega)
 * - 600 PPR encoders for precise analog control (0.6° resolution)
 * - Dynamic encoder calibration with EEPROM persistence
 * - Bidirectional serial protocol for calibration commands
 *
 * Serial Commands (Client → ESP32):
 * - CAL_START:THROTTLE/BRAKE/STEERING - Start calibration mode
 * - CAL_SAVE:THROTTLE:min:max - Save throttle/brake calibration (unipolar)
 * - CAL_SAVE:STEERING:left:center:right - Save steering calibration (bipolar)
 *
 * Serial Responses (ESP32 → Client):
 * - CAL_STARTED:component - Calibration mode activated
 * - CAL_THROTTLE/BRAKE/STEERING:raw_value - Raw encoder position during calibration
 * - CAL_COMPLETE:component - Calibration saved successfully
 * - CAL_ERROR:component - Calibration save failed
 *
 * @author F1 RC Car Project
 * @date 2025-10-13
 */

#include "throttle_manager.h"
#include "brake_manager.h"
#include "steering_manager.h"
#include "gear_manager.h"
#include "serial_sender_manager.h"

// Component managers
ThrottleManager throttle_manager;
BrakeManager brake_manager;
SteeringManager steering_manager;
GearManager gear_manager;
SerialSenderManager serial_sender;

// Timing control
unsigned long last_update = 0;
const unsigned long UPDATE_INTERVAL = 10; // 100Hz update rate

// Serial command buffer
String serial_buffer = "";

// FreeRTOS task handles
TaskHandle_t EncoderTaskHandle;
TaskHandle_t SerialTaskHandle;

/**
 * @brief Task running on Core 0 - Encoder processing
 * High-priority task for real-time encoder tracking
 */
void EncoderTask(void* parameter) {
    for (;;) {
        unsigned long current_time = millis();

        // Update all components at 100Hz
        throttle_manager.update();
        brake_manager.update();
        steering_manager.update();
        gear_manager.update();

        // Maintain 100Hz update rate
        vTaskDelay(10 / portTICK_PERIOD_MS);
    }
}

/**
 * @brief Process incoming serial commands from client
 */
void process_serial_command(String command) {
    command.trim();

    if (command.startsWith("CAL_START:")) {
        String component = command.substring(10);

        if (component == "THROTTLE") {
            throttle_manager.start_calibration();
            Serial.println("CAL_STARTED:THROTTLE");
        } else if (component == "BRAKE") {
            brake_manager.start_calibration();
            Serial.println("CAL_STARTED:BRAKE");
        } else if (component == "STEERING") {
            steering_manager.start_calibration();
            Serial.println("CAL_STARTED:STEERING");
        }
    }
    else if (command.startsWith("CAL_SAVE:")) {
        // Format: CAL_SAVE:THROTTLE:min:max or CAL_SAVE:STEERING:left:center:right
        int first_colon = command.indexOf(':', 9);
        int second_colon = command.indexOf(':', first_colon + 1);
        int third_colon = command.indexOf(':', second_colon + 1);

        String component = command.substring(9, first_colon);

        if (component == "THROTTLE") {
            int32_t min_val = command.substring(first_colon + 1, second_colon).toInt();
            int32_t max_val = command.substring(second_colon + 1).toInt();

            if (throttle_manager.save_calibration(min_val, max_val)) {
                Serial.println("CAL_COMPLETE:THROTTLE");
            } else {
                Serial.println("CAL_ERROR:THROTTLE");
            }
        }
        else if (component == "BRAKE") {
            int32_t min_val = command.substring(first_colon + 1, second_colon).toInt();
            int32_t max_val = command.substring(second_colon + 1).toInt();

            if (brake_manager.save_calibration(min_val, max_val)) {
                Serial.println("CAL_COMPLETE:BRAKE");
            } else {
                Serial.println("CAL_ERROR:BRAKE");
            }
        }
        else if (component == "STEERING") {
            int32_t left_val = command.substring(first_colon + 1, second_colon).toInt();
            int32_t center_val = command.substring(second_colon + 1, third_colon).toInt();
            int32_t right_val = command.substring(third_colon + 1).toInt();

            if (steering_manager.save_calibration(left_val, center_val, right_val)) {
                Serial.println("CAL_COMPLETE:STEERING");
            } else {
                Serial.println("CAL_ERROR:STEERING");
            }
        }
    }
}

/**
 * @brief Task running on Core 1 - Serial communication
 * Handles USB serial transmission to client PC and receives calibration commands
 */
void SerialTask(void* parameter) {
    for (;;) {
        unsigned long current_time = millis();

        // Check for incoming serial commands (calibration)
        while (Serial.available() > 0) {
            char c = Serial.read();
            if (c == '\n') {
                process_serial_command(serial_buffer);
                serial_buffer = "";
            } else {
                serial_buffer += c;
            }
        }

        if (current_time - last_update >= UPDATE_INTERVAL) {
            last_update = current_time;

            // Check if any component is in calibration mode
            bool throttle_cal = throttle_manager.is_calibrating();
            bool brake_cal = brake_manager.is_calibrating();
            bool steering_cal = steering_manager.is_calibrating();

            // If in calibration mode, send raw encoder values
            if (throttle_cal) {
                long raw_pos = throttle_manager.get_raw_position();
                Serial.print("CAL_THROTTLE:");
                Serial.println(raw_pos);
            }
            else if (brake_cal) {
                long raw_pos = brake_manager.get_raw_position();
                Serial.print("CAL_BRAKE:");
                Serial.println(raw_pos);
            }
            else if (steering_cal) {
                long raw_pos = steering_manager.get_raw_position();
                Serial.print("CAL_STEERING:");
                Serial.println(raw_pos);
            }
            else {
                // Normal operation - send processed values
                int throttle_value = throttle_manager.get_value();
                int brake_value = brake_manager.get_value();
                int steering_value = steering_manager.get_value();
                bool gear_up_pressed = gear_manager.is_gear_up_pressed();
                bool gear_down_pressed = gear_manager.is_gear_down_pressed();

                // Send all data via USB serial
                serial_sender.send_throttle(throttle_value);
                serial_sender.send_brake(brake_value);
                serial_sender.send_steering(steering_value);

                if (gear_up_pressed) {
                    serial_sender.send_gear_up();
                }

                if (gear_down_pressed) {
                    serial_sender.send_gear_down();
                }
            }
        }

        // Small delay to prevent watchdog reset
        vTaskDelay(5 / portTICK_PERIOD_MS);
    }
}

void setup() {
    // Initialize serial communication (115200 baud for high-speed data)
    Serial.begin(115200);
    delay(1000);

    Serial.println("\n=== F1 Cockpit ESP32 System ===");
    Serial.println("ESP32 Dual-Core Controller");
    Serial.println("CPU Freq: " + String(getCpuFrequencyMhz()) + " MHz");

    // Initialize serial sender
    serial_sender.begin();

    // Initialize all hardware component managers
    throttle_manager.begin();
    brake_manager.begin();
    steering_manager.begin();
    gear_manager.begin();

    Serial.println("\n=== Dual-Core Task Creation ===");

    // Create encoder task on Core 0 (high priority for real-time)
    xTaskCreatePinnedToCore(
        EncoderTask,          // Task function
        "EncoderTask",        // Task name
        4096,                 // Stack size (bytes)
        NULL,                 // Parameters
        2,                    // Priority (2 = high)
        &EncoderTaskHandle,   // Task handle
        0                     // Core 0
    );
    Serial.println("Core 0: Encoder Task (Priority 2)");

    // Create serial task on Core 1 (default Arduino core)
    xTaskCreatePinnedToCore(
        SerialTask,           // Task function
        "SerialTask",         // Task name
        4096,                 // Stack size (bytes)
        NULL,                 // Parameters
        1,                    // Priority (1 = normal)
        &SerialTaskHandle,    // Task handle
        1                     // Core 1
    );
    Serial.println("Core 1: Serial Task (Priority 1)");

    Serial.println("\n=== System Ready ===");
    Serial.println("Sending commands via USB Serial - 115200 baud");
}

void loop() {
    // Main loop runs on Core 1
    // All work is done in FreeRTOS tasks
    // Keep this minimal to avoid interfering with tasks
    vTaskDelay(1000 / portTICK_PERIOD_MS);
}
