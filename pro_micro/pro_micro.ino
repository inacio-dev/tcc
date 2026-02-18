/*
 * pro_micro.ino - Unidade de Aquisição de Energia (Arduino Pro Micro)
 *
 * Lê tensão da bateria (divisor de tensão) e corrente de 2 subsistemas
 * (ACS758) via ADC interno (10 bits) e envia via USB Serial ao Raspberry Pi 4.
 *
 * ARQUITETURA:
 * ===========
 * Divisor de tensão (bateria) + ACS758 (2 unidades)
 *     ↓ (analógico)
 * Pro Micro (ADC 10-bit, filtragem, calibração)
 *     ↓ (USB Serial 115200)
 * Raspberry Pi 4 (power_monitor_manager.py)
 *
 * NOTA: A corrente do Raspberry Pi é medida pelo INA219 (I2C direto no RPi),
 * que oferece resolução muito superior ao ACS758 para correntes baixas (<3A).
 *
 * HARDWARE: Arduino Pro Micro (ATmega32U4)
 * =========================================
 * - MCU: ATmega32U4 @ 16MHz
 * - USB: Nativo (CDC, sem conversor FTDI)
 * - ADC: 10 bits (0-1023), referência AVCC (5V)
 * - EEPROM: 1024 bytes (para calibração persistente)
 * - Tensão: 5V (ratiométrico com ACS758)
 *
 * PINOUT ARDUINO PRO MICRO:
 * =========================
 *
 *   Pino    | Função          | Conexão
 *   --------|-----------------|---------------------------------------------
 *   A0      | ADC Canal 0     | Divisor de tensão da bateria 3S LiPo
 *   A1      | ADC Canal 1     | ACS758 50A #1 OUT  (Corrente Servos/UBEC)
 *   A2      | ADC Canal 2     | ACS758 100A #2 OUT (Corrente Motor DC 775)
 *   VCC     | Alimentação 5V  | VCC dos 2x ACS758
 *   GND     | Terra           | GND dos 2x ACS758 + GND divisor + GND comum
 *   USB     | Serial CDC      | USB do Raspberry Pi 4
 *
 *   Pinos não utilizados: D0-D10, A3, A6-A10, MISO, MOSI, SCK
 *
 * DIVISOR DE TENSÃO DA BATERIA (Canal A0):
 * ========================================
 *
 *   IMPORTANTE: NÃO usar o divisor antigo (2x 10kΩ) do ADS1115!
 *   O ADS1115 suportava ±6.144V, mas o Pro Micro tem ADC de 5V máximo.
 *   Com 2x 10kΩ, a saída seria 6.3V com bateria cheia → QUEIMA o ADC!
 *
 *   Divisor correto para ADC 5V:
 *
 *     Bateria (+) ─── R1 (20kΩ) ───┬─── Pro Micro A0
 *                                   │
 *                              R2 (10kΩ)
 *                                   │
 *                                  GND
 *
 *   Razão: R2 / (R1 + R2) = 10k / 30k = 1/3
 *   V_adc = V_bateria × (1/3)
 *   V_bateria = V_adc × 3
 *
 *   Tensões:
 *     Bateria cheia  (12.6V) → ADC = 4.2V  (seguro, < 5V)
 *     Bateria nominal (11.1V) → ADC = 3.7V
 *     Bateria mínima  (9.0V) → ADC = 3.0V
 *
 *   Corrente pelo divisor: 12.6V / 30kΩ = 0.42mA (desprezível)
 *
 *   Filtro RC recomendado (mesmo esquema dos ACS758):
 *     Junção R1/R2 ─── 1kΩ ───┬─── Pro Micro A0
 *                              │
 *                           100nF
 *                              │
 *                             GND
 *
 * CONEXÃO DOS SENSORES ACS758:
 * ============================
 *
 * ACS758 #1 (50A) - Corrente UBEC → Servos PCA9685:
 *   VCC  → VCC do Pro Micro (5V)
 *   GND  → GND do Pro Micro
 *   OUT  → Filtro RC → A1 do Pro Micro
 *
 * ACS758 #2 (100A) - Corrente Motor DC 775:
 *   VCC  → VCC do Pro Micro (5V)
 *   GND  → GND do Pro Micro
 *   OUT  → Filtro RC → A2 do Pro Micro
 *
 * FILTRO RC (hardware, para cada sensor ACS758):
 * ==============================================
 *
 *   ACS758 OUT ─── 1kΩ ───┬─── Pro Micro (Ax)
 *                         │
 *                      100nF
 *                         │
 *                        GND
 *
 *   Frequência de corte: fc = 1/(2π×1k×100n) ≈ 1.6 kHz
 *
 * PARTE DE POTÊNCIA (ACS758 em série, high-side):
 * ===============================================
 *
 *   ACS758 100A (Motor DC 775):
 *     Bateria (+) ─── IP+ ─── IP- ─── Ponte H BTS7960 (+) ─── Motor
 *
 *   ACS758 50A (Servos/UBEC):
 *     Bateria (+) ─── IP+ ─── IP- ─── UBEC IN (+) ─── Servos PCA9685
 *
 *   Os sensores ficam no fio POSITIVO (high-side), entre a bateria e cada carga.
 *   O GND comum do sistema permanece intacto (não é interrompido).
 *
 * PROTOCOLO SERIAL (USB, 115200 baud):
 * ====================================
 *
 * Pro Micro → RPi:
 *   "PWR:<v_bat>,<i_servos>,<i_motor>\n"   Tensão (V) e correntes (A)
 *   "STATUS:READY\n"                         Pronto após inicialização
 *   "STATUS:CALIBRATING\n"                   Durante calibração
 *
 * RPi → Pro Micro:
 *   "CAL\n"                                  Solicitar recalibração dos ACS758
 *
 * CALIBRAÇÃO:
 * ===========
 * - Offsets dos ACS758 salvos em EEPROM (persistem entre reboots)
 * - Na primeira execução: usa offset teórico (512 = VCC/2)
 * - Comando "CAL\n" via serial: recalibra e salva na EEPROM
 * - IMPORTANTE: para calibrar, desligar motor e servos
 * - O canal A0 (bateria) NÃO precisa de calibração (é tensão direta)
 */

