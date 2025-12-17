/**
 * @file throttle_manager.cpp
 * @brief Implementação do Gerenciador de Controle de Aceleração (ESP32)
 *
 * Leitura de encoder simples e confiável usando interrupções baseadas em CLK
 *
 * @author F1 RC Car Project
 * @date 2025-10-13
 */

#include "throttle_manager.h"

// Inicializa ponteiro de instância estática
ThrottleManager* ThrottleManager::instance = nullptr;

ThrottleManager::ThrottleManager()
    : encoder_position(0),
      last_clk(HIGH),
      current_value(0),
      calibration(EEPROM_THROTTLE_ADDR, false) {  // false = unipolar (0-100%)
    instance = this;
}

void ThrottleManager::begin() {
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

    Serial.println("[Throttle] Initialized - GPIO25,26");
}

void IRAM_ATTR ThrottleManager::encoder_isr() {
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
            // Restrição será feita pelo mapeamento de calibração no update()

            // Atualiza último estado CLK
            instance->last_clk = clk_value;
        }
    }
}

void ThrottleManager::update() {
    // Atualiza calibração se em modo de calibração
    if (calibration.is_in_calibration_mode()) {
        calibration.update_calibration(encoder_position);
    }

    // Converte posição do encoder para porcentagem usando calibração
    current_value = calibration.map_to_percent(encoder_position);

    // Garante que o valor está dentro da faixa válida
    current_value = constrain(current_value, 0, 100);
}

int ThrottleManager::get_value() const {
    return current_value;
}

long ThrottleManager::get_raw_position() const {
    return encoder_position;
}

void ThrottleManager::start_calibration() {
    calibration.start_calibration();
    Serial.println("[Throttle] Calibration mode started");
}

bool ThrottleManager::save_calibration(int32_t min_val, int32_t max_val) {
    return calibration.save_calibration(min_val, max_val, 0);
}

bool ThrottleManager::is_calibrating() const {
    return calibration.is_in_calibration_mode();
}
