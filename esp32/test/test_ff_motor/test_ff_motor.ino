/**
 * @file test_ff_motor.ino
 * @brief Teste independente do motor de force feedback via BTS7960
 *
 * Testa o motor simulando os calculos de force feedback do projeto.
 * O motor gira em diferentes intensidades e direcoes.
 *
 * Pinagem BTS7960 -> ESP32:
 * - RPWM: GPIO 16 - PWM rotacao horaria (direita)
 * - LPWM: GPIO 17 - PWM rotacao anti-horaria (esquerda)
 * - R_EN: GPIO 18 - Enable direita (manter HIGH)
 * - L_EN: GPIO 19 - Enable esquerda (manter HIGH)
 * - VCC:  5V (logica)
 * - GND:  GND
 *
 * Alimentacao do motor (B+/B-): 6V-27V DC
 *
 * Upload: Arduino IDE ou PlatformIO
 * Monitor Serial: 115200 baud
 */

// Pinos BTS7960
const int PIN_RPWM = 16;
const int PIN_LPWM = 17;
const int PIN_R_EN = 18;
const int PIN_L_EN = 19;

// Configuracao PWM
const int PWM_CHANNEL_R = 0;
const int PWM_CHANNEL_L = 1;
const int PWM_FREQ = 1000;
const int PWM_RESOLUTION = 8;

// Variaveis de teste
int test_phase = 0;
unsigned long phase_start_time = 0;
const int PHASE_DURATION = 2000;  // 2 segundos por fase

// Converte 0-100% para 0-255 PWM
int intensity_to_pwm(int intensity) {
    intensity = constrain(intensity, 0, 100);
    return map(intensity, 0, 100, 0, 255);
}

// Define forca e direcao do motor
void set_force(const char* direction, int intensity) {
    int pwm_value = intensity_to_pwm(intensity);

    Serial.print("  Motor: ");
    Serial.print(direction);
    Serial.print(" @ ");
    Serial.print(intensity);
    Serial.print("% (PWM: ");
    Serial.print(pwm_value);
    Serial.println(")");

    if (strcmp(direction, "LEFT") == 0) {
        ledcWrite(PWM_CHANNEL_R, 0);
        ledcWrite(PWM_CHANNEL_L, pwm_value);
    } else if (strcmp(direction, "RIGHT") == 0) {
        ledcWrite(PWM_CHANNEL_R, pwm_value);
        ledcWrite(PWM_CHANNEL_L, 0);
    } else {  // NEUTRAL
        ledcWrite(PWM_CHANNEL_R, 0);
        ledcWrite(PWM_CHANNEL_L, 0);
    }
}

// Simula calculo de force feedback baseado no algoritmo real
void simulate_ff_calculation(float g_lateral, float gyro_z, int steering_percent) {
    Serial.println();
    Serial.println("--- Simulacao Force Feedback ---");
    Serial.print("  Entrada: G_lateral=");
    Serial.print(g_lateral, 2);
    Serial.print("g | Gyro_Z=");
    Serial.print(gyro_z, 1);
    Serial.print("deg/s | Steering=");
    Serial.print(steering_percent);
    Serial.println("%");

    // Componente 1: Forcas G laterais (0-100%)
    float lateral_component = min(abs(g_lateral) * 50.0f, 100.0f);

    // Componente 2: Rotacao yaw (0-50%)
    float yaw_component = min(abs(gyro_z) / 60.0f * 50.0f, 50.0f);

    // Componente 3: Mola de centragem (0-40%)
    float centering_component = abs(steering_percent) / 100.0f * 40.0f;

    // Combinado
    float base_ff = min(lateral_component + yaw_component + centering_component, 100.0f);

    Serial.print("  Componentes: Lateral=");
    Serial.print(lateral_component, 1);
    Serial.print("% | Yaw=");
    Serial.print(yaw_component, 1);
    Serial.print("% | Centering=");
    Serial.print(centering_component, 1);
    Serial.println("%");

    Serial.print("  Forca Total: ");
    Serial.print(base_ff, 1);
    Serial.println("%");

    // Determina direcao baseado no G lateral
    const char* direction;
    if (g_lateral > 0.1) {
        direction = "RIGHT";
    } else if (g_lateral < -0.1) {
        direction = "LEFT";
    } else {
        direction = "NEUTRAL";
    }

    set_force(direction, (int)base_ff);
}

