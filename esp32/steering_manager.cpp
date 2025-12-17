/**
 * @file steering_manager.cpp
 * @brief Implementação do Gerenciador de Controle de Direção (ESP32)
 *
 * Leitura de encoder simples e confiável usando interrupções baseadas em CLK
 *
 * @author F1 RC Car Project
 * @date 2025-10-13
 */

#include "steering_manager.h"

// Inicializa ponteiro de instância estática
SteeringManager* SteeringManager::instance = nullptr;

SteeringManager::SteeringManager()
    : encoder_position(0),  // Inicia em 0, não CENTER_POSITION
      last_clk(HIGH),
      current_value(0),
      calibration(EEPROM_STEERING_ADDR, true) {  // true = bipolar (-100% a +100%)
    instance = this;
}

void SteeringManager::begin() {
    // Inicializa calibração
    calibration.begin();

    // Configura pinos do encoder como entradas com resistores pull-up
    pinMode(PIN_ENCODER_CLK, INPUT_PULLUP);
    pinMode(PIN_ENCODER_DT, INPUT_PULLUP);

    // Lê estado inicial do CLK
    last_clk = digitalRead(PIN_ENCODER_CLK);

    // Anexa interrupção apenas ao pino CLK
    attachInterrupt(digitalPinToInterrupt(PIN_ENCODER_CLK), encoder_isr, CHANGE);

    // Inicia na posição 0 (calibração definirá o centro)
    encoder_position = 0;
    current_value = 0;

    Serial.println("[Steering] Initialized - GPIO12,13");
    Serial.print("[Steering] Starting position: ");
    Serial.println(encoder_position);
}

void IRAM_ATTR SteeringManager::encoder_isr() {
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

void SteeringManager::update() {
    // Atualiza calibração se em modo de calibração
    if (calibration.is_in_calibration_mode()) {
        calibration.update_calibration(encoder_position);
    }

    // Converte posição do encoder para porcentagem usando calibração (bipolar: -100% a +100%)
    current_value = calibration.map_to_percent(encoder_position);

    // Garante que o valor está dentro da faixa válida
    current_value = constrain(current_value, -100, 100);
}

int SteeringManager::get_value() const {
    return current_value;
}

long SteeringManager::get_raw_position() const {
    return encoder_position;
}

void SteeringManager::start_calibration() {
    calibration.start_calibration();
    Serial.println("[Steering] Calibration mode started");
}

bool SteeringManager::save_calibration(int32_t left_val, int32_t center_val, int32_t right_val) {
    // encoder_calibration espera: (min, max, center)
    // Temos: (left, center, right)
    // Então passamos: (left como min, right como max, center como center)
    return calibration.save_calibration(left_val, right_val, center_val);
}

bool SteeringManager::is_calibrating() const {
    return calibration.is_in_calibration_mode();
}
