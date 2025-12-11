/**
 * @file steering_manager.h
 * @brief Gerenciador de Controle de Direção para Cockpit F1 (ESP32)
 *
 * Gerencia um encoder rotativo incremental LPD3806-600BM-G5-24C para controle de direção.
 * Fornece entrada suave de direção de -100% (esquerda) a +100% (direita).
 *
 * Especificações do Encoder:
 * - Modelo: LPD3806-600BM-G5-24C
 * - Tipo: Encoder rotativo incremental
 * - Resolução: 600 pulsos por revolução (PPR)
 * - Saída: Quadratura fase AB (2 canais)
 * - Tensão de Operação: 5-24V DC
 * - Tipo de Saída: Coletor aberto NPN
 *
 * Pinagem ESP32:
 * - Encoder CLK (A): GPIO 12 (D12) - Fio Branco (INVERTIDO - era Verde)
 * - Encoder DT (B):  GPIO 13 (D13) - Fio Verde (INVERTIDO - era Branco)
 * - Encoder VCC: 5V (ou 3.3V com pull-ups) - Fio Vermelho
 * - Encoder GND: GND - Fio Preto
 *
 * Nota: Pinos CLK/DT estão INVERTIDOS para direção correta (esquerda=-100%, direita=+100%)
 *
 * Componentes de Hardware Necessários:
 * - Capacitor: 100nF (0.1µF) cerâmico X7R entre GPIO 12 e GND (filtro anti-bounce)
 * - Capacitor: 100nF (0.1µF) cerâmico X7R entre GPIO 13 e GND (filtro anti-bounce)
 * - Resistor: 10kΩ pull-up (OPCIONAL - ESP32 tem pull-ups internos habilitados no código)
 *
 * Observações:
 * - Capacitores devem ser posicionados o mais próximo possível dos pinos do ESP32
 * - Pull-ups internos são habilitados via INPUT_PULLUP, resistores externos não são necessários
 * - Use capacitores cerâmicos X7R (melhor estabilidade térmica que Y5V)
 * - Posição central está em 300 pulsos (metade do encoder 600 PPR)
 * - LPD3806 fornece 600 pulsos por rotação completa para controle preciso de direção
 *
 * @author F1 RC Car Project
 * @date 2025-10-13
 */

#ifndef STEERING_MANAGER_H
#define STEERING_MANAGER_H

#include <Arduino.h>
#include "encoder_calibration.h"

class SteeringManager {
private:
    // Definições de pinos (GPIO ESP32)
    static const int PIN_ENCODER_CLK = 12;  // CLK (A)
    static const int PIN_ENCODER_DT = 13;   // DT (B)

    // Configuração do encoder
    static const int PULSES_PER_REV = 600;
    static const int CENTER_POSITION = 300;  // Centro = 0% direção
    static const int MAX_POSITION = 600;     // Completo direita = +100%
    static const int MIN_POSITION = 0;       // Completo esquerda = -100%

    // Variáveis de estado
    volatile long encoder_position;  // Contagem bruta do encoder
    volatile int last_clk;           // Último estado CLK
    int current_value;               // -100 a +100%

    // Calibração (modo bipolar para direção)
    EncoderCalibration calibration;

    // Instância estática para ISR
    static SteeringManager* instance;

    // Rotina de serviço de interrupção
    static void IRAM_ATTR encoder_isr();

public:
    SteeringManager();

    /**
     * @brief Inicializa encoder de direção
     */
    void begin();

    /**
     * @brief Atualiza estado da direção (chamar no loop principal)
     */
    void update();

    /**
     * @brief Obtém valor atual da direção
     * @return Porcentagem de direção (-100 a +100%)
     */
    int get_value() const;

    /**
     * @brief Obtém posição bruta do encoder (para calibração)
     */
    long get_raw_position() const;

    /**
     * @brief Reseta direção para posição central
     */
    void reset();

    /**
     * @brief Inicia modo de calibração
     */
    void start_calibration();

    /**
     * @brief Salva calibração com valores esquerda/centro/direita
     */
    bool save_calibration(int32_t left_val, int32_t center_val, int32_t right_val);

    /**
     * @brief Verifica se está em modo de calibração
     */
    bool is_calibrating() const;
};

#endif // STEERING_MANAGER_H
