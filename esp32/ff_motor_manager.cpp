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
      current_direction("NEUTRAL"),
      initialized(false),
      startup_check_done(false),
      startup_check_running(false),
      startup_phase(0),
      phase_start_time(0) {
}

void FFMotorManager::begin() {
    // Configura pinos de habilitação como saídas
    pinMode(PIN_R_EN, OUTPUT);
    pinMode(PIN_L_EN, OUTPUT);

    // Configura pinos PWM
    pinMode(PIN_RPWM, OUTPUT);
    pinMode(PIN_LPWM, OUTPUT);

    // IMPORTANTE: Mantém ponte H DESABILITADA durante inicialização
    digitalWrite(PIN_R_EN, LOW);
    digitalWrite(PIN_L_EN, LOW);

    // Configura canais PWM
    ledcSetup(PWM_CHANNEL_R, PWM_FREQ, PWM_RESOLUTION);
    ledcSetup(PWM_CHANNEL_L, PWM_FREQ, PWM_RESOLUTION);

    // Anexa canais PWM aos pinos
    ledcAttachPin(PIN_RPWM, PWM_CHANNEL_R);
    ledcAttachPin(PIN_LPWM, PWM_CHANNEL_L);

    // Garante PWM zerado
    ledcWrite(PWM_CHANNEL_R, 0);
    ledcWrite(PWM_CHANNEL_L, 0);

    // Motor NÃO está pronto ainda - aguarda startup check
    initialized = false;
    startup_check_done = false;

    Serial.println("[FF Motor] Initialized - GPIO16,17,18,19");
    Serial.println("[FF Motor] BTS7960 DISABLED - waiting for startup check");
}

void FFMotorManager::set_force(String direction, int intensity) {
    // Ignora comandos se motor não está pronto ou checagem em progresso
    if (!initialized || startup_check_running) {
        return;
    }

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

int FFMotorManager::intensity_to_pwm(int intensity) {
    // Mapeia 0-100% para ciclo de trabalho PWM 0-255
    return map(intensity, 0, 100, 0, 255);
}

void FFMotorManager::start_startup_check() {
    Serial.println("[FF Motor] Starting startup check sequence...");

    // Habilita ponte H para checagem
    digitalWrite(PIN_R_EN, HIGH);
    digitalWrite(PIN_L_EN, HIGH);

    // Inicia máquina de estados
    startup_check_running = true;
    startup_check_done = false;
    startup_phase = 0;  // Começa com LEFT
    phase_start_time = millis();

    // Fase 0: Gira para esquerda
    Serial.println("[FF Motor] Phase 0: Rotating LEFT");
    int pwm_value = intensity_to_pwm(STARTUP_INTENSITY);
    ledcWrite(PWM_CHANNEL_L, pwm_value);
    ledcWrite(PWM_CHANNEL_R, 0);
}

bool FFMotorManager::update_startup_check() {
    if (!startup_check_running) {
        return false;
    }

    unsigned long elapsed = millis() - phase_start_time;

    // Verifica se fase atual terminou
    if (elapsed >= PHASE_DURATION_MS) {
        startup_phase++;
        phase_start_time = millis();

        int pwm_value = intensity_to_pwm(STARTUP_INTENSITY);

        switch (startup_phase) {
            case 1:
                // Fase 1: Gira para direita
                Serial.println("[FF Motor] Phase 1: Rotating RIGHT");
                ledcWrite(PWM_CHANNEL_R, pwm_value);
                ledcWrite(PWM_CHANNEL_L, 0);
                break;

            case 2:
                // Fase 2: Centraliza (para motor)
                Serial.println("[FF Motor] Phase 2: Centering (stop)");
                ledcWrite(PWM_CHANNEL_R, 0);
                ledcWrite(PWM_CHANNEL_L, 0);
                break;

            case 3:
                // Fase 3: Checagem completa
                Serial.println("[FF Motor] Startup check COMPLETE - motor ready");
                ledcWrite(PWM_CHANNEL_R, 0);
                ledcWrite(PWM_CHANNEL_L, 0);
                startup_check_running = false;
                startup_check_done = true;
                initialized = true;
                return false;  // Checagem terminou
        }
    }

    return true;  // Checagem ainda em progresso
}

bool FFMotorManager::is_ready() const {
    return initialized && startup_check_done;
}

bool FFMotorManager::is_checking() const {
    return startup_check_running;
}
