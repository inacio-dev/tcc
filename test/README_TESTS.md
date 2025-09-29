# Testes dos Sistemas do Carrinho F1

Este diretório contém testes independentes para verificar o funcionamento de todos os sistemas do carrinho F1.

## Arquivos de Teste

### 📡 `test_bmi160_direct.py`
Teste completo do sensor BMI160 (6-axis IMU).

**O que testa:**
- Inicialização I2C e verificação CHIP_ID
- Leitura de dados raw (acelerômetro + giroscópio)
- Conversão para unidades físicas
- Calibração automática
- Detecção de eventos (impactos, curvas)
- Estatísticas de funcionamento

**Como executar:**
```bash
cd /home/inacio-rasp/tcc
python test/test_bmi160_direct.py
```

### ⚙️ `test_motor_direct.py`
Teste completo do sistema de motor e transmissão F1.

**O que testa:**
- Inicialização do motor RS550
- Sistema de transmissão 5-marchas
- Zonas de eficiência F1
- Controle PWM e aceleração
- Mudanças de marcha automáticas/manuais
- Estatísticas de desempenho

**Como executar:**
```bash
cd /home/inacio-rasp/tcc
python test/test_motor_direct.py
```

### 🏎️ `test_steering.py`
Teste completo do sistema de direção (SteeringManager).

**O que testa:**
- Inicialização do sistema
- Movimentos básicos (-100% a +100%)
- Diferentes modos (Normal, Sport, Comfort, Parking)
- Limites e valores extremos
- Estatísticas do sistema

**Como executar:**
```bash
cd /home/inacio-rasp/tcc
python test/test_steering.py
```

### 🛑 `test_brake.py`
Teste completo do sistema de freios (BrakeManager).

**O que testa:**
- Inicialização do sistema
- Aplicação progressiva de freios (0-100%)
- Balanço de freios (frontal/traseiro)
- Freio de emergência
- Limites e valores extremos
- Estatísticas do sistema

**Como executar:**
```bash
cd /home/inacio-rasp/tcc
python test/test_brake.py
```

### 🌡️ `test_temperature_sensor.py`
Teste completo do sensor de temperatura DS18B20.

**O que testa:**
- Verificação de configuração 1-Wire
- Inicialização do TemperatureManager
- Leitura única de temperatura
- Leituras contínuas com estatísticas
- Detecção de zonas térmicas
- Funcionalidade de histórico

**Como executar:**
```bash
cd /home/inacio/Documentos/tcc/codigo
python test/test_temperature_sensor.py
```

### 🚀 `quick_temp_test.py`
Teste rápido e simples do sensor DS18B20 (sem dependências do projeto).

**O que testa:**
- Configuração básica 1-Wire
- Leituras diretas do sistema de arquivos
- Conversão de temperaturas (°C, °F, K)
- Status térmico em tempo real
- Estatísticas básicas

**Como executar:**
```bash
cd /home/inacio/Documentos/tcc/codigo
python test/quick_temp_test.py
```

## Pré-requisitos

### Hardware Necessário
- **Servos via PCA9685**: Freios dianteiro/traseiro + direção (canais 0/1/2)
- **Sensor de temperatura**: DS18B20 conectado ao GPIO4 (Pin 7)
- **Alimentação**: 5-6V para os servos via PCA9685

### Conexões dos Servos (via PCA9685)
```
PCA9685 → Raspberry Pi:
├── VCC → Pin 1 (3.3V)
├── GND → Pin 6 (GND)
├── SCL → Pin 5 (GPIO3)
└── SDA → Pin 3 (GPIO2)

Servos MG996R → PCA9685:
├── Freio Frontal  → Canal 0
├── Freio Traseiro → Canal 1
└── Direção        → Canal 2

GPIOs LIBERADOS (agora livres):
├── GPIO4  (Pin 7)  → DS18B20
├── GPIO17 (Pin 11) → Livre
└── GPIO24 (Pin 18) → Livre
```

### Conexões do Sensor DS18B20
```
DS18B20:
├── VDD (Vermelho)  → Pin 1 (3.3V)
├── GND (Preto)     → Pin 6 (GND)
├── DQ (Amarelo)    → Pin 7 (GPIO4)
└── Pull-up         → Resistor 4.7kΩ entre DQ e VDD
```

**Configuração 1-Wire necessária:**
```bash
sudo raspi-config
# Interface Options → 1-Wire → Enable

# Adicionar ao /boot/firmware/config.txt:
dtoverlay=w1-gpio,gpiopin=4

sudo reboot
```

### Software
- Python 3.7+
- RPi.GPIO
- Raspberry Pi OS com GPIO habilitado

## Interpretando os Resultados

### ✅ Sucesso Esperado
```
✅ Sistema de direção inicializado com sucesso!
🏎️ Testando Centro: 0.0%
   → Ângulo servo: 90.0°
   → Porcentagem: 0.0%
```

### ❌ Possíveis Erros

**GPIO não disponível:**
```
❌ RPi.GPIO não disponível - hardware GPIO obrigatório
```
**Solução:** Execute no Raspberry Pi com GPIO habilitado.

**Falha na inicialização:**
```
❌ Falha ao inicializar sistema de direção
```
**Soluções:**
- Verifique conexões dos servos
- Confirme alimentação adequada (5-6V)
- Teste continuidade dos cabos PWM

**Sem resposta do servo:**
```
⚠️ Servo não responde aos comandos
```
**Soluções:**
- Verifique se servo está recebendo alimentação
- Teste com multímetro se há sinal PWM no GPIO
- Verifique se cabo signal não está invertido

## Logs Importantes

### Durante Inicialização
```
✓ SteeringManager importado com sucesso
✅ Sistema de direção inicializado com sucesso!
✅ Sistema de freios inicializado com sucesso!
```

### Durante Movimentos
```
🏎️ DIREÇÃO: -45.0% recebido
🔧 Direção: -45% → -28.5° (Velocidade: 0.0 km/h)

🛑 FREIO: 50.0% recebido
⚖️ Distribuição: Frontal 30.0% | Traseiro 20.0%
```

## Troubleshooting

### Problema: Servo não se move
1. Verifique alimentação (5-6V)
2. Teste continuidade do cabo signal
3. Confirme GPIO correto
4. Verifique se servo não está danificado

### Problema: Movimento irregular
1. Pode ser problema de alimentação instável
2. Adicione capacitores (470µF + 10µF)
3. Use fonte externa para servos
4. Verifique interferência de outros dispositivos

### Problema: Erro de permissions
```bash
sudo python test/test_steering.py
```

### Problema: ImportError
Certifique-se de estar no diretório correto:
```bash
cd /home/inacio-rasp/tcc
python test/test_steering.py
```

## Interpretação dos Ângulos

### Sistema de Direção
- **-100%** = -45° (máximo esquerda)
- **0%** = 90° (centro)
- **+100%** = 135° (máximo direita)

### Sistema de Freios
- **0%** = 0° (freio solto)
- **100%** = 90° (freio máximo)

## Dicas de Teste

1. **Teste individual primeiro**: Use `test_steering.py` e `test_brake.py` antes do combinado
2. **Observe logs**: Todos os comandos devem aparecer nos logs
3. **Movimento visual**: Servos devem se mover visivelmente
4. **Sons normais**: Servos fazem ruído leve ao se mover
5. **Emergência**: Ctrl+C para parar teste a qualquer momento

## Próximos Passos

Após confirmar que os testes passam:
1. Execute o sistema principal: `python raspberry/main.py`
2. Teste com cliente: `python client/main.py`
3. Use sliders para controle em tempo real
4. Monitore logs para confirmação de funcionamento