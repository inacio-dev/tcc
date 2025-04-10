#!/usr/bin/env python3
import queue
import socket
import threading
import time

# Armazena informações dos Arduinos:
# Chave: ID do Arduino
# Valor: {"address": (ip, port), "status": último status recebido}
arduinos = {}

# Cada Arduino terá sua própria fila (opcional, para logs locais)
arduino_queues = {}

# Senhas configuradas para cada Arduino – utilizadas pelo cliente que deseja logar para enviar comandos
arduino_passwords = {
    "1": "senha1",
    "2": "senha2",
    # Adicione outros IDs e senhas conforme necessário
}

# Armazena os clientes autorizados para cada Arduino:
# Chave: ID do Arduino; Valor: dict com {cliente_addr: timestamp_última_atividade}
authorized_clients = {}

# Configurações do UDP
UDP_IP = "0.0.0.0"
UDP_PORT = 5005
BUFFER_SIZE = 1024

# Tempo limite para inatividade do cliente (em segundos)
CLIENT_TIMEOUT = 30


def print_connections_status():
    """Exibe um resumo dos Arduinos e clientes conectados."""
    print("=== Conexões Atuais ===")
    for arduino_id, info in arduinos.items():
        status = "conectado" if info["address"] else "offline"
        print(f"Arduino {arduino_id}: {status}, status: {info['status']}")
    for aid, clients in authorized_clients.items():
        if clients:
            print(f"Clientes no Arduino {aid}: {list(clients.keys())}")
    print("=======================")


def status_printer():
    """Imprime o status das conexões a cada 1 minuto."""
    while True:
        time.sleep(60)
        print_connections_status()


def session_manager():
    """
    Remove periodicamente clientes inativos.
    Se um cliente não enviar KEEPALIVE por CLIENT_TIMEOUT segundos,
    sua sessão é removida.
    """
    while True:
        current_time = time.time()
        for arduino_id, clients in list(authorized_clients.items()):
            for client_addr, last_active in list(clients.items()):
                if current_time - last_active > CLIENT_TIMEOUT:
                    print(
                        f"Cliente {client_addr} desconectado por inatividade no Arduino {arduino_id}."
                    )
                    del authorized_clients[arduino_id][client_addr]
        time.sleep(5)


def udp_server():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((UDP_IP, UDP_PORT))
    print(f"Servidor UDP rodando em {UDP_IP}:{UDP_PORT}")

    while True:
        data, addr = sock.recvfrom(BUFFER_SIZE)
        message = data.decode("utf-8").strip()
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
            print(f"Novo dispositivo registrado com ID {arduino_id}.")

        if msg_type == "STATUS":
            # Mensagem enviada pelo Arduino para atualizar seu status (online/offline, etc.)
            arduinos[arduino_id]["address"] = addr
            arduinos[arduino_id]["status"] = payload
            # Encaminha o status para os clientes autorizados, se houver
            for client_addr in authorized_clients.get(arduino_id, {}):
                forward_message = f"{arduino_id};STATUS;{payload}"
                sock.sendto(forward_message.encode("utf-8"), client_addr)
            # NÃO imprime status aqui; será impresso pela thread status_printer a cada 1 minuto

        elif msg_type == "LOGIN":
            # Login do cliente que deseja enviar comandos ao Arduino
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
                print(f"Cliente {addr} autenticado para o Arduino {arduino_id}.")
            else:
                error_msg = f"{arduino_id};LOGIN_FAIL;Senha incorreta."
                sock.sendto(error_msg.encode("utf-8"), addr)
            continue

        elif msg_type == "KEEPALIVE":
            # Atualiza timestamp dos clientes que mandam KEEPALIVE
            if addr in authorized_clients.get(arduino_id, {}):
                authorized_clients[arduino_id][addr] = time.time()
                sock.sendto(f"{arduino_id};KEEPALIVE_OK;".encode("utf-8"), addr)
            continue

        elif msg_type == "CMD":
            # Encaminha comandos do cliente para o Arduino, se o cliente estiver autenticado
            if addr not in authorized_clients.get(arduino_id, {}):
                error_msg = f"{arduino_id};CMD_FAIL;Cliente não autenticado."
                sock.sendto(error_msg.encode("utf-8"), addr)
                continue
            # Atualiza o timestamp do cliente para manter a sessão ativa
            authorized_clients[arduino_id][addr] = time.time()
            arduino_addr = arduinos[arduino_id]["address"]
            if arduino_addr:
                forward_message = f"{arduino_id};CMD;{payload}"
                sock.sendto(forward_message.encode("utf-8"), arduino_addr)
            else:
                error_msg = f"{arduino_id};CMD_FAIL;Arduino offline ou não registrado."
                sock.sendto(error_msg.encode("utf-8"), addr)
        else:
            continue  # Ignora outros tipos de mensagens


if __name__ == "__main__":
    try:
        threading.Thread(target=session_manager, daemon=True).start()
        threading.Thread(target=status_printer, daemon=True).start()
        threading.Thread(target=udp_server, daemon=True).start()

        print("Servidor iniciado. Aguardando conexões...")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Servidor interrompido manualmente.")
