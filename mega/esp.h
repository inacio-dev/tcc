#ifndef ESP_H
#define ESP_H

#include "WiFiEsp.h"
#include "WiFiEspUdp.h"

const int UDP_BUFFER_SIZE = 128;
byte packetBuffer[UDP_BUFFER_SIZE];

char serverAddress[] = "192.168.5.255";  // IP do seu servidor UDP Python
unsigned int serverPort = 5005;

WiFiEspUDP Udp;
unsigned long lastStatusSent = 0;

// Envia mensagem de status indicando que o Arduino está online.
// Formato: "ID;STATUS;Arduino online"
void sendStatusMessage() {
  char statusMessage[] = "1;STATUS;Arduino online";
  Udp.beginPacket(serverAddress, serverPort);
  Udp.write(statusMessage);
  Udp.endPacket();
  // Removido print no Serial para evitar impressão desnecessária.
}

// Processa mensagens UDP recebidas do servidor.
// Não há prints no Serial, pois se trata somente de atualização de controle.
void esp_update() {
  // Processa qualquer pacote recebido (sem impressão)
  int packetSize = Udp.parsePacket();
  if (packetSize) {
    Udp.read(packetBuffer, UDP_BUFFER_SIZE);
  }
  // Envia a atualização de status a cada 10 milissegundos
  if (millis() - lastStatusSent > 10) {
    sendStatusMessage();
    lastStatusSent = millis();
  }
}

// Inicializa a comunicação UDP e envia a mensagem de status inicial
void esp_begin() {
  Udp.begin(2390);  // Porta local do Arduino (pode ser alterada se necessário)
  sendStatusMessage();
}

#endif