#include <EEPROM.h>

// ============================================================
// CONFIGURAÇÃO DE PINOS
// ============================================================
const int PIN_BATTERY = A0;     // Divisor de tensão → Bateria 3S LiPo
const int PIN_ACS_SERVOS = A1;  // ACS758 50A  - Corrente Servos (UBEC)
const int PIN_ACS_MOTOR  = A2;  // ACS758 100A - Corrente Motor DC 775

// ============================================================
// CONFIGURAÇÃO DOS SENSORES
// ============================================================

// ADC
const float VCC = 5.0;                      // Tensão de alimentação (V)
const int   ADC_RESOLUTION   = 1024;        // 10 bits
const float ADC_STEP         = VCC / ADC_RESOLUTION;  // ~4.88 mV/LSB
const int   OFFSET_TEORICO   = ADC_RESOLUTION / 2;    // 512 (VCC/2)

// ACS758
const float SENSITIVITY_50A  = 0.040;       // 40 mV/A (ACS758LCB-050B)
const float SENSITIVITY_100A = 0.020;       // 20 mV/A (ACS758LCB-100B)

// Divisor de tensão da bateria
// R1 = 20kΩ (superior), R2 = 10kΩ (inferior)
// V_bateria = V_adc × BATTERY_DIVIDER_RATIO
const float BATTERY_DIVIDER_RATIO = 3.0;    // (R1 + R2) / R2 = 30k / 10k

// ============================================================
// CONFIGURAÇÃO DE AMOSTRAGEM
// ============================================================
const int  NUM_SAMPLES    = 50;    // Amostras por leitura (oversampling)
const int  SEND_INTERVAL  = 100;   // Intervalo de envio em ms (10 Hz)
const int  CAL_SAMPLES    = 200;   // Amostras para calibração
const int  CAL_DELAY_MS   = 5;     // Delay entre amostras de calibração

// ============================================================
// EEPROM - Armazenamento de Calibração
// ============================================================
// Estrutura na EEPROM:
//   Addr 0-1: Magic number (0xCAFE)
//   Addr 2-3: Offset canal A1 - Servos (int16_t)
//   Addr 4-5: Offset canal A2 - Motor  (int16_t)
//   Addr 6:   Checksum (XOR dos bytes 2-5)
const int    EEPROM_ADDR_MAGIC   = 0;
const int    EEPROM_ADDR_OFFSETS = 2;
const uint16_t EEPROM_MAGIC      = 0xCAFE;

// ============================================================
// VARIÁVEIS GLOBAIS
// ============================================================
int offset_servos = OFFSET_TEORICO;  // Offset canal A1 (ADC units)
int offset_motor  = OFFSET_TEORICO;  // Offset canal A2 (ADC units)

unsigned long last_send_time = 0;

// ============================================================
// SETUP
// ============================================================
void setup() {
    Serial.begin(115200);
    while (!Serial) {
        ; // Aguarda conexão USB (necessário para Pro Micro com USB nativo)
    }

    // Configura pinos analógicos como entrada
    pinMode(PIN_BATTERY, INPUT);
    pinMode(PIN_ACS_SERVOS, INPUT);
    pinMode(PIN_ACS_MOTOR, INPUT);

    // Referência ADC = AVCC (5V, ratiométrico)
    analogReference(DEFAULT);

    // Descarta primeiras leituras (estabilização do ADC)
    for (int i = 0; i < 10; i++) {
        analogRead(PIN_BATTERY);
        analogRead(PIN_ACS_SERVOS);
        analogRead(PIN_ACS_MOTOR);
    }

    // Carrega calibração da EEPROM (ou usa offset teórico)
    if (!loadCalibration()) {
        Serial.println("STATUS:NO_CAL");
    }

    Serial.println("STATUS:READY");
}

