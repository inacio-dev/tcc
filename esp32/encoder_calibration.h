/**
 * @file encoder_calibration.h
 * @brief Encoder Calibration Module for ESP32
 *
 * Provides calibration functionality for incremental rotary encoders.
 * Allows dynamic adjustment of encoder ranges without hardcoded pulse limits.
 *
 * Features:
 * - Stores min/max/center calibration values in EEPROM
 * - Maps raw encoder pulses to percentages (-100% to +100%)
 * - Supports both unipolar (0-100%) and bipolar (-100 to +100%) encoders
 * - Calibration mode for interactive setup
 *
 * @author F1 RC Car Project
 * @date 2025-10-14
 */

#ifndef ENCODER_CALIBRATION_H
#define ENCODER_CALIBRATION_H

#include <Arduino.h>
#include <EEPROM.h>

// EEPROM addresses for calibration data
#define EEPROM_SIZE 512
#define EEPROM_THROTTLE_ADDR 0
#define EEPROM_BRAKE_ADDR 16
#define EEPROM_STEERING_ADDR 32
#define EEPROM_MAGIC_NUMBER 0xCAFE  // Magic number to verify valid calibration data

/**
 * @brief Calibration data structure
 */
struct CalibrationData {
    uint16_t magic;      // Magic number for validation
    int32_t min_value;   // Minimum encoder position
    int32_t max_value;   // Maximum encoder position
    int32_t center_value;  // Center position (for bipolar encoders like steering)
    uint16_t checksum;   // Simple checksum for data integrity
};

/**
 * @brief Encoder calibration class
 */
class EncoderCalibration {
private:
    int eeprom_address;
    CalibrationData cal_data;
    bool is_bipolar;  // True for steering (-100 to +100), false for throttle/brake (0-100)
    bool is_calibrating;
    int32_t cal_raw_min;
    int32_t cal_raw_max;

    /**
     * @brief Calculate checksum for calibration data
     */
    uint16_t calculate_checksum(const CalibrationData& data);

    /**
     * @brief Verify checksum of calibration data
     */
    bool verify_checksum(const CalibrationData& data);

public:
    /**
     * @brief Constructor
     * @param eeprom_addr EEPROM address to store calibration
     * @param bipolar True for bipolar encoders (steering), false for unipolar (throttle/brake)
     */
    EncoderCalibration(int eeprom_addr, bool bipolar = false);

    /**
     * @brief Initialize calibration (load from EEPROM)
     */
    void begin();

    /**
     * @brief Start calibration mode
     */
    void start_calibration();

    /**
     * @brief Update calibration with current raw value
     * @param raw_value Current raw encoder position
     */
    void update_calibration(int32_t raw_value);

    /**
     * @brief Save calibration to EEPROM
     * @param min_val Minimum encoder position
     * @param max_val Maximum encoder position
     * @param center_val Center position (only for bipolar encoders)
     * @return True if saved successfully
     */
    bool save_calibration(int32_t min_val, int32_t max_val, int32_t center_val = 0);

    /**
     * @brief Load calibration from EEPROM
     * @return True if loaded successfully
     */
    bool load_calibration();

    /**
     * @brief Reset to default calibration values
     * @param default_min Default minimum value
     * @param default_max Default maximum value
     * @param default_center Default center value
     */
    void reset_to_defaults(int32_t default_min, int32_t default_max, int32_t default_center = 0);

    /**
     * @brief Map raw encoder value to percentage
     * @param raw_value Raw encoder position
     * @return Mapped value (0-100% or -100 to +100%)
     */
    int map_to_percent(int32_t raw_value);

    /**
     * @brief Get calibration mode status
     */
    bool is_in_calibration_mode() const { return is_calibrating; }

    /**
     * @brief Get current min calibration value
     */
    int32_t get_min() const { return cal_data.min_value; }

    /**
     * @brief Get current max calibration value
     */
    int32_t get_max() const { return cal_data.max_value; }

    /**
     * @brief Get current center calibration value
     */
    int32_t get_center() const { return cal_data.center_value; }

    /**
     * @brief Check if calibration data is valid
     */
    bool is_valid() const { return cal_data.magic == EEPROM_MAGIC_NUMBER; }
};

#endif // ENCODER_CALIBRATION_H
