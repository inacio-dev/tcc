/**
 * @file ff_motor_manager.h
 * @brief Gerenciador de Motor Force Feedback (ESP32)
 *
 * Controla um motor DC via driver ponte H BTS7960 para force feedback de direção.
 * Fornece controle bidirecional com intensidade PWM (0-100%).
 *
 * Hardware: Driver Motor Ponte H Dupla BTS7960 43A
 *
 * PINOUT PONTE H BTS7960:
 * =======================
 * Pinos do módulo: VCC, GND, R_IS, L_IS, R_EN, L_EN, RPWM, LPWM, B-, B+, M+, M-
 *
 * Ponte H BTS7960 → ESP32 DevKit V1:
 *   - VCC   → 5V do ESP32 (alimentação lógica)
 *   - GND   → GND do ESP32 (terra comum)
 *   - R_IS  → Não conectado (current sense direita - opcional)
 *   - L_IS  → Não conectado (current sense esquerda - opcional)
 *   - R_EN  → GPIO 18 - Enable direita (manter HIGH)
 *   - L_EN  → GPIO 19 - Enable esquerda (manter HIGH)
 *   - RPWM  → GPIO 16 - PWM rotação horária (direita)
 *   - LPWM  → GPIO 17 - PWM rotação anti-horária (esquerda)
 *
 * Ponte H BTS7960 → Fonte de Alimentação Motor:
 *   - B+    → Positivo da fonte (6V-27V dependendo do motor)
 *   - B-    → GND da fonte
 *
 * Ponte H BTS7960 → Motor Force Feedback:
 *   - M+    → Terminal positivo do motor
 *   - M-    → Terminal negativo do motor
 *
 * @author F1 RC Car Project
 * @date 2025-10-14
 */

#ifndef FF_MOTOR_MANAGER_H
#define FF_MOTOR_MANAGER_H

#include <Arduino.h>

class FFMotorManager {
private:
    // Configuração de Pinos BTS7960
    static const int PIN_RPWM = 16;  // GPIO16 - PWM direita (horário)
    static const int PIN_LPWM = 17;  // GPIO17 - PWM esquerda (anti-horário)
    static const int PIN_R_EN = 18;  // GPIO18 - Habilitação direita
    static const int PIN_L_EN = 19;  // GPIO19 - Habilitação esquerda

    // Configuração PWM
    static const int PWM_CHANNEL_R = 0;  // Canal PWM para RPWM
    static const int PWM_CHANNEL_L = 1;  // Canal PWM para LPWM
    static const int PWM_FREQ = 1000;    // Frequência PWM 1kHz
    static const int PWM_RESOLUTION = 8; // Resolução 8-bit (0-255)

    // Estado atual do motor
    int current_intensity;
    String current_direction;

    // Estado de inicialização
    bool initialized;           // Motor pronto para operação
    bool startup_check_done;    // Checagem inicial concluída
    bool startup_check_running; // Checagem em progresso

    // Parâmetros de checagem inicial
    int startup_phase;          // Fase atual: 0=left, 1=right, 2=center, 3=done
    unsigned long phase_start_time;
    static const int PHASE_DURATION_MS = 500;  // 500ms por fase
    static const int STARTUP_INTENSITY = 20;   // 20% de força durante checagem

public:
    FFMotorManager();

    /**
     * @brief Inicializa pinos BTS7960 e canais PWM (motor permanece DESABILITADO)
     */
    void begin();

    /**
     * @brief Define força e direção do motor
     * @param direction "LEFT", "RIGHT", ou "NEUTRAL"
     * @param intensity 0-100 (porcentagem)
     */
    void set_force(String direction, int intensity);

    /**
     * @brief Inicia sequência de checagem inicial (esquerda → direita → centro)
     * Deve ser chamado APÓS toda inicialização do sistema estar completa
     */
    void start_startup_check();

    /**
     * @brief Atualiza máquina de estados da checagem inicial
     * @return True se checagem ainda em progresso, False se concluída
     */
    bool update_startup_check();

    /**
     * @brief Verifica se motor está pronto para operação normal
     * @return True se checagem inicial foi concluída
     */
    bool is_ready() const;

    /**
     * @brief Verifica se checagem inicial está em progresso
     * @return True se checagem está rodando
     */
    bool is_checking() const;

private:
    /**
     * @brief Converte 0-100% para ciclo de trabalho PWM (0-255)
     * @param intensity Porcentagem (0-100)
     * @return Valor PWM (0-255)
     */
    int intensity_to_pwm(int intensity);
};

#endif