// ============================================================
// LOOP PRINCIPAL
// ============================================================
void loop() {
    // Verifica comandos do RPi
    checkSerialCommands();

    // Envia dados na taxa configurada
    unsigned long now = millis();
    if (now - last_send_time >= SEND_INTERVAL) {
        last_send_time = now;

        // Lê tensão da bateria (A0)
        float v_battery = readBatteryVoltage();

        // Lê correntes com oversampling (A1, A2)
        float i_servos = readCurrent(PIN_ACS_SERVOS, offset_servos, SENSITIVITY_50A);
        float i_motor  = readCurrent(PIN_ACS_MOTOR, offset_motor, SENSITIVITY_100A);

        // Envia no formato: PWR:v_bat,i_servos,i_motor
        Serial.print("PWR:");
        Serial.print(v_battery, 2);
        Serial.print(",");
        Serial.print(i_servos, 3);
        Serial.print(",");
        Serial.println(i_motor, 3);
    }
}

// ============================================================
// LEITURA DE TENSÃO DA BATERIA
// ============================================================
float readBatteryVoltage() {
    // Acumula múltiplas amostras para reduzir ruído
    long sum = 0;
    for (int i = 0; i < NUM_SAMPLES; i++) {
        sum += analogRead(PIN_BATTERY);
    }
    int avg = sum / NUM_SAMPLES;

    // Converte ADC → tensão no pino → tensão real da bateria
    float v_adc = avg * ADC_STEP;
    float v_battery = v_adc * BATTERY_DIVIDER_RATIO;

    return v_battery;
}

// ============================================================
// LEITURA DE CORRENTE COM OVERSAMPLING
// ============================================================
float readCurrent(int pin, int offset, float sensitivity) {
    // Acumula múltiplas amostras para reduzir ruído
    long sum = 0;
    for (int i = 0; i < NUM_SAMPLES; i++) {
        sum += analogRead(pin);
    }
    int avg = sum / NUM_SAMPLES;

    // Converte ADC → tensão → corrente
    // V = (avg - offset) * VCC / 1024
    // I = V / sensitivity
    float voltage_diff = (avg - offset) * ADC_STEP;
    float current = voltage_diff / sensitivity;

    return current;
}

// ============================================================
// CALIBRAÇÃO DE OFFSET (ZERO CURRENT) - APENAS ACS758
// ============================================================
void calibrate() {
    Serial.println("STATUS:CALIBRATING");

    long sum_servos = 0;
    long sum_motor = 0;

    for (int i = 0; i < CAL_SAMPLES; i++) {
        sum_servos += analogRead(PIN_ACS_SERVOS);
        sum_motor  += analogRead(PIN_ACS_MOTOR);
        delay(CAL_DELAY_MS);
    }

    offset_servos = sum_servos / CAL_SAMPLES;
    offset_motor  = sum_motor / CAL_SAMPLES;

    // Salva na EEPROM
    saveCalibration();

    Serial.print("CAL_DONE:");
    Serial.print(offset_servos);
    Serial.print(",");
    Serial.println(offset_motor);

    Serial.println("STATUS:READY");
}

// ============================================================
// EEPROM - SALVAR CALIBRAÇÃO
// ============================================================
void saveCalibration() {
    // Escreve magic number
    EEPROM.put(EEPROM_ADDR_MAGIC, EEPROM_MAGIC);

    // Escreve offsets (apenas 2 canais: servos e motor)
    int16_t offsets[2] = {
        (int16_t)offset_servos,
        (int16_t)offset_motor
    };
    EEPROM.put(EEPROM_ADDR_OFFSETS, offsets);

    // Calcula e escreve checksum
    uint8_t checksum = 0;
    uint8_t* bytes = (uint8_t*)offsets;
    for (int i = 0; i < 4; i++) {
        checksum ^= bytes[i];
    }
    EEPROM.put(EEPROM_ADDR_OFFSETS + 4, checksum);
}

// ============================================================
// EEPROM - CARREGAR CALIBRAÇÃO
// ============================================================
bool loadCalibration() {
    // Verifica magic number
    uint16_t magic;
    EEPROM.get(EEPROM_ADDR_MAGIC, magic);
    if (magic != EEPROM_MAGIC) {
        return false;
    }

    // Lê offsets
    int16_t offsets[2];
    EEPROM.get(EEPROM_ADDR_OFFSETS, offsets);

    // Verifica checksum
    uint8_t checksum = 0;
    uint8_t* bytes = (uint8_t*)offsets;
    for (int i = 0; i < 4; i++) {
        checksum ^= bytes[i];
    }
    uint8_t stored_checksum;
    EEPROM.get(EEPROM_ADDR_OFFSETS + 4, stored_checksum);

    if (checksum != stored_checksum) {
        return false;
    }

    // Valida range (offset deve estar próximo de 512)
    for (int i = 0; i < 2; i++) {
        if (offsets[i] < 400 || offsets[i] > 624) {
            return false;
        }
    }

    offset_servos = offsets[0];
    offset_motor  = offsets[1];

    return true;
}

// ============================================================
// COMANDOS SERIAL (RPi → Pro Micro)
// ============================================================
void checkSerialCommands() {
    if (Serial.available() > 0) {
        String cmd = Serial.readStringUntil('\n');
        cmd.trim();

        if (cmd == "CAL") {
            calibrate();
        }
    }
}
