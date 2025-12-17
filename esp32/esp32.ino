/**
 * @file esp32.ino
 * @brief Controlador Principal ESP32 para Cockpit F1
 *
 * Este arquivo orquestra todos os componentes de hardware do cockpit para o
 * projeto de carro de controle remoto estilo F1. Gerencia encoders rotativos
 * para aceleração, freio e direção, além de botões de troca de marcha.
 *
 * Hardware: ESP32 DevKit V1 (ou compatível)
 *
 * Componentes:
 * - 3x Encoders Rotativos Incrementais LPD3806-600BM-G5-24C (600 PPR)
 *   - Acelerador: GPIO 25/26 (D25/D26) - Pinos CLK/DT INVERTIDOS (branco→CLK, verde→DT) para direção correta
 *   - Freio: GPIO 27/14 (D27/D14)
 *   - Direção: GPIO 12/13 (D12/D13) - Pinos CLK/DT INVERTIDOS (branco→CLK, verde→DT) para direção correta
 * - 2x Botões de Pressão (troca de marcha cima/baixo)
 *   - Marcha Cima: GPIO 32 (D32)
 *   - Marcha Baixo: GPIO 33 (D33)
 * - Driver Motor Ponte H BTS7960 (Force Feedback)
 *   - RPWM: GPIO 16 (D16) - PWM direita (sentido horário)
 *   - LPWM: GPIO 17 (D17) - PWM esquerda (sentido anti-horário)
 *   - R_EN: GPIO 18 (D18) - Habilitação direita
 *   - L_EN: GPIO 19 (D19) - Habilitação esquerda
 * - Comunicação serial USB para PC cliente (115200 baud)
 *
 * Recursos:
 * - Processamento dual-core:
 *   - Core 0 (Prioridade 2): Encoders + Motor Force Feedback (alta prioridade, tempo real)
 *   - Core 1 (Prioridade 1): Comunicação serial (prioridade normal)
 * - Rastreamento de encoder em tempo real com interrupções de hardware
 * - Transmissão serial USB (115200 baud)
 * - Velocidade de clock 240MHz (15x mais rápido que Arduino Mega)
 * - Encoders 600 PPR para controle analógico preciso (resolução 0.6°)
 * - Calibração dinâmica de encoder com persistência EEPROM
 * - Protocolo serial bidirecional para calibração e comandos force feedback
 * - Comunicação inter-core thread-safe com mutex locks
 *
 * Comandos Serial (Cliente → ESP32):
 * - CAL_START:THROTTLE/BRAKE/STEERING - Iniciar modo de calibração
 * - CAL_SAVE:THROTTLE:min:max - Salvar calibração acelerador/freio (unipolar)
 * - CAL_SAVE:STEERING:left:center:right - Salvar calibração direção (bipolar)
 * - FF_MOTOR:direction:intensity - Controlar motor force feedback (LEFT/RIGHT/NEUTRAL, 0-100%)
 *
 * Respostas Serial (ESP32 → Cliente):
 * - CAL_STARTED:component - Modo de calibração ativado
 * - CAL_THROTTLE/BRAKE/STEERING:raw_value - Posição bruta do encoder durante calibração
 * - CAL_COMPLETE:component - Calibração salva com sucesso
 * - CAL_ERROR:component - Falha ao salvar calibração
 *
 * @author F1 RC Car Project
 * @date 2025-10-13
 */

#include "throttle_manager.h"
#include "brake_manager.h"
#include "steering_manager.h"
#include "gear_manager.h"
#include "serial_sender_manager.h"
#include "ff_motor_manager.h"

// Gerenciadores de componentes
ThrottleManager throttle_manager;
BrakeManager brake_manager;
SteeringManager steering_manager;
GearManager gear_manager;
SerialSenderManager serial_sender;
FFMotorManager ff_motor;

// Controle de temporização
unsigned long last_update = 0;
const unsigned long UPDATE_INTERVAL = 10; // Taxa de atualização 100Hz

// Buffer de comandos serial
String serial_buffer = "";

// Estado do motor Force Feedback (compartilhado entre cores)
String ff_direction = "NEUTRAL";
volatile int ff_intensity = 0;
portMUX_TYPE ff_mutex = portMUX_INITIALIZER_UNLOCKED;

// Handles de tarefas FreeRTOS
TaskHandle_t EncoderTaskHandle;
TaskHandle_t SerialTaskHandle;

// Flag de inicialização completa
volatile bool system_fully_initialized = false;

/**
 * @brief Tarefa executando no Core 0 - Processamento de encoders + Motor Force Feedback
 * Tarefa de alta prioridade para rastreamento de encoder em tempo real e controle de motor
 */
