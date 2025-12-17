/**
 * @file gear_manager.cpp
 * @brief Implementação do Gerenciador de Troca de Marchas (ESP32)
 *
 * @author F1 RC Car Project
 * @date 2025-10-13
 */

#include "gear_manager.h"

GearManager::GearManager()
    : last_gear_up_state(HIGH), last_gear_up_time(0),
      last_gear_down_state(HIGH), last_gear_down_time(0),
      gear_up_pressed(false), gear_down_pressed(false) {
}

void GearManager::begin() {
    // Configura pinos dos botões como entradas com resistores pull-up
    // Botões são ativos LOW (pressionado = LOW, solto = HIGH)
    pinMode(PIN_GEAR_UP, INPUT_PULLUP);
    pinMode(PIN_GEAR_DOWN, INPUT_PULLUP);

    // Inicializa estados dos botões
    last_gear_up_state = digitalRead(PIN_GEAR_UP);
    last_gear_down_state = digitalRead(PIN_GEAR_DOWN);

    Serial.println("[Gear] Initialized - GPIO32,33");
}

bool GearManager::read_button(int pin, int& last_state, unsigned long& last_time) {
    int reading = digitalRead(pin);
    bool pressed = false;
    unsigned long current_time = millis();

    // Verifica se o estado do botão mudou
    if (reading != last_state) {
        // Verifica se o tempo de debounce passou desde a última mudança
        if ((current_time - last_time) > DEBOUNCE_DELAY) {
            // Detecta transição HIGH para LOW (pressão do botão)
            if (reading == LOW && last_state == HIGH) {
                pressed = true;
            }

            // Atualiza estado
            last_state = reading;
        }
        // Sempre atualiza tempo na mudança
        last_time = current_time;
    }

    return pressed;
}

void GearManager::update() {
    // Reseta flags de pressão
    gear_up_pressed = false;
    gear_down_pressed = false;

    // Lê botão marcha cima
    if (read_button(PIN_GEAR_UP, last_gear_up_state, last_gear_up_time)) {
        gear_up_pressed = true;
    }

    // Lê botão marcha baixo
    if (read_button(PIN_GEAR_DOWN, last_gear_down_state, last_gear_down_time)) {
        gear_down_pressed = true;
    }
}

bool GearManager::is_gear_up_pressed() {
    bool result = gear_up_pressed;
    gear_up_pressed = false;  // Detecção single-shot
    return result;
}

bool GearManager::is_gear_down_pressed() {
    bool result = gear_down_pressed;
    gear_down_pressed = false;  // Detecção single-shot
    return result;
}
