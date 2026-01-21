/**
 * @file test_steering_encoder.ino
 * @brief Teste independente do encoder de direcao (LPD3806-600BM-G5-24C)
 *
 * Pinagem:
 * - CLK (A): GPIO 12 - Fio Branco
 * - DT (B):  GPIO 13 - Fio Verde
 * - VCC:     5V      - Fio Vermelho
 * - GND:     GND     - Fio Preto
 *
 * Upload: Arduino IDE ou PlatformIO
 * Monitor Serial: 115200 baud
 */

// Pinos do encoder
const int PIN_CLK = 12;
const int PIN_DT = 13;

// Variaveis do encoder
volatile long encoder_position = 300;  // Inicia no centro (metade de 600)
volatile int last_clk = 0;
long last_printed_position = -999;

// ISR para leitura do encoder
void IRAM_ATTR encoder_isr() {
    int clk = digitalRead(PIN_CLK);
    int dt = digitalRead(PIN_DT);

    if (clk != last_clk) {
        if (dt != clk) {
            encoder_position++;
        } else {
            encoder_position--;
        }
        last_clk = clk;
    }
}

void setup() {
    Serial.begin(115200);
    delay(1000);

    Serial.println("=====================================");
    Serial.println("  TESTE: ENCODER DIRECAO (STEERING)");
    Serial.println("=====================================");
    Serial.println();
    Serial.println("Pinagem:");
    Serial.println("  CLK (A): GPIO 12 - Fio Branco");
    Serial.println("  DT (B):  GPIO 13 - Fio Verde");
    Serial.println("  VCC:     5V      - Fio Vermelho");
    Serial.println("  GND:     GND     - Fio Preto");
    Serial.println();
    Serial.println("Gire o encoder para testar...");
    Serial.println("Centro = 0% | Esquerda = -100% | Direita = +100%");
    Serial.println("=====================================");
    Serial.println();

    // Configura pinos
    pinMode(PIN_CLK, INPUT_PULLUP);
    pinMode(PIN_DT, INPUT_PULLUP);

    // Le estado inicial
    last_clk = digitalRead(PIN_CLK);

    // Anexa interrupcao
    attachInterrupt(digitalPinToInterrupt(PIN_CLK), encoder_isr, CHANGE);

    Serial.println("Encoder inicializado! (posicao central = 300)");
    Serial.println();
}

void loop() {
    // So imprime quando houver mudanca
    if (encoder_position != last_printed_position) {
        last_printed_position = encoder_position;

        // Calcula porcentagem (-100% a +100%)
        // 0 = -100% (esquerda), 300 = 0% (centro), 600 = +100% (direita)
        int percent = constrain(map(encoder_position, 0, 600, -100, 100), -100, 100);

        Serial.print("Posicao: ");
        Serial.print(encoder_position);
        Serial.print(" | Direcao: ");
        if (percent >= 0) Serial.print("+");
        Serial.print(percent);
        Serial.print("% | ");

        // Indicador visual de direcao
        if (percent < -50) {
            Serial.print("<<< ESQUERDA");
        } else if (percent < -10) {
            Serial.print("<< Esquerda");
        } else if (percent > 50) {
            Serial.print("DIREITA >>>");
        } else if (percent > 10) {
            Serial.print("Direita >>");
        } else {
            Serial.print("== CENTRO ==");
        }

        Serial.println();
    }

    delay(10);
}
