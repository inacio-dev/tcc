/**
 * @file throttle_manager.h
 * @brief Gerenciador de Controle de Aceleração para Cockpit F1 (ESP32)
 *
 * Gerencia um encoder rotativo incremental LPD3806-600BM-G5-24C para controle de aceleração.
 * Fornece entrada suave de aceleração de 0% a 100%.
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
 * - Encoder CLK (A): GPIO 25 (D25) - Fio Branco (INVERTIDO - era Verde)
 * - Encoder DT (B):  GPIO 26 (D26) - Fio Verde (INVERTIDO - era Branco)
 * - Encoder VCC: 5V (ou 3.3V com pull-ups) - Fio Vermelho
 * - Encoder GND: GND - Fio Preto
 *
 * Nota: Pinos CLK/DT estão INVERTIDOS comparados ao freio/direção para direção crescente correta
 *
 * Componentes de Hardware Necessários:
 * - Capacitor: 100nF (0.1µF) cerâmico X7R entre GPIO 25 e GND (filtro anti-bounce)
 * - Capacitor: 100nF (0.1µF) cerâmico X7R entre GPIO 26 e GND (filtro anti-bounce)
 * - Resistor: 10kΩ pull-up (OPCIONAL - ESP32 tem pull-ups internos habilitados no código)
 *
 * Observações:
 * - Capacitores devem ser posicionados o mais próximo possível dos pinos do ESP32
 * - Pull-ups internos são habilitados via INPUT_PULLUP, resistores externos não são necessários
 * - Use capacitores cerâmicos X7R (melhor estabilidade térmica que Y5V)
 * - LPD3806 fornece 600 pulsos por rotação completa para controle preciso de aceleração
 *
 * @author F1 RC Car Project
 * @date 2025-10-13
 */

#ifndef THROTTLE_MANAGER_H
#define THROTTLE_MANAGER_H

#include <Arduino.h>
#include "encoder_calibration.h"

class ThrottleManager {
private:
    // Definições de pinos (GPIO ESP32)
    static const int PIN_ENCODER_CLK = 25;  // CLK (A)
    static const int PIN_ENCODER_DT = 26;   // DT (B)

    // Configuração do encoder
    static const int PULSES_PER_REV = 600;
    static const int MAX_POSITION = 600;  // Rotação completa = 100% aceleração
    static const int MIN_POSITION = 0;    // Rotação zero = 0% aceleração

    // Variáveis de estado
    volatile long encoder_position;  // Contagem bruta do encoder (alterado para long para faixa ilimitada)
    volatile int last_clk;          // Último estado CLK
    int current_value;              // 0-100%

    // Calibração
    EncoderCalibration calibration;

    // Instância estática para ISR
    static ThrottleManager* instance;

    // Rotina de serviço de interrupção
    static void IRAM_ATTR encoder_isr();

public:
    ThrottleManager();

    /**
     * @brief Inicializa encoder de aceleração
     */
    void begin();

    /**
     * @brief Atualiza estado da aceleração (chamar no loop principal)
     */
    void update();

    /**
     * @brief Obtém valor atual da aceleração
     * @return Porcentagem de aceleração (0-100%)
     */
    int get_value() const;

    /**
     * @brief Obtém posição bruta do encoder (para calibração)
     */
    long get_raw_position() const;

    /**
     * @brief Reseta aceleração para posição zero
     */
    void reset();

    /**
     * @brief Inicia modo de calibração
     */
    void start_calibration();

    /**
     * @brief Salva calibração com valores min/max
     */
    bool save_calibration(int32_t min_val, int32_t max_val);

    /**
     * @brief Verifica se está em modo de calibração
     */
    bool is_calibrating() const;
};

#endif // THROTTLE_MANAGER_H
