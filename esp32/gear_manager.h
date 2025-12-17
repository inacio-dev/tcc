/**
 * @file gear_manager.h
 * @brief Gerenciador de Troca de Marchas para Cockpit F1 (ESP32)
 *
 * Gerencia dois botões de pressão para troca de marchas (cima/baixo).
 * Implementa debouncing para detecção confiável de botões.
 *
 * Pinagem ESP32:
 * - Botão Marcha Cima:   GPIO 32 (D32)
 * - Botão Marcha Baixo: GPIO 33 (D33)
 * - GND do Botão:       GND
 *
 * Componentes de Hardware Necessários:
 * - Capacitor: 100nF (0.1µF) cerâmico X7R entre GPIO 32 e GND (filtro debounce)
 * - Capacitor: 100nF (0.1µF) cerâmico X7R entre GPIO 33 e GND (filtro debounce)
 * - Resistor: 10kΩ pull-up (OPCIONAL - ESP32 tem pull-ups internos habilitados no código)
 *
 * Observações:
 * - Capacitores devem ser posicionados o mais próximo possível dos pinos do ESP32
 * - Pull-ups internos são habilitados via INPUT_PULLUP, resistores externos não são necessários
 * - Use capacitores cerâmicos X7R (melhor estabilidade térmica que Y5V)
 * - Botões são ativos LOW (pressionado = LOW, solto = HIGH)
 * - Debounce em software: 50ms implementado no código para confiabilidade adicional
 *
 * @author F1 RC Car Project
 * @date 2025-10-13
 */

#ifndef GEAR_MANAGER_H
#define GEAR_MANAGER_H

#include <Arduino.h>

class GearManager {
private:
    // Definições de pinos (GPIO ESP32)
    static const int PIN_GEAR_UP = 32;    // Botão marcha cima
    static const int PIN_GEAR_DOWN = 33;  // Botão marcha baixo

    // Configuração de debounce
    static const unsigned long DEBOUNCE_DELAY = 50;  // 50ms debounce

    // Estados dos botões
    int last_gear_up_state;
    unsigned long last_gear_up_time;

    int last_gear_down_state;
    unsigned long last_gear_down_time;

    // Flags de detecção de pressão
    bool gear_up_pressed;
    bool gear_down_pressed;

    /**
     * @brief Lê botão com debouncing
     * @param pin Pino do botão a ler
     * @param last_state Estado anterior do botão
     * @param last_time Tempo da última mudança de estado
     * @return true se pressão do botão detectada
     */
    bool read_button(int pin, int& last_state, unsigned long& last_time);

public:
    GearManager();

    /**
     * @brief Inicializa botões de troca de marcha
     */
    void begin();

    /**
     * @brief Atualiza estados dos botões (chamar no loop principal)
     */
    void update();

    /**
     * @brief Verifica se botão marcha cima foi pressionado
     * @return true se pressionado (detecção single-shot)
     */
    bool is_gear_up_pressed();

    /**
     * @brief Verifica se botão marcha baixo foi pressionado
     * @return true se pressionado (detecção single-shot)
     */
    bool is_gear_down_pressed();
};

#endif // GEAR_MANAGER_H
