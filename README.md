```
sudo apt update
sudo apt install build-essential python3-dev libcap-dev

sudo apt install libcamera-apps python3-libcamera

pip install --upgrade pip wheel
pip install -r requirements.txt

sudo apt install python3-opencv python3-numpy python3-picamera2 python3-libcamera

# Para sensores I2C (BMI160)
sudo apt install python3-smbus

# Para smbus2 (Debian/Raspberry Pi OS protege sistema)
# Opção 1: Usar python3-smbus (já instalado acima)
# Opção 2: Forçar instalação (NÃO recomendado para produção):
pip3 install smbus2 --break-system-packages

# Opção 3: Usar ambiente virtual (RECOMENDADO):
# python3 -m venv venv
# source venv/bin/activate
# pip install smbus2
```

asasfasfasf

```
# Baixar a biblioteca
git clone https://github.com/BLavery/lib_nrf24.git
cd lib_nrf24
# Instalar
sudo cp lib_nrf24.py /usr/local/lib/python3.*/dist-packages/
# Ou alternativamente:
# sudo cp lib_nrf24.py /usr/lib/python3/dist-packages/
```