void EncoderTask(void* parameter) {
    for (;;) {
        // Atualiza todos os componentes a 100Hz
        throttle_manager.update();
        brake_manager.update();
        steering_manager.update();
        gear_manager.update();

        // Se sistema inicializado, processa checagem ou force feedback
        if (system_fully_initialized) {
            // Se checagem em progresso, atualiza máquina de estados
            if (ff_motor.is_checking()) {
                ff_motor.update_startup_check();
            }
            // Se motor pronto, processa comandos force feedback
            else if (ff_motor.is_ready()) {
                // Atualiza motor force feedback (acesso thread-safe a variáveis compartilhadas)
                portENTER_CRITICAL(&ff_mutex);
                String current_direction = ff_direction;
                int current_intensity = ff_intensity;
                portEXIT_CRITICAL(&ff_mutex);

                // Aplica força do motor (alta prioridade, resposta instantânea)
                ff_motor.set_force(current_direction, current_intensity);
            }
        }

        // Mantém taxa de atualização 100Hz
        vTaskDelay(10 / portTICK_PERIOD_MS);
    }
}

/**
 * @brief Processa comandos serial recebidos do cliente
 */
void process_serial_command(String command) {
    command.trim();

    // Ignora comandos vazios
    if (command.length() == 0) {
        return;
    }

    // Ignora respostas que o ESP32 enviou (previne loop de eco)
    // Processa apenas comandos DO cliente (CAL_START, CAL_SAVE, FF_MOTOR)
    if (command.startsWith("CAL_STARTED:") ||
        command.startsWith("CAL_THROTTLE:") ||
        command.startsWith("CAL_BRAKE:") ||
        command.startsWith("CAL_STEERING:") ||
        command.startsWith("CAL_COMPLETE:") ||
        command.startsWith("CAL_ERROR:") ||
        command.startsWith("THROTTLE:") ||
        command.startsWith("BRAKE:") ||
        command.startsWith("STEERING:") ||
        command.startsWith("GEAR_") ||
        command.startsWith("===") ||
        command.startsWith("Core") ||
        command.startsWith("CPU") ||
        command.startsWith("ESP32") ||
        command.startsWith("Sending") ||
        command.startsWith("[")) {
        // Estas são respostas DO ESP32, não comandos PARA o ESP32
        // Exceção: FF_MOTOR é um comando PARA o ESP32, não uma resposta
        return;
    }

    if (command.startsWith("CAL_START:")) {
        String component = command.substring(10);

        if (component == "THROTTLE") {
            throttle_manager.start_calibration();
            Serial.println("CAL_STARTED:THROTTLE");
        } else if (component == "BRAKE") {
            brake_manager.start_calibration();
            Serial.println("CAL_STARTED:BRAKE");
        } else if (component == "STEERING") {
            steering_manager.start_calibration();
            Serial.println("CAL_STARTED:STEERING");
        }
    }
    else if (command.startsWith("CAL_SAVE:")) {
        // Formato: CAL_SAVE:THROTTLE:min:max ou CAL_SAVE:STEERING:left:center:right
        int first_colon = command.indexOf(':', 9);
        int second_colon = command.indexOf(':', first_colon + 1);
        int third_colon = command.indexOf(':', second_colon + 1);

        String component = command.substring(9, first_colon);

        if (component == "THROTTLE") {
            int32_t min_val = command.substring(first_colon + 1, second_colon).toInt();
            int32_t max_val = command.substring(second_colon + 1).toInt();

            if (throttle_manager.save_calibration(min_val, max_val)) {
                Serial.println("CAL_COMPLETE:THROTTLE");
            } else {
                Serial.println("CAL_ERROR:THROTTLE");
            }
        }
        else if (component == "BRAKE") {
            int32_t min_val = command.substring(first_colon + 1, second_colon).toInt();
            int32_t max_val = command.substring(second_colon + 1).toInt();

            if (brake_manager.save_calibration(min_val, max_val)) {
                Serial.println("CAL_COMPLETE:BRAKE");
            } else {
                Serial.println("CAL_ERROR:BRAKE");
            }
        }
        else if (component == "STEERING") {
            int32_t left_val = command.substring(first_colon + 1, second_colon).toInt();
            int32_t center_val = command.substring(second_colon + 1, third_colon).toInt();
            int32_t right_val = command.substring(third_colon + 1).toInt();

            Serial.printf("[DEBUG] Received calibration: Left=%d, Center=%d, Right=%d\n",
                         left_val, center_val, right_val);

            if (steering_manager.save_calibration(left_val, center_val, right_val)) {
                Serial.println("CAL_COMPLETE:STEERING");
            } else {
                Serial.println("CAL_ERROR:STEERING");
            }
        }
    }
    else if (command.startsWith("FF_MOTOR:")) {
        // Formato: FF_MOTOR:direction:intensity
        // Exemplos: FF_MOTOR:LEFT:45, FF_MOTOR:RIGHT:80, FF_MOTOR:NEUTRAL:0
        int first_colon = command.indexOf(':', 9);
        int second_colon = command.indexOf(':', first_colon + 1);

        if (first_colon > 0 && second_colon > 0) {
            String direction = command.substring(first_colon + 1, second_colon);
            int intensity = command.substring(second_colon + 1).toInt();

            // Atualiza variáveis compartilhadas para o Core 0 processar (thread-safe)
            portENTER_CRITICAL(&ff_mutex);
            ff_direction = direction;
            ff_intensity = intensity;
            portEXIT_CRITICAL(&ff_mutex);
        }
    }
}

