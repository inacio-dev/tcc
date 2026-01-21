/**
 * @file test_gear_buttons.ino
 * @brief Teste independente dos botoes de troca de marcha
 *
 * Pinagem:
 * - Botao Marcha Cima:  GPIO 32 -> GND
 * - Botao Marcha Baixo: GPIO 33 -> GND
 *
 * Os botoes usam pull-up interno, ativos em LOW (pressionado = LOW)
 *
 * Upload: Arduino IDE ou PlatformIO
 * Monitor Serial: 115200 baud
 */

// Pinos dos botoes
const int PIN_GEAR_UP = 32;
const int PIN_GEAR_DOWN = 33;

// Debounce
const unsigned long DEBOUNCE_DELAY = 50;

// Estados
int last_gear_up_state = HIGH;
int last_gear_down_state = HIGH;
unsigned long last_gear_up_time = 0;
unsigned long last_gear_down_time = 0;

// Marcha atual simulada
int current_gear = 1;
const int MIN_GEAR = 1;
const int MAX_GEAR = 5;

// Contadores de pressao
int gear_up_count = 0;
int gear_down_count = 0;

bool read_button_with_debounce(int pin, int& last_state, unsigned long& last_time) {
    int reading = digitalRead(pin);
    bool pressed = false;

    if (reading != last_state) {
        last_time = millis();
    }

    if ((millis() - last_time) > DEBOUNCE_DELAY) {
        if (reading == LOW && last_state == HIGH) {
            pressed = true;
        }
    }

    last_state = reading;
    return pressed;
}

void print_gear_display() {
    Serial.print("Marcha: [");
    for (int i = 1; i <= MAX_GEAR; i++) {
        if (i == current_gear) {
            Serial.print("*");
            Serial.print(i);
            Serial.print("*");
        } else {
            Serial.print(" ");
            Serial.print(i);
            Serial.print(" ");
        }
        if (i < MAX_GEAR) Serial.print("|");
    }
    Serial.print("] | UP: ");
    Serial.print(gear_up_count);
    Serial.print("x | DOWN: ");
    Serial.print(gear_down_count);
    Serial.println("x");
}

void setup() {
    Serial.begin(115200);
    delay(1000);

    Serial.println("=====================================");
    Serial.println("  TESTE: BOTOES DE MARCHA (GEAR)");
    Serial.println("=====================================");
    Serial.println();
    Serial.println("Pinagem:");
    Serial.println("  Marcha Cima:  GPIO 32 -> GND");
    Serial.println("  Marcha Baixo: GPIO 33 -> GND");
    Serial.println();
    Serial.println("Pressione os botoes para testar...");
    Serial.println("=====================================");
    Serial.println();

    // Configura pinos com pull-up interno
    pinMode(PIN_GEAR_UP, INPUT_PULLUP);
    pinMode(PIN_GEAR_DOWN, INPUT_PULLUP);

    Serial.println("Botoes inicializados!");
    Serial.println();

    // Estado inicial
    Serial.print("Estado GPIO 32 (UP):   ");
    Serial.println(digitalRead(PIN_GEAR_UP) == HIGH ? "HIGH (solto)" : "LOW (pressionado)");
    Serial.print("Estado GPIO 33 (DOWN): ");
    Serial.println(digitalRead(PIN_GEAR_DOWN) == HIGH ? "HIGH (solto)" : "LOW (pressionado)");
    Serial.println();

    print_gear_display();
    Serial.println();
}

void loop() {
    bool gear_up_pressed = read_button_with_debounce(PIN_GEAR_UP, last_gear_up_state, last_gear_up_time);
    bool gear_down_pressed = read_button_with_debounce(PIN_GEAR_DOWN, last_gear_down_state, last_gear_down_time);

    if (gear_up_pressed) {
        gear_up_count++;
        if (current_gear < MAX_GEAR) {
            current_gear++;
            Serial.print(">>> GEAR UP! ");
        } else {
            Serial.print(">>> GEAR UP (ja na maxima)! ");
        }
        print_gear_display();
    }

    if (gear_down_pressed) {
        gear_down_count++;
        if (current_gear > MIN_GEAR) {
            current_gear--;
            Serial.print("<<< GEAR DOWN! ");
        } else {
            Serial.print("<<< GEAR DOWN (ja na minima)! ");
        }
        print_gear_display();
    }

    delay(10);
}
