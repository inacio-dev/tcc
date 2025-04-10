#!/usr/bin/env python3
import queue
import socket
import threading
import time

# Dicionário para armazenar informações dos Arduinos:
# Chave: ID do Arduino
# Valor: {"address": (ip, port), "status": último status recebido}
arduinos = {}

# Cada Arduino terá sua própria fila de log (para exibição local)
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


def handle_arduino_log(arduino_id):
    """Thread que processa os logs de um Arduino específico."""
    log_queue = arduino_queues[arduino_id]
    while True:
        log_message = log_queue.get()
        if log_message is None:
            break  # Sinal para encerrar a thread
        print(f"[Arduino {arduino_id}] {log_message}")
        log_queue.task_done()


def session_manager():
    """
    Thread que periodicamente verifica a atividade dos clientes.
    Se um cliente não enviar mensagens (ou keepalive) por CLIENT_TIMEOUT segundos, sua sessão é removida.
    """
    while True:
        current_time = time.time()
        for arduino_id, clients in list(authorized_clients.items()):
            for client_addr, last_active in list(clients.items()):
                if current_time - last_active > CLIENT_TIMEOUT:
                    print(
                        f"Removendo cliente {client_addr} do Arduino {arduino_id} por inatividade."
                    )
                    del authorized_clients[arduino_id][client_addr]
        time.sleep(5)


def status_printer():
    """Thread que exibe periodicamente o status do servidor."""
    while True:
        print("\n===== STATUS ATUAL DO SERVIDOR =====")
        print("Arduinos registrados:")
        for arduino_id, info in arduinos.items():
            print(
                f"  ID: {arduino_id} | Endereço: {info['address']} | Status: {info['status']}"
            )
        print("Clientes autorizados:")
        for aid, clients in authorized_clients.items():
            print(f"  Arduino {aid}: {list(clients.keys())}")
        print("=====================================\n")
        time.sleep(10)


def udp_server():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((UDP_IP, UDP_PORT))
    print(f"Servidor UDP rodando em {UDP_IP}:{UDP_PORT}")

    while True:
        data, addr = sock.recvfrom(BUFFER_SIZE)
        message = data.decode("utf-8").strip()
        print(f"Recebido de {addr}: {message}")

        # Espera-se o formato: "ID;TIPO;DADOS"
        try:
            parts = message.split(";")
            if len(parts) < 3:
                print("Formato de mensagem inválido.")
                continue
            arduino_id = parts[0]
            msg_type = parts[1].upper()
            payload = ";".join(parts[2:])
        except Exception as e:
            print("Erro ao parsear mensagem:", e)
            continue

        # Se o Arduino não estiver registrado, cria seu registro, fila de log e clientes autorizados
        if arduino_id not in arduinos:
            arduinos[arduino_id] = {"address": None, "status": ""}
            arduino_queues[arduino_id] = queue.Queue()
            authorized_clients[arduino_id] = {}
            threading.Thread(
                target=handle_arduino_log, args=(arduino_id,), daemon=True
            ).start()
            print(f"Registrado novo Arduino com ID {arduino_id}.")

        if msg_type == "LOGIN":
            # O cliente envia: "ID;LOGIN;senha"
            expected_password = arduino_passwords.get(arduino_id)
            if expected_password is None:
                error_msg = (
                    f"{arduino_id};LOGIN_FAIL;Arduino não configurado para acesso."
                )
                sock.sendto(error_msg.encode("utf-8"), addr)
                print(
                    f"Login falhou para {addr} no Arduino {arduino_id} (sem senha configurada)."
                )
                continue
            if payload == expected_password:
                # Registra o cliente com o timestamp atual
                authorized_clients[arduino_id][addr] = time.time()
                success_msg = f"{arduino_id};LOGIN_OK;Conectado com sucesso."
                sock.sendto(success_msg.encode("utf-8"), addr)
                print(f"Cliente {addr} autenticado no Arduino {arduino_id}.")
                arduino_queues[arduino_id].put(
                    f"Cliente {addr} autenticado com sucesso."
                )
            else:
                error_msg = f"{arduino_id};LOGIN_FAIL;Senha incorreta."
                sock.sendto(error_msg.encode("utf-8"), addr)
                print(f"Cliente {addr} falhou na autenticação do Arduino {arduino_id}.")
            continue

        elif msg_type == "KEEPALIVE":
            # O cliente envia mensagens de KEEPALIVE para manter a sessão ativa
            if addr in authorized_clients.get(arduino_id, {}):
                authorized_clients[arduino_id][addr] = time.time()
                sock.sendto(f"{arduino_id};KEEPALIVE_OK;".encode("utf-8"), addr)
                print(f"Keepalive recebido de {addr} para Arduino {arduino_id}.")
            continue

        elif msg_type == "STATUS":
            # Mensagem vinda do Arduino: atualiza status e encaminha para os clientes autorizados
            arduinos[arduino_id]["address"] = addr
            arduinos[arduino_id]["status"] = payload
            log_text = f"Status atualizado: {payload}"
            arduino_queues[arduino_id].put(log_text)
            for client_addr in authorized_clients.get(arduino_id, {}):
                forward_message = f"{arduino_id};STATUS;{payload}"
                sock.sendto(forward_message.encode("utf-8"), client_addr)
                print(
                    f"Encaminhado STATUS para cliente {client_addr} do Arduino {arduino_id}."
                )

        elif msg_type == "CMD":
            # O cliente envia um comando: "ID;CMD;comando"
            if addr not in authorized_clients.get(arduino_id, {}):
                error_msg = f"{arduino_id};CMD_FAIL;Cliente não autenticado."
                sock.sendto(error_msg.encode("utf-8"), addr)
                print(
                    f"Comando de {addr} rejeitado para Arduino {arduino_id} (não autenticado)."
                )
                continue
            # Atualiza o timestamp do cliente para manter a sessão ativa
            authorized_clients[arduino_id][addr] = time.time()
            arduino_addr = arduinos[arduino_id]["address"]
            if arduino_addr:
                forward_message = f"{arduino_id};CMD;{payload}"
                sock.sendto(forward_message.encode("utf-8"), arduino_addr)
                arduino_queues[arduino_id].put(
                    f"Comando enviado para Arduino: {payload}"
                )
                print(
                    f"Comando de {addr} encaminhado para Arduino {arduino_id}: {payload}"
                )
            else:
                error_msg = f"{arduino_id};CMD_FAIL;Arduino offline ou não registrado."
                sock.sendto(error_msg.encode("utf-8"), addr)
                print(
                    f"Comando de {addr} não pode ser encaminhado para Arduino {arduino_id} (sem endereço)."
                )
        else:
            print(f"Tipo de mensagem desconhecido: {msg_type}")


if __name__ == "__main__":
    try:
        # Inicia a thread que gerencia as sessões de clientes (keepalive)
        session_thread = threading.Thread(target=session_manager, daemon=True)
        session_thread.start()

        # Inicia a thread que exibe periodicamente o status do servidor
        status_thread = threading.Thread(target=status_printer, daemon=True)
        status_thread.start()

        # Inicia o servidor UDP em uma thread separada
        server_thread = threading.Thread(target=udp_server, daemon=True)
        server_thread.start()

        # Exibe mensagem inicial e mantém o script rodando
        print(
            "Servidor iniciado. Aguardando conexões de clientes externos e Arduinos..."
        )
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Servidor interrompido manualmente.")
