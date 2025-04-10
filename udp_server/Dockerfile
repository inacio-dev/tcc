FROM python:3.13.2

ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Copia o código do servidor para dentro do container
COPY main.py .

# Expõe a porta UDP 5005
EXPOSE 5005/udp

# Comando para iniciar o servidor
CMD ["python", "main.py"]
