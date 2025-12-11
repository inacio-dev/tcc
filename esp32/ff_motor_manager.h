/**
 * @file ff_motor_manager.h
 * @brief Gerenciador de Motor Force Feedback (ESP32)
 *
 * Controla um motor DC via driver ponte H BTS7960 para force feedback de direção.
 * Fornece controle bidirecional com intensidade PWM (0-100%).
 *
 * Hardware: Driver Motor Ponte H Dupla BTS7960 43A
 *
 * Pinagem (ESP32 → BTS7960):
 * - GPIO 16 (D16) → RPWM (PWM direita - rotação horária)
 * - GPIO 17 (D17) → LPWM (PWM esquerda - rotação anti-horária)
 * - GPIO 18 (D18) → R_EN (Habilitação direita - HIGH para ativar)
 * - GPIO 19 (D19) → L_EN (Habilitação esquerda - HIGH para ativar)
 * - GND → GND (terra comum)
 *
 * Alimentação BTS7960:
 * - VCC (lógica 5V) → 5V do ESP32 ou alimentação externa
 * - B+ / B- → Terminais do motor
 * - Vcc motor → Fonte de alimentação do motor (6V-27V, dependendo das especificações do motor)
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

public:
    FFMotorManager();

    /**
     * @brief Inicializa pinos BTS7960 e canais PWM
     */
    void begin();

    /**
     * @brief Define força e direção do motor
     * @param direction "LEFT", "RIGHT", ou "NEUTRAL"
     * @param intensity 0-100 (porcentagem)
     */
    void set_force(String direction, int intensity);

    /**
     * @brief Para motor imediatamente
     */
    void stop();

    /**
     * @brief Obtém intensidade atual do motor
     * @return Intensidade atual (0-100%)
     */
    int get_intensity() const;

    /**
     * @brief Obtém direção atual do motor
     * @return Direção atual ("LEFT", "RIGHT", "NEUTRAL")
     */
    String get_direction() const;

private:
    /**
     * @brief Converte 0-100% para ciclo de trabalho PWM (0-255)
     * @param intensity Porcentagem (0-100)
     * @return Valor PWM (0-255)
     */
    int intensity_to_pwm(int intensity);
};

#endif
