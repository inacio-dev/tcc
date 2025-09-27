#!/usr/bin/env python3
"""
test_servo_direto.py - Teste Direto do Servo no PCA9685
Teste com movimentos mais agressivos para verificar se servo está funcionando
"""

import time
import board
import busio
from adafruit_pca9685 import PCA9685
from adafruit_motor import servo

print("🔧 === TESTE DIRETO DO SERVO ===")
print("Este teste move o servo de forma mais agressiva")
print("para verificar se há algum movimento")

try:
    # Inicializar PCA9685
    i2c = busio.I2C(board.SCL, board.SDA)
    pca = PCA9685(i2c, address=0x40)
    pca.frequency = 50
    print("✓ PCA9685 inicializado")

    # Configurar servo no canal 2 (direção)
    steering_servo = servo.Servo(
        pca.channels[2],
        min_pulse=1000,  # 1ms
        max_pulse=2000,  # 2ms
    )
    print("✓ Servo configurado no canal 2")

    print("\n--- Teste de movimento agressivo ---")

    # Movimentos extremos para detectar qualquer movimento
    positions = [0, 45, 90, 135, 180, 90]  # Extremos e centro

    for i, pos in enumerate(positions):
        print(f"Movimento {i+1}: {pos}°")
        steering_servo.angle = pos
        time.sleep(2)  # Tempo maior para ver movimento

        input("Pressione ENTER para próxima posição (ou Ctrl+C para sair)...")

    print("\n--- Teste de oscilação ---")
    print("Movendo rapidamente entre extremos...")

    for cycle in range(5):
        print(f"Ciclo {cycle+1}/5")
        steering_servo.angle = 0    # Extremo esquerda
        time.sleep(0.5)
        steering_servo.angle = 180  # Extremo direita
        time.sleep(0.5)

    # Voltar ao centro
    steering_servo.angle = 90
    print("✓ Retornado ao centro")

except KeyboardInterrupt:
    print("\n⚠️ Teste interrompido")
except Exception as e:
    print(f"❌ Erro: {e}")
finally:
    try:
        steering_servo.angle = 90  # Centro
        pca.deinit()
    except:
        pass
    print("✓ Teste finalizado")

print("\n🔍 DIAGNÓSTICO:")
print("Se o servo NÃO se moveu:")
print("1. ❌ V+ não conectado (fonte externa 5V-6V)")
print("2. ❌ Servo defeituoso")
print("3. ❌ Conexão solta no canal 2")
print("\nSe o servo se moveu:")
print("✅ Hardware OK - problema no software original")