#include "WiFiEsp.h"
#include "SoftwareSerial.h"
#include "esp.h"

#define PIN_LED_NETWORK 22

void setup() {
  Serial.begin(115200);  // Apenas para debug inicial, se necessário
  Serial3.begin(115200);
  WiFi.init(&Serial3);

  pinMode(PIN_LED_NETWORK, OUTPUT);

  // Verifica a presença do shield WiFi
  if (WiFi.status() == WL_NO_SHIELD) {
    // Opcional: Remova prints se não for necessário debug
    while (true);
  }

  // Conecta à rede WiFi
  int status = WL_IDLE_STATUS;
  char ssid[] = "CARLOS ADP";
  char pass[] = "12991308";
  digitalWrite(PIN_LED_NETWORK, HIGH);
  while (status != WL_CONNECTED) {
    status = WiFi.begin(ssid, pass);
  }
  digitalWrite(PIN_LED_NETWORK, LOW);

  // Inicializa a comunicação UDP e envia o status inicial
  esp_begin();
}

void loop() {
  delay(1);      // Delay curto para permitir outras operações
  esp_update();  // Processa mensagens UDP e envia atualizações de status a cada 10ms
  // Aqui você pode adicionar outras lógicas de controle do carro
}