void setup() {
    Serial.begin(115200);
    delay(1000);

    Serial.println("=====================================");
    Serial.println("  TESTE: MOTOR FORCE FEEDBACK");
    Serial.println("=====================================");
    Serial.println();
    Serial.println("Pinagem BTS7960 -> ESP32:");
    Serial.println("  RPWM: GPIO 16");
    Serial.println("  LPWM: GPIO 17");
    Serial.println("  R_EN: GPIO 18");
    Serial.println("  L_EN: GPIO 19");
    Serial.println();
    Serial.println("ATENCAO: Certifique-se que o motor");
    Serial.println("esta alimentado (6-27V em B+/B-)");
    Serial.println("=====================================");
    Serial.println();

    // Configura pinos enable
    pinMode(PIN_R_EN, OUTPUT);
    pinMode(PIN_L_EN, OUTPUT);
    digitalWrite(PIN_R_EN, HIGH);
    digitalWrite(PIN_L_EN, HIGH);

    // Configura canais PWM
    ledcSetup(PWM_CHANNEL_R, PWM_FREQ, PWM_RESOLUTION);
    ledcSetup(PWM_CHANNEL_L, PWM_FREQ, PWM_RESOLUTION);
    ledcAttachPin(PIN_RPWM, PWM_CHANNEL_R);
    ledcAttachPin(PIN_LPWM, PWM_CHANNEL_L);

    // Motor desligado inicialmente
    ledcWrite(PWM_CHANNEL_R, 0);
    ledcWrite(PWM_CHANNEL_L, 0);

    Serial.println("Motor inicializado!");
    Serial.println();
    Serial.println("Iniciando sequencia de testes em 3 segundos...");
    delay(3000);

    phase_start_time = millis();
}

void loop() {
    unsigned long elapsed = millis() - phase_start_time;

    if (elapsed >= PHASE_DURATION) {
        test_phase++;
        phase_start_time = millis();

        if (test_phase > 10) {
            test_phase = 0;  // Reinicia ciclo
            Serial.println();
            Serial.println("========================================");
            Serial.println("  CICLO COMPLETO - Reiniciando...");
            Serial.println("========================================");
            delay(2000);
        }
    }

    // Executa apenas no inicio de cada fase
    static int last_phase = -1;
    if (test_phase != last_phase) {
        last_phase = test_phase;

        Serial.println();
        Serial.print("=== FASE ");
        Serial.print(test_phase + 1);
        Serial.println(" ===");

        switch (test_phase) {
            case 0:
                Serial.println("Teste 1: Motor PARADO");
                set_force("NEUTRAL", 0);
                break;

            case 1:
                Serial.println("Teste 2: ESQUERDA 30%");
                set_force("LEFT", 30);
                break;

            case 2:
                Serial.println("Teste 3: ESQUERDA 60%");
                set_force("LEFT", 60);
                break;

            case 3:
                Serial.println("Teste 4: Motor PARADO");
                set_force("NEUTRAL", 0);
                break;

            case 4:
                Serial.println("Teste 5: DIREITA 30%");
                set_force("RIGHT", 30);
                break;

            case 5:
                Serial.println("Teste 6: DIREITA 60%");
                set_force("RIGHT", 60);
                break;

            case 6:
                Serial.println("Teste 7: Motor PARADO");
                set_force("NEUTRAL", 0);
                break;

            case 7:
                Serial.println("Teste 8: Simulacao - Curva leve esquerda");
                // G lateral negativo = curva esquerda
                simulate_ff_calculation(-0.5, 15.0, -30);
                break;

            case 8:
                Serial.println("Teste 9: Simulacao - Curva forte direita");
                // G lateral positivo = curva direita
                simulate_ff_calculation(1.2, -45.0, 70);
                break;

            case 9:
                Serial.println("Teste 10: Simulacao - Reta com volante centralizado");
                simulate_ff_calculation(0.05, 2.0, 0);
                break;

            case 10:
                Serial.println("Teste 11: Motor PARADO (fim do ciclo)");
                set_force("NEUTRAL", 0);
                break;
        }
    }

    delay(100);
}
