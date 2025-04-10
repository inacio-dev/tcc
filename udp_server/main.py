#!/usr/bin/env python3
import queue
import socket
import threading
import time

# Dicionário para armazenar informações dos Arduinos:
# Chave: ID do Arduino
# Valor: {"address": (ip, port), "status": último status recebido}
arduinos = {}

# Cada Arduino terá sua própria fila (pode ser utilizada para logs, se necessário)
arduino_queues = {}

# Dicionário com as senhas configuradas para cada Arduino
arduino_passwords = {
    "1": "senha1",
    "2": "senha2",
    # Adicione outros IDs e senhas conforme necessário
}

# Dicionário para armazenar os clientes autorizados para cada Arduino
# Chave: ID do Arduino; Valor: dict com {cliente_addr: timestamp_última_atividade}
authorized_clients = {}

# Configurações do UDP
UDP_IP = "0.0.0.0"
UDP_PORT = 5005
BUFFER_SIZE = 1024

# Tempo limite para inatividade do cliente (em segundos)
CLIENT_TIMEOUT = 30


def print_connections_status():
    """Exibe um resumo minimalista dos Arduinos e clientes conectados."""
    print("=== Conexões Atuais ===")
    for arduino_id, info in arduinos.items():
        status = "conectado" if info["address"] else "offline"
        print(f"Arduino {arduino_id}: {status}")
    for aid, clients in authorized_clients.items():
        if clients:
            print(f"Clientes no Arduino {aid}: {list(clients.keys())}")
    print("=======================")


def session_manager():
    """
    Verifica periodicamente a atividade dos clientes.
    Se um cliente não enviar keepalive por CLIENT_TIMEOUT segundos, sua sessão é removida.
    """
    while True:
        current_time = time.time()
        for arduino_id, clients in list(authorized_clients.items()):
            for client_addr, last_active in list(clients.items()):
                if current_time - last_active > CLIENT_TIMEOUT:
                    print(
                        f"Cliente {client_addr} desconectado por inatividade do Arduino {arduino_id}."
                    )
                    del authorized_clients[arduino_id][client_addr]
                    print_connections_status()
        time.sleep(5)


def udp_server():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((UDP_IP, UDP_PORT))
    print(f"Servidor UDP rodando em {UDP_IP}:{UDP_PORT}")

    while True:
        data, addr = sock.recvfrom(BUFFER_SIZE)
        message = data.decode("utf-8").strip()

        # Espera-se o formato: "ID;TIPO;DADOS"
        try:
            parts = message.split(";")
            if len(parts) < 3:
                continue  # Ignora mensagens com formato inválido
            arduino_id = parts[0]
            msg_type = parts[1].upper()
            payload = ";".join(parts[2:])
        except Exception:
            continue

        # Registra o Arduino se ainda não estiver registrado
        if arduino_id not in arduinos:
            arduinos[arduino_id] = {"address": None, "status": ""}
            arduino_queues[arduino_id] = queue.Queue()
            authorized_clients[arduino_id] = {}
            print(f"Novo Arduino registrado com ID {arduino_id}.")
            print_connections_status()

        if msg_type == "LOGIN":
            # Verificação de senha para login do cliente
            expected_password = arduino_passwords.get(arduino_id)
            if expected_password is None:
                error_msg = (
                    f"{arduino_id};LOGIN_FAIL;Arduino não configurado para acesso."
                )
                sock.sendto(error_msg.encode("utf-8"), addr)
                continue
            if payload == expected_password:
                authorized_clients[arduino_id][addr] = time.time()
                success_msg = f"{arduino_id};LOGIN_OK;Conectado com sucesso."
                sock.sendto(success_msg.encode("utf-8"), addr)
                print(f"Cliente {addr} autenticado no Arduino {arduino_id}.")
                print_connections_status()
            else:
                error_msg = f"{arduino_id};LOGIN_FAIL;Senha incorreta."
                sock.sendto(error_msg.encode("utf-8"), addr)
            continue

        elif msg_type == "KEEPALIVE":
            if addr in authorized_clients.get(arduino_id, {}):
                authorized_clients[arduino_id][addr] = time.time()
                sock.sendto(f"{arduino_id};KEEPALIVE_OK;".encode("utf-8"), addr)
            continue

        elif msg_type == "STATUS":
            # Atualiza status do Arduino e encaminha para os clientes autorizados
            arduinos[arduino_id]["address"] = addr
            arduinos[arduino_id]["status"] = payload
            for client_addr in authorized_clients.get(arduino_id, {}):
                forward_message = f"{arduino_id};STATUS;{payload}"
                sock.sendto(forward_message.encode("utf-8"), client_addr)
            print_connections_status()

        elif msg_type == "CMD":
            # Processa comandos enviados por clientes autorizados ao Arduino
            if addr not in authorized_clients.get(arduino_id, {}):
                error_msg = f"{arduino_id};CMD_FAIL;Cliente não autenticado."
                sock.sendto(error_msg.encode("utf-8"), addr)
                continue
            authorized_clients[arduino_id][addr] = time.time()
            arduino_addr = arduinos[arduino_id]["address"]
            if arduino_addr:
                forward_message = f"{arduino_id};CMD;{payload}"
                sock.sendto(forward_message.encode("utf-8"), arduino_addr)
            else:
                error_msg = f"{arduino_id};CMD_FAIL;Arduino offline ou não registrado."
                sock.sendto(error_msg.encode("utf-8"), addr)
        # Ignora quaisquer outros tipos de mensagens
        else:
            continue


if __name__ == "__main__":
    try:
        threading.Thread(target=session_manager, daemon=True).start()
        threading.Thread(target=udp_server, daemon=True).start()

        print("Servidor iniciado. Aguardando conexões...")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Servidor interrompido manualmente.")
