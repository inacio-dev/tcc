/**
 * @file encoder_calibration.cpp
 * @brief Encoder Calibration Module Implementation
 *
 * @author F1 RC Car Project
 * @date 2025-10-14
 */

#include "encoder_calibration.h"

EncoderCalibration::EncoderCalibration(int eeprom_addr, bool bipolar)
    : eeprom_address(eeprom_addr),
      is_bipolar(bipolar),
      is_calibrating(false),
      cal_raw_min(0),
      cal_raw_max(0) {

    // Initialize calibration data
    cal_data.magic = 0;
    cal_data.min_value = 0;
    cal_data.max_value = 600;  // Default for 600 PPR encoder
    cal_data.center_value = 300;  // Default center
    cal_data.checksum = 0;
}

void EncoderCalibration::begin() {
    // Initialize EEPROM
    EEPROM.begin(EEPROM_SIZE);

    // Try to load calibration from EEPROM
    if (!load_calibration()) {
        Serial.println("[Calibration] No valid calibration found, using defaults");
        // Set default values
        if (is_bipolar) {
            reset_to_defaults(0, 600, 300);
        } else {
            reset_to_defaults(0, 600, 0);
        }
    } else {
        Serial.println("[Calibration] Loaded from EEPROM");
        Serial.printf("  Min: %d, Max: %d, Center: %d\n",
                      cal_data.min_value, cal_data.max_value, cal_data.center_value);
    }
}

uint16_t EncoderCalibration::calculate_checksum(const CalibrationData& data) {
    // Simple XOR checksum
    uint16_t checksum = data.magic;
    checksum ^= (uint16_t)(data.min_value & 0xFFFF);
    checksum ^= (uint16_t)((data.min_value >> 16) & 0xFFFF);
    checksum ^= (uint16_t)(data.max_value & 0xFFFF);
    checksum ^= (uint16_t)((data.max_value >> 16) & 0xFFFF);
    checksum ^= (uint16_t)(data.center_value & 0xFFFF);
    checksum ^= (uint16_t)((data.center_value >> 16) & 0xFFFF);
    return checksum;
}

bool EncoderCalibration::verify_checksum(const CalibrationData& data) {
    uint16_t calculated = calculate_checksum(data);
    return calculated == data.checksum;
}

void EncoderCalibration::start_calibration() {
    is_calibrating = true;
    cal_raw_min = INT32_MAX;
    cal_raw_max = INT32_MIN;
    Serial.println("[Calibration] Started calibration mode");
}

void EncoderCalibration::update_calibration(int32_t raw_value) {
    if (!is_calibrating) return;

    // Track min/max values
    if (raw_value < cal_raw_min) {
        cal_raw_min = raw_value;
    }
    if (raw_value > cal_raw_max) {
        cal_raw_max = raw_value;
    }
}

bool EncoderCalibration::save_calibration(int32_t min_val, int32_t max_val, int32_t center_val) {
    // Validate inputs
    if (min_val >= max_val) {
        Serial.println("[Calibration] ERROR: Invalid calibration (min >= max)");
        return false;
    }

    // Update calibration data
    cal_data.magic = EEPROM_MAGIC_NUMBER;
    cal_data.min_value = min_val;
    cal_data.max_value = max_val;
    cal_data.center_value = center_val;
    cal_data.checksum = calculate_checksum(cal_data);

    // Write to EEPROM
    EEPROM.put(eeprom_address, cal_data);
    EEPROM.commit();

    is_calibrating = false;

    Serial.println("[Calibration] Saved to EEPROM");
    Serial.printf("  Min: %d, Max: %d, Center: %d\n", min_val, max_val, center_val);

    return true;
}

bool EncoderCalibration::load_calibration() {
    // Read from EEPROM
    EEPROM.get(eeprom_address, cal_data);

    // Verify magic number and checksum
    if (cal_data.magic != EEPROM_MAGIC_NUMBER) {
        Serial.println("[Calibration] Invalid magic number");
        return false;
    }

    if (!verify_checksum(cal_data)) {
        Serial.println("[Calibration] Checksum mismatch");
        return false;
    }

    // Validate ranges
    if (cal_data.min_value >= cal_data.max_value) {
        Serial.println("[Calibration] Invalid range (min >= max)");
        return false;
    }

    return true;
}

void EncoderCalibration::reset_to_defaults(int32_t default_min, int32_t default_max, int32_t default_center) {
    cal_data.magic = EEPROM_MAGIC_NUMBER;
    cal_data.min_value = default_min;
    cal_data.max_value = default_max;
    cal_data.center_value = default_center;
    cal_data.checksum = calculate_checksum(cal_data);

    // Save to EEPROM
    EEPROM.put(eeprom_address, cal_data);
    EEPROM.commit();

    Serial.println("[Calibration] Reset to defaults");
    Serial.printf("  Min: %d, Max: %d, Center: %d\n", default_min, default_max, default_center);
}

int EncoderCalibration::map_to_percent(int32_t raw_value) {
    if (!is_valid()) {
        // No valid calibration, return 0
        return 0;
    }

    // Constrain raw value to calibrated range
    int32_t constrained = constrain(raw_value, cal_data.min_value, cal_data.max_value);

    if (is_bipolar) {
        // Bipolar mapping (-100 to +100% for steering)
        int32_t center = cal_data.center_value;

        if (constrained < center) {
            // Left side: min to center → -100% to 0%
            int32_t range = center - cal_data.min_value;
            if (range == 0) return 0;
            return map(constrained, cal_data.min_value, center, -100, 0);
        } else {
            // Right side: center to max → 0% to +100%
            int32_t range = cal_data.max_value - center;
            if (range == 0) return 0;
            return map(constrained, center, cal_data.max_value, 0, 100);
        }
    } else {
        // Unipolar mapping (0-100% for throttle/brake)
        return map(constrained, cal_data.min_value, cal_data.max_value, 0, 100);
    }
}