/**
 * @brief Tarefa executando no Core 1 - Comunicação serial
 * Gerencia transmissão serial USB para PC cliente e recebe comandos de calibração
 */
void SerialTask(void* parameter) {
    for (;;) {
        unsigned long current_time = millis();

        // Verifica comandos serial recebidos (calibração)
        while (Serial.available() > 0) {
            char c = Serial.read();
            if (c == '\n') {
                process_serial_command(serial_buffer);
                serial_buffer = "";
            } else {
                serial_buffer += c;
            }
        }

        if (current_time - last_update >= UPDATE_INTERVAL) {
            last_update = current_time;

            // Verifica se algum componente está em modo de calibração
            bool throttle_cal = throttle_manager.is_calibrating();
            bool brake_cal = brake_manager.is_calibrating();
            bool steering_cal = steering_manager.is_calibrating();

            // Se em modo de calibração, envia valores brutos do encoder
            if (throttle_cal) {
                long raw_pos = throttle_manager.get_raw_position();
                Serial.print("CAL_THROTTLE:");
                Serial.println(raw_pos);
            }
            else if (brake_cal) {
                long raw_pos = brake_manager.get_raw_position();
                Serial.print("CAL_BRAKE:");
                Serial.println(raw_pos);
            }
            else if (steering_cal) {
                long raw_pos = steering_manager.get_raw_position();
                Serial.print("CAL_STEERING:");
                Serial.println(raw_pos);
            }
            else {
                // Operação normal - envia valores processados
                int throttle_value = throttle_manager.get_value();
                int brake_value = brake_manager.get_value();
                int steering_value = steering_manager.get_value();
                bool gear_up_pressed = gear_manager.is_gear_up_pressed();
                bool gear_down_pressed = gear_manager.is_gear_down_pressed();

                // Envia todos os dados via serial USB
                serial_sender.send_throttle(throttle_value);
                serial_sender.send_brake(brake_value);
                serial_sender.send_steering(steering_value);

                if (gear_up_pressed) {
                    serial_sender.send_gear_up();
                }

                if (gear_down_pressed) {
                    serial_sender.send_gear_down();
                }
            }
        }

        // Pequeno delay para prevenir reset do watchdog
        vTaskDelay(5 / portTICK_PERIOD_MS);
    }
}

void setup() {
    // Inicializa comunicação serial (115200 baud para dados de alta velocidade)
    Serial.begin(115200);
    delay(1000);

    Serial.println("\n=== F1 Cockpit ESP32 System ===");
    Serial.println("ESP32 Dual-Core Controller");
    Serial.println("CPU Freq: " + String(getCpuFrequencyMhz()) + " MHz");

    // Inicializa sender serial
    serial_sender.begin();

    // Inicializa todos os gerenciadores de componentes de hardware
    throttle_manager.begin();
    brake_manager.begin();
    steering_manager.begin();
    gear_manager.begin();
    ff_motor.begin();

    Serial.println("\n=== Dual-Core Task Creation ===");

    // Cria tarefa de encoder no Core 0 (alta prioridade para tempo real)
    xTaskCreatePinnedToCore(
        EncoderTask,          // Função da tarefa
        "EncoderTask",        // Nome da tarefa
        4096,                 // Tamanho da pilha (bytes)
        NULL,                 // Parâmetros
        2,                    // Prioridade (2 = alta)
        &EncoderTaskHandle,   // Handle da tarefa
        0                     // Core 0
    );
    Serial.println("Core 0: Encoder Task (Priority 2)");

    // Cria tarefa serial no Core 1 (core padrão do Arduino)
    xTaskCreatePinnedToCore(
        SerialTask,           // Função da tarefa
        "SerialTask",         // Nome da tarefa
        4096,                 // Tamanho da pilha (bytes)
        NULL,                 // Parâmetros
        1,                    // Prioridade (1 = normal)
        &SerialTaskHandle,    // Handle da tarefa
        1                     // Core 1
    );
    Serial.println("Core 1: Serial Task (Priority 1)");

    Serial.println("\n=== Starting Motor Check ===");

    // Pequeno delay para garantir que todas as tarefas estejam rodando
    delay(500);

    // Marca sistema como inicializado e inicia checagem do motor
    system_fully_initialized = true;
    ff_motor.start_startup_check();

    Serial.println("\n=== System Ready ===");
    Serial.println("Sending commands via USB Serial - 115200 baud");
}

void loop() {
    // Loop principal executa no Core 1
    // Todo o trabalho é feito nas tarefas FreeRTOS
    // Mantém isso mínimo para evitar interferir com as tarefas
    vTaskDelay(1000 / portTICK_PERIOD_MS);
}
