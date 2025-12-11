/**
 * @file brake_manager.cpp
 * @brief Implementação do Gerenciador de Controle de Freio (ESP32)
 *
 * Leitura de encoder simples e confiável usando interrupções baseadas em CLK
 *
 * @author F1 RC Car Project
 * @date 2025-10-13
 */

#include "brake_manager.h"

// Inicializa ponteiro de instância estática
BrakeManager* BrakeManager::instance = nullptr;

BrakeManager::BrakeManager()
    : encoder_position(0),
      last_clk(HIGH),
      current_value(0),
      calibration(EEPROM_BRAKE_ADDR, false) {  // false = unipolar (0-100%)
    instance = this;
}

void BrakeManager::begin() {
    // Inicializa calibração
    calibration.begin();

    // Configura pinos do encoder como entradas com resistores pull-up
    pinMode(PIN_ENCODER_CLK, INPUT_PULLUP);
    pinMode(PIN_ENCODER_DT, INPUT_PULLUP);

    // Lê estado inicial do CLK
    last_clk = digitalRead(PIN_ENCODER_CLK);

    // Anexa interrupção apenas ao pino CLK
    attachInterrupt(digitalPinToInterrupt(PIN_ENCODER_CLK), encoder_isr, CHANGE);

    // Reseta posição
    encoder_position = 0;
    current_value = 0;

    Serial.println("[Brake] Initialized - GPIO27,14");
}

void IRAM_ATTR BrakeManager::encoder_isr() {
    if (instance != nullptr) {
        // Lê estados atuais dos pinos
        int clk_value = digitalRead(instance->PIN_ENCODER_CLK);
        int dt_value = digitalRead(instance->PIN_ENCODER_DT);

        // Detecta direção de rotação baseada na borda CLK e estado DT
        if (clk_value != instance->last_clk) {
            if (dt_value != clk_value) {
                // Rotação horária
                instance->encoder_position++;
            } else {
                // Rotação anti-horária
                instance->encoder_position--;
            }

            // SEM restrição em modo de calibração - deixa encoder contar livremente

            // Atualiza último estado CLK
            instance->last_clk = clk_value;
        }
    }
}

void BrakeManager::update() {
    // Atualiza calibração se em modo de calibração
    if (calibration.is_in_calibration_mode()) {
        calibration.update_calibration(encoder_position);
    }

    // Converte posição do encoder para porcentagem usando calibração
    current_value = calibration.map_to_percent(encoder_position);

    // Garante que o valor está dentro da faixa válida
    current_value = constrain(current_value, 0, 100);
}

int BrakeManager::get_value() const {
    return current_value;
}

long BrakeManager::get_raw_position() const {
    return encoder_position;
}

void BrakeManager::reset() {
    encoder_position = 0;
    current_value = 0;
}

void BrakeManager::start_calibration() {
    calibration.start_calibration();
    Serial.println("[Brake] Calibration mode started");
}

bool BrakeManager::save_calibration(int32_t min_val, int32_t max_val) {
    return calibration.save_calibration(min_val, max_val, 0);
}

bool BrakeManager::is_calibrating() const {
    return calibration.is_in_calibration_mode();
}
