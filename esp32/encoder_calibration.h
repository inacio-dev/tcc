/**
 * @file encoder_calibration.h
 * @brief Módulo de Calibração de Encoder para ESP32
 *
 * Fornece funcionalidade de calibração para encoders rotativos incrementais.
 * Permite ajuste dinâmico de faixas de encoder sem limites de pulsos codificados.
 *
 * Recursos:
 * - Armazena valores de calibração min/max/centro na EEPROM
 * - Mapeia pulsos brutos do encoder para porcentagens (-100% a +100%)
 * - Suporta encoders tanto unipolares (0-100%) quanto bipolares (-100 a +100%)
 * - Modo de calibração para configuração interativa
 *
 * @author F1 RC Car Project
 * @date 2025-10-14
 */

#ifndef ENCODER_CALIBRATION_H
#define ENCODER_CALIBRATION_H

#include <Arduino.h>
#include <EEPROM.h>

// Endereços EEPROM para dados de calibração
#define EEPROM_SIZE 512
#define EEPROM_THROTTLE_ADDR 0
#define EEPROM_BRAKE_ADDR 16
#define EEPROM_STEERING_ADDR 32
#define EEPROM_MAGIC_NUMBER 0xCAFE  // Número mágico para verificar dados de calibração válidos

/**
 * @brief Estrutura de dados de calibração
 */
struct CalibrationData {
    uint16_t magic;      // Número mágico para validação
    int32_t min_value;   // Posição mínima do encoder
    int32_t max_value;   // Posição máxima do encoder
    int32_t center_value;  // Posição central (para encoders bipolares como direção)
    uint16_t checksum;   // Checksum simples para integridade dos dados
};

/**
 * @brief Classe de calibração de encoder
 */
class EncoderCalibration {
private:
    int eeprom_address;
    CalibrationData cal_data;
    bool is_bipolar;  // True para direção (-100 a +100), false para aceleração/freio (0-100)
    bool is_calibrating;
    int32_t cal_raw_min;
    int32_t cal_raw_max;

    /**
     * @brief Calcula checksum para dados de calibração
     */
    uint16_t calculate_checksum(const CalibrationData& data);

    /**
     * @brief Verifica checksum dos dados de calibração
     */
    bool verify_checksum(const CalibrationData& data);

public:
    /**
     * @brief Construtor
     * @param eeprom_addr Endereço EEPROM para armazenar calibração
     * @param bipolar True para encoders bipolares (direção), false para unipolares (aceleração/freio)
     */
    EncoderCalibration(int eeprom_addr, bool bipolar = false);

    /**
     * @brief Inicializa calibração (carrega da EEPROM)
     */
    void begin();

    /**
     * @brief Inicia modo de calibração
     */
    void start_calibration();

    /**
     * @brief Atualiza calibração com valor bruto atual
     * @param raw_value Posição bruta atual do encoder
     */
    void update_calibration(int32_t raw_value);

    /**
     * @brief Salva calibração na EEPROM
     * @param min_val Posição mínima do encoder
     * @param max_val Posição máxima do encoder
     * @param center_val Posição central (apenas para encoders bipolares)
     * @return True se salvo com sucesso
     */
    bool save_calibration(int32_t min_val, int32_t max_val, int32_t center_val = 0);

    /**
     * @brief Carrega calibração da EEPROM
     * @return True se carregado com sucesso
     */
    bool load_calibration();

    /**
     * @brief Reseta para valores padrão de calibração
     * @param default_min Valor mínimo padrão
     * @param default_max Valor máximo padrão
     * @param default_center Valor central padrão
     */
    void reset_to_defaults(int32_t default_min, int32_t default_max, int32_t default_center = 0);

    /**
     * @brief Mapeia valor bruto do encoder para porcentagem
     * @param raw_value Posição bruta do encoder
     * @return Valor mapeado (0-100% ou -100 a +100%)
     */
    int map_to_percent(int32_t raw_value);

    /**
     * @brief Obtém status do modo de calibração
     */
    bool is_in_calibration_mode() const { return is_calibrating; }

    /**
     * @brief Obtém valor mínimo atual de calibração
     */
    int32_t get_min() const { return cal_data.min_value; }

    /**
     * @brief Obtém valor máximo atual de calibração
     */
    int32_t get_max() const { return cal_data.max_value; }

    /**
     * @brief Obtém valor central atual de calibração
     */
    int32_t get_center() const { return cal_data.center_value; }

    /**
     * @brief Verifica se dados de calibração são válidos
     */
    bool is_valid() const { return cal_data.magic == EEPROM_MAGIC_NUMBER; }
};

#endif // ENCODER_CALIBRATION_H
