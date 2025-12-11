/**
 * @file brake_manager.h
 * @brief Gerenciador de Controle de Freio para Cockpit F1 (ESP32)
 *
 * Gerencia um encoder rotativo incremental LPD3806-600BM-G5-24C para controle de freio.
 * Fornece entrada suave de freio de 0% a 100%.
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
 * - Encoder CLK (A): GPIO 27 (D27) - Fio Verde
 * - Encoder DT (B):  GPIO 14 (D14) - Fio Branco
 * - Encoder VCC: 5V (ou 3.3V com pull-ups) - Fio Vermelho
 * - Encoder GND: GND - Fio Preto
 *
 * Componentes de Hardware Necessários:
 * - Capacitor: 100nF (0.1µF) cerâmico X7R entre GPIO 27 e GND (filtro anti-bounce)
 * - Capacitor: 100nF (0.1µF) cerâmico X7R entre GPIO 14 e GND (filtro anti-bounce)
 * - Resistor: 10kΩ pull-up (OPCIONAL - ESP32 tem pull-ups internos habilitados no código)
 *
 * Observações:
 * - Capacitores devem ser posicionados o mais próximo possível dos pinos do ESP32
 * - Pull-ups internos são habilitados via INPUT_PULLUP, resistores externos não são necessários
 * - Use capacitores cerâmicos X7R (melhor estabilidade térmica que Y5V)
 * - LPD3806 fornece 600 pulsos por rotação completa para controle preciso de freio
 *
 * @author F1 RC Car Project
 * @date 2025-10-13
 */

#ifndef BRAKE_MANAGER_H
#define BRAKE_MANAGER_H

#include <Arduino.h>
#include "encoder_calibration.h"

class BrakeManager {
private:
    // Definições de pinos (GPIO ESP32)
    static const int PIN_ENCODER_CLK = 27;  // CLK (A)
    static const int PIN_ENCODER_DT = 14;   // DT (B)

    // Configuração do encoder
    static const int PULSES_PER_REV = 600;
    static const int MAX_POSITION = 600;  // Rotação completa = 100% freio
    static const int MIN_POSITION = 0;    // Rotação zero = 0% freio

    // Variáveis de estado
    volatile long encoder_position;  // Contagem bruta do encoder (alterado para long para faixa ilimitada)
    volatile int last_clk;          // Último estado CLK
    int current_value;              // 0-100%

    // Calibração
    EncoderCalibration calibration;

    // Instância estática para ISR
    static BrakeManager* instance;

    // Rotina de serviço de interrupção
    static void IRAM_ATTR encoder_isr();

public:
    BrakeManager();

    /**
     * @brief Inicializa encoder de freio
     */
    void begin();

    /**
     * @brief Atualiza estado do freio (chamar no loop principal)
     */
    void update();

    /**
     * @brief Obtém valor atual do freio
     * @return Porcentagem de freio (0-100%)
     */
    int get_value() const;

    /**
     * @brief Obtém posição bruta do encoder (para calibração)
     */
    long get_raw_position() const;

    /**
     * @brief Reseta freio para posição zero
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

#endif // BRAKE_MANAGER_H
