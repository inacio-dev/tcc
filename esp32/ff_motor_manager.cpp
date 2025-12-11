/**
 * @file ff_motor_manager.cpp
 * @brief Implementação do Gerenciador de Motor Force Feedback (ESP32)
 *
 * Controle de ponte H BTS7960 para motor force feedback de direção.
 * Suporta rotação bidirecional com controle de intensidade PWM.
 *
 * @author F1 RC Car Project
 * @date 2025-10-14
 */

#include "ff_motor_manager.h"

FFMotorManager::FFMotorManager()
    : current_intensity(0),
      current_direction("NEUTRAL") {
}

void FFMotorManager::begin() {
    // Configura pinos de habilitação como saídas
    pinMode(PIN_R_EN, OUTPUT);
    pinMode(PIN_L_EN, OUTPUT);

    // Configura pinos PWM
    pinMode(PIN_RPWM, OUTPUT);
    pinMode(PIN_LPWM, OUTPUT);

    // Configura canais PWM
    ledcSetup(PWM_CHANNEL_R, PWM_FREQ, PWM_RESOLUTION);
    ledcSetup(PWM_CHANNEL_L, PWM_FREQ, PWM_RESOLUTION);

    // Anexa canais PWM aos pinos
    ledcAttachPin(PIN_RPWM, PWM_CHANNEL_R);
    ledcAttachPin(PIN_LPWM, PWM_CHANNEL_L);

    // Habilita ambos os lados da ponte H (sempre habilitado para esta aplicação)
    digitalWrite(PIN_R_EN, HIGH);
    digitalWrite(PIN_L_EN, HIGH);

    // Inicia com motor parado
    stop();

    Serial.println("[FF Motor] Initialized - GPIO16,17,18,19");
    Serial.println("[FF Motor] BTS7960 enabled and ready");
}

void FFMotorManager::set_force(String direction, int intensity) {
    // Restringe intensidade à faixa válida
    intensity = constrain(intensity, 0, 100);

    // Atualiza estado atual
    current_intensity = intensity;
    current_direction = direction;

    // Converte intensidade para valor PWM (0-255)
    int pwm_value = intensity_to_pwm(intensity);

    if (direction == "LEFT") {
        // Rotação anti-horária (LPWM ativo, RPWM desligado)
        ledcWrite(PWM_CHANNEL_L, pwm_value);
        ledcWrite(PWM_CHANNEL_R, 0);
    }
    else if (direction == "RIGHT") {
        // Rotação horária (RPWM ativo, LPWM desligado)
        ledcWrite(PWM_CHANNEL_R, pwm_value);
        ledcWrite(PWM_CHANNEL_L, 0);
    }
    else {  // NEUTRAL
        // Para motor
        ledcWrite(PWM_CHANNEL_R, 0);
        ledcWrite(PWM_CHANNEL_L, 0);
    }
}

void FFMotorManager::stop() {
    // Define ambos os canais PWM para 0
    ledcWrite(PWM_CHANNEL_R, 0);
    ledcWrite(PWM_CHANNEL_L, 0);

    // Atualiza estado
    current_intensity = 0;
    current_direction = "NEUTRAL";
}

int FFMotorManager::get_intensity() const {
    return current_intensity;
}

String FFMotorManager::get_direction() const {
    return current_direction;
}

int FFMotorManager::intensity_to_pwm(int intensity) {
    // Mapeia 0-100% para ciclo de trabalho PWM 0-255
    return map(intensity, 0, 100, 0, 255);
}
