/**
 * @file encoder_calibration.cpp
 * @brief Implementação do Módulo de Calibração de Encoder
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

    // Inicializa dados de calibração
    cal_data.magic = 0;
    cal_data.min_value = 0;
    cal_data.max_value = 600;  // Padrão para encoder 600 PPR
    cal_data.center_value = 300;  // Centro padrão
    cal_data.checksum = 0;
}

void EncoderCalibration::begin() {
    // Inicializa EEPROM
    EEPROM.begin(EEPROM_SIZE);

    // Tenta carregar calibração da EEPROM
    if (!load_calibration()) {
        Serial.println("[Calibration] No valid calibration found, using defaults");
        // Define valores padrão
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
    // Checksum XOR simples
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

    // Rastreia valores min/max
    if (raw_value < cal_raw_min) {
        cal_raw_min = raw_value;
    }
    if (raw_value > cal_raw_max) {
        cal_raw_max = raw_value;
    }
}

bool EncoderCalibration::save_calibration(int32_t min_val, int32_t max_val, int32_t center_val) {
    // Valida entradas
    if (min_val >= max_val) {
        Serial.println("[Calibration] ERROR: Invalid calibration (min >= max)");
        return false;
    }

    // Atualiza dados de calibração
    cal_data.magic = EEPROM_MAGIC_NUMBER;
    cal_data.min_value = min_val;
    cal_data.max_value = max_val;
    cal_data.center_value = center_val;
    cal_data.checksum = calculate_checksum(cal_data);

    // Escreve na EEPROM
    EEPROM.put(eeprom_address, cal_data);
    EEPROM.commit();

    is_calibrating = false;

    Serial.println("[Calibration] Saved to EEPROM");
    Serial.printf("  Min: %d, Max: %d, Center: %d\n", min_val, max_val, center_val);

    return true;
}

bool EncoderCalibration::load_calibration() {
    // Lê da EEPROM
    EEPROM.get(eeprom_address, cal_data);

    // Verifica número mágico e checksum
    if (cal_data.magic != EEPROM_MAGIC_NUMBER) {
        Serial.println("[Calibration] Invalid magic number");
        return false;
    }

    if (!verify_checksum(cal_data)) {
        Serial.println("[Calibration] Checksum mismatch");
        return false;
    }

    // Valida faixas
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

    // Salva na EEPROM
    EEPROM.put(eeprom_address, cal_data);
    EEPROM.commit();

    Serial.println("[Calibration] Reset to defaults");
    Serial.printf("  Min: %d, Max: %d, Center: %d\n", default_min, default_max, default_center);
}

int EncoderCalibration::map_to_percent(int32_t raw_value) {
    if (!is_valid()) {
        // Sem calibração válida, retorna 0
        return 0;
    }

    // Restringe valor bruto à faixa calibrada
    int32_t constrained = constrain(raw_value, cal_data.min_value, cal_data.max_value);

    if (is_bipolar) {
        // Mapeamento bipolar (-100 a +100% para direção)
        int32_t center = cal_data.center_value;

        if (constrained < center) {
            // Lado esquerdo: min para centro → -100% a 0%
            int32_t range = center - cal_data.min_value;
            if (range == 0) return 0;
            return map(constrained, cal_data.min_value, center, -100, 0);
        } else {
            // Lado direito: centro para max → 0% a +100%
            int32_t range = cal_data.max_value - center;
            if (range == 0) return 0;
            return map(constrained, center, cal_data.max_value, 0, 100);
        }
    } else {
        // Mapeamento unipolar (0-100% para aceleração/freio)
        return map(constrained, cal_data.min_value, cal_data.max_value, 0, 100);
    }
}
