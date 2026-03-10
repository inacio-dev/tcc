# Configuração I2C - Raspberry Pi 4

## Dispositivos no Barramento I2C-1

| Endereço | Dispositivo | Função |
|----------|-------------|--------|
| 0x40     | INA219      | Monitoramento de energia |
| 0x41     | PCA9685     | PWM para servos (A0 soldado) |
| 0x68     | BMI160      | IMU (acelerômetro + giroscópio) |

## Verificar Dispositivos Conectados

```bash
i2cdetect -y 1
```

## Velocidade do Barramento (Baudrate)

### Configuração

Arquivo: `/boot/firmware/config.txt` (Bookworm+) ou `/boot/config.txt` (versões anteriores)

Para 400kHz (Fast mode), adicionar como linha separada:

```
dtparam=i2c_arm=on
dtparam=i2c_arm_baudrate=400000
```

> **IMPORTANTE**: NÃO usar vírgula na mesma linha (`dtparam=i2c_arm=on,i2c_arm_baudrate=400000`).
> Usar duas linhas `dtparam=` separadas.

Após editar: `sudo reboot`

### Verificar Baudrate Atual

```bash
# Ler clock-frequency do device tree (retorna binário, usar xxd)
xxd /sys/firmware/devicetree/base/soc/i2c@7e804000/clock-frequency
```

Valores esperados:
- `0001 86a0` = **100000 Hz** (100kHz — padrão)
- `0006 1a80` = **400000 Hz** (400kHz — Fast mode)

> **Nota**: `xxd` pode não estar instalado por padrão. Instalar com: `sudo apt install xxd`

### Encontrar o Caminho Correto

Se o caminho acima não existir:

```bash
find /sys -name clock-frequency 2>/dev/null | grep i2c
```

O barramento I2C-1 ARM é o `i2c@7e804000`.

### Comandos que NÃO Funcionam para Verificar

- `sudo vcgencmd get_config i2c_arm_baudrate` → retorna "unknown" nesta versão do firmware
- `sudo cat /sys/module/i2c_bcm2835/parameters/baudrate` → arquivo não existe
- `dmesg | grep i2c` → mostra apenas `brcmstb-i2c` (HDMI), NÃO o barramento ARM

### Barramentos I2C no RPi4

| Caminho Device Tree | Controlador | Uso |
|---------------------|-------------|-----|
| `i2c@7e804000`      | bcm2835 (ARM) | **Sensores/periféricos (I2C-1)** |
| `i2c@7ef04500`      | brcmstb | HDMI 0 |
| `i2c@7ef09500`      | brcmstb | HDMI 1 |
| `i2c@7e205000`      | bcm2835 | I2C-0 (câmera/display) |

## Velocidades Suportadas

| Modo | Velocidade | Suporte |
|------|-----------|---------|
| Standard | 100 kHz | Todos os dispositivos |
| Fast | 400 kHz | BMI160, PCA9685, INA219 — todos suportam |
| Fast+ | 1 MHz | Não recomendado (nem todos suportam) |
