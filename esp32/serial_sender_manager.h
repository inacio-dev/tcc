/**
 * @file serial_sender_manager.h
 * @brief Gerenciador de Comunicação Serial para ESP32
 *
 * Gerencia comunicação serial do ESP32 para PC cliente.
 * Envia comandos de controle do cockpit (aceleração, freio, direção, trocas de marcha)
 * via conexão serial USB a 115200 baud.
 *
 * Formato do Protocolo:
 * - THROTTLE:<value>   (0-100%)
 * - BRAKE:<value>      (0-100%)
 * - STEERING:<value>   (-100 a +100%)
 * - GEAR_UP
 * - GEAR_DOWN
 *
 * Pinos Serial ESP32:
 * - TX0 (GPIO 1): Transmitir para USB
 * - RX0 (GPIO 3): Receber de USB
 * - Serial USB: Hardware Serial (objeto Serial)
 *
 * @author F1 RC Car Project
 * @date 2025-10-13
 */

#ifndef SERIAL_SENDER_MANAGER_H
#define SERIAL_SENDER_MANAGER_H

#include <Arduino.h>

class SerialSenderManager {
private:
    // Configuração serial
    static const long BAUD_RATE = 115200;

    // Últimos valores enviados para detecção de mudança
    int last_throttle;
    int last_brake;
    int last_steering;

    /**
     * @brief Envia string de comando via serial
     * @param command String de comando a enviar
     */
    void send_command(const String& command);

public:
    SerialSenderManager();

    /**
     * @brief Inicializa comunicação serial
     */
    void begin();

    /**
     * @brief Envia valor de aceleração
     * @param value Porcentagem de aceleração (0-100%)
     */
    void send_throttle(int value);

    /**
     * @brief Envia valor de freio
     * @param value Porcentagem de freio (0-100%)
     */
    void send_brake(int value);

    /**
     * @brief Envia valor de direção
     * @param value Porcentagem de direção (-100 a +100%)
     */
    void send_steering(int value);

    /**
     * @brief Envia comando de marcha cima
     */
    void send_gear_up();

    /**
     * @brief Envia comando de marcha baixo
     */
    void send_gear_down();

    /**
     * @brief Verifica se conexão serial está disponível
     * @return true se conectado
     */
    bool is_connected() const;
};

#endif // SERIAL_SENDER_MANAGER_H
