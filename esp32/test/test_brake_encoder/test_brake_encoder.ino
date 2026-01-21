/**
 * @file test_brake_encoder.ino
 * @brief Teste independente do encoder de freio (LPD3806-600BM-G5-24C)
 *
 * Pinagem:
 * - CLK (A): GPIO 27 - Fio Verde
 * - DT (B):  GPIO 14 - Fio Branco
 * - VCC:     5V      - Fio Vermelho
 * - GND:     GND     - Fio Preto
 *
 * Upload: Arduino IDE ou PlatformIO
 * Monitor Serial: 115200 baud
 */

// Pinos do encoder
const int PIN_CLK = 27;
const int PIN_DT = 14;

// Variaveis do encoder
volatile long encoder_position = 0;
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
    Serial.println("  TESTE: ENCODER FREIO (BRAKE)");
    Serial.println("=====================================");
    Serial.println();
    Serial.println("Pinagem:");
    Serial.println("  CLK (A): GPIO 27 - Fio Verde");
    Serial.println("  DT (B):  GPIO 14 - Fio Branco");
    Serial.println("  VCC:     5V      - Fio Vermelho");
    Serial.println("  GND:     GND     - Fio Preto");
    Serial.println();
    Serial.println("Gire o encoder para testar...");
    Serial.println("=====================================");
    Serial.println();

    // Configura pinos
    pinMode(PIN_CLK, INPUT_PULLUP);
    pinMode(PIN_DT, INPUT_PULLUP);

    // Le estado inicial
    last_clk = digitalRead(PIN_CLK);

    // Anexa interrupcao
    attachInterrupt(digitalPinToInterrupt(PIN_CLK), encoder_isr, CHANGE);

    Serial.println("Encoder inicializado!");
    Serial.println();
}

void loop() {
    // So imprime quando houver mudanca
    if (encoder_position != last_printed_position) {
        last_printed_position = encoder_position;

        // Calcula porcentagem simulada (assume 0-600 = 0-100%)
        int percent = constrain(map(encoder_position, 0, 600, 0, 100), 0, 100);

        Serial.print("Posicao: ");
        Serial.print(encoder_position);
        Serial.print(" | Freio: ");
        Serial.print(percent);
        Serial.print("% | ");

        // Barra visual
        int bars = percent / 5;
        Serial.print("[");
        for (int i = 0; i < 20; i++) {
            Serial.print(i < bars ? "#" : "-");
        }
        Serial.println("]");
    }

    delay(10);
}
