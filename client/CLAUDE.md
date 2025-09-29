# CLAUDE.md - F1 Client Application

Este arquivo fornece orientações para o Claude Code ao trabalhar com o cliente F1 do projeto de carro de controle remoto.

## Visão Geral do Projeto

O **F1 Client** é a aplicação cliente do sistema de controle remoto F1. Ele recebe telemetria em tempo real, vídeo HD e processa comandos de controle enviados ao Raspberry Pi via comunicação UDP otimizada.

## Arquitetura do Cliente

### Estrutura de Pastas

```
client/
├── main.py                    # Ponto de entrada principal (103 linhas)
├── core/                      # Módulos principais do sistema
│   ├── __init__.py           # Exportações do pacote core
│   ├── config.py             # Configurações centralizadas
│   ├── application/          # Aplicação principal modularizada
│   │   ├── __init__.py      # Exportações da aplicação
│   │   ├── application.py   # Classe principal F1ClientApplication
│   │   └── managers/        # Gerenciadores especializados
│   │       ├── __init__.py  # Exportações dos gerenciadores
│   │       ├── components_manager.py   # Gerenciamento de componentes
│   │       ├── threads_manager.py      # Gerenciamento de threads
│   │       └── lifecycle_manager.py    # Gerenciamento do ciclo de vida
│   ├── argument_parser.py    # Parser e validação de argumentos
│   ├── signal_handler.py     # Gerenciamento de sinais (SIGINT/SIGTERM)
│   └── startup.py           # Banner e funções de inicialização
├── components/               # Componentes da interface e rede
│   ├── __init__.py          # Exportações do pacote components
│   ├── console_interface.py # Interface gráfica principal (Tkinter)
│   ├── network_client.py    # Cliente UDP bidirecional
│   ├── video_display.py     # Exibição de vídeo integrada
│   ├── sensor_display.py    # Processamento de dados BMI160
│   ├── keyboard_controller.py # Controles de teclado assíncronos
│   ├── slider_controller.py  # Controles deslizantes
│   └── simple_logger.py     # Sistema de logging
└── CLAUDE.md               # Este arquivo de documentação
```

## Módulos Core

### 1. main.py - Ponto de Entrada

**Responsabilidade**: Orquestrador principal da aplicação

```python
from core import (
    F1ClientApplication,
    create_argument_parser,
    validate_arguments,
    setup_signal_handlers,
    print_startup_banner,
)
```

**Funcionalidades**:

- Parse de argumentos da linha de comando
- Validação de parâmetros
- Criação da aplicação principal
- Configuração de handlers de sinal
- Cleanup forçado com `os._exit(0)` para evitar problemas com Tkinter

### 2. core/config.py - Configurações

**Responsabilidade**: Centralizador de todas as configurações do sistema

**Configurações Principais**:

```python
class Config:
    # Network
    DEFAULT_PORT = 9999          # Porta UDP para dados
    COMMAND_PORT = 9998          # Porta UDP para comandos
    DEFAULT_BUFFER_SIZE = 131072 # 128KB buffer

    # IPs fixos do projeto
    RASPBERRY_PI_IP = "192.168.5.33"
    CLIENT_IP = "192.168.5.12"

    # Limites de validação
    MIN_PORT = 1024
    MAX_PORT = 65535
    MIN_BUFFER_KB = 32
    MAX_BUFFER_KB = 1024
```

### 3. core/application/ - Aplicação Principal Modularizada

**Responsabilidade**: Gerenciamento de todos os componentes do sistema através de uma arquitetura modular

#### 3.1. core/application/application.py - Classe Principal

**Funcionalidades**:

- Centraliza a instância da aplicação F1ClientApplication
- Delega responsabilidades para gerenciadores especializados
- Configuração inicial e setup de filas de comunicação
- Coordenação entre componentes através de composição

```python
class F1ClientApplication:
    def __init__(self, port, buffer_size, debug_mode):
        # Gerenciadores especializados
        self.components_manager = ComponentsManager(self)
        self.threads_manager = ThreadsManager(self)
        self.lifecycle_manager = LifecycleManager(self)
```

#### 3.2. core/application/managers/ - Gerenciadores Especializados

##### ComponentsManager (components_manager.py)

- **Responsabilidade**: Inicialização e conexão de componentes
- **Funções**:
  - `initialize_components()`: Inicializa NetworkClient, VideoDisplay, SensorDisplay, ConsoleInterface
  - `_initialize_network_client()`: Setup do cliente UDP
  - `_initialize_video_display()`: Setup do sistema de vídeo
  - `_initialize_sensor_display()`: Setup do processamento BMI160
  - `_initialize_console_interface()`: Setup da interface Tkinter
  - `_connect_components()`: Conecta componentes entre si

##### ThreadsManager (threads_manager.py)

- **Responsabilidade**: Gerenciamento de threads do sistema
- **Threads Gerenciadas**:
  - **NetworkThread** (daemon): Recepção UDP
  - **VideoThread** (daemon): Processamento de vídeo
  - **ConsoleThread** (não-daemon): Interface principal
- **Funções**:
  - `start_threads()`: Inicia todas as threads
  - `_start_network_thread()`: Thread de recepção UDP
  - `_start_video_thread()`: Thread de processamento de vídeo
  - `_start_console_thread()`: Thread da interface principal
  - `join_threads_with_timeout()`: Aguarda threads com timeout controlado

##### LifecycleManager (lifecycle_manager.py)

- **Responsabilidade**: Gerenciamento do ciclo de vida da aplicação
- **Funções**:
  - `run()`: Execução principal da aplicação
  - `stop()`: Parada limpa e ordenada
  - `_stop_components()`: Para componentes em ordem reversa
- **Características**:
  - Tratamento de KeyboardInterrupt (Ctrl+C)
  - Cleanup forçado com timeouts
  - Ordem reversa de parada para evitar dependências

### 4. core/argument_parser.py - Parser de Argumentos

**Responsabilidade**: Processamento e validação de argumentos CLI

**Argumentos Suportados**:

- `--port/-p`: Porta UDP (padrão: 9999)
- `--buffer/-b`: Buffer em KB (padrão: 128)
- `--debug/-d`: Modo debug com logs detalhados

### 5. core/signal_handler.py - Gerenciamento de Sinais

**Responsabilidade**: Tratamento de sinais do sistema

**Sinais Tratados**:

- `SIGINT` (Ctrl+C): Parada limpa da aplicação
- `SIGTERM`: Encerramento do processo
- **Cleanup**: Força saída imediata com `os._exit(0)`

### 6. core/startup.py - Inicialização

**Responsabilidade**: Banner e funções de inicialização

**Funcionalidades**:

- Exibe banner de inicialização com configurações
- Mostra informações de rede (IPs, portas)
- Indica status de debug

## Componentes da Interface

### 1. components/console_interface.py - Interface Principal

**Responsabilidade**: Interface gráfica Tkinter com dashboard F1

**Características Principais**:

- **Layout 2-Colunas Responsivo**: Divisão otimizada da tela
  - **Coluna Esquerda**: Dados técnicos (Status, Instrumentos, Sensores BMI160, Force Feedback)
  - **Coluna Direita**: Elementos interativos (Vídeo, Controles, Comandos, Logs)
- **Sistema de Scroll Avançado**: Suporte a mouse wheel com Canvas
- **Vídeo Integrado**: Display incorporado na interface principal
- **Controles F1**:
  - Painel de instrumentos com RPM, marcha, throttle, velocidade
  - Controles de teclado assíncronos (WASD/Arrow keys)
  - Brake balance slider (0-100%)
  - Gear shifting manual (M/N keys)

**Dados Exibidos**:

- Status de conexão em tempo real
- 37+ campos do BMI160 (acelerômetro, giroscópio, G-forces)
- Eventos detectados (curvas, freios, aceleração, impactos)
- Force feedback para controles imersivos
- Estatísticas de rede (FPS, throughput, latência)

### 2. components/network_client.py - Cliente UDP

**Responsabilidade**: Comunicação UDP bidirecional com Raspberry Pi

**Características**:

- **Comunicação Bidirecional**:
  - **Porta 9999**: Recebe dados (vídeo + telemetria)
  - **Porta 9998**: Envia comandos
- **Modo IP Fixo**: Configuração otimizada para performance
  - Raspberry Pi: 192.168.5.33
  - Cliente: 192.168.5.12
- **Protocolo de Comando**:
  ```
  CONNECT/DISCONNECT/PING:<timestamp>
  CONTROL:THROTTLE:<0-100>
  CONTROL:BRAKE:<0-100>
  CONTROL:STEERING:<-100-+100>
  CONTROL:BRAKE_BALANCE:<0-100>
  CONTROL:GEAR_UP/GEAR_DOWN
  ```

**Formato de Pacote Recebido**:

```
| 4 bytes    | 4 bytes     | N bytes    | M bytes      |
| frame_size | sensor_size | frame_data | sensor_data  |
```

### 3. components/video_display.py - Exibição de Vídeo

**Responsabilidade**: Renderização otimizada de vídeo na interface Tkinter

**Otimizações de Performance**:

- **Frame Dropping**: Descarta frames antigos para manter tempo real
- **Batch Processing**: Processa fila inteira e exibe apenas frame mais recente
- **Smart Resizing**: Redimensiona apenas quando necessário (>50px diferença)
- **Fast Interpolation**: Usa INTER_NEAREST para reduzir CPU
- **60 FPS Máximo**: Ciclo de 16ms para latência mínima

**Melhorias de Latência**:

- **Tkinter Otimizado**: ~30-50ms delay (competitivo com OpenCV)
- **Conversão PIL Direta**: Modo RGB especificado
- **Overlays Otimizados**: Info de FPS/resolução apenas a cada 5º frame

### 4. components/sensor_display.py - Processamento de Sensores

**Responsabilidade**: Processamento e organização de dados BMI160

**Dados Suportados (37+ campos)**:

- **Dados Raw BMI160**: Valores LSB do acelerômetro/giroscópio
- **Dados Físicos**: Conversões para m/s² e °/s
- **Forças G**: Cálculos de G-force (frontal, lateral, vertical)
- **Ângulos Integrados**: Roll, pitch, yaw
- **Eventos Detectados**: Curvas, freios, aceleração, impactos
- **Force Feedback**: Intensidades para volante, pedais, assento
- **Metadados**: Timestamps, contadores, configurações

**Características**:

- Processamento automático de tipos numpy
- Validação de dados recebidos
- Histórico para gráficos (configurável)
- Detecção de anomalias
- Estatísticas em tempo real

### 5. components/keyboard_controller.py - Controles de Teclado

**Responsabilidade**: Sistema de input assíncrono para controle de marchas

**Controles Suportados**:

- **Marcha**: M (gear up), N (gear down)
- **Tipo de Controle**: Instantâneo (pressionar) para mudança de marcha
- **Taxa de Atualização**: 20 comandos/segundo
- **Feedback Visual**: Flash verde para mudanças de marcha

### 6. components/slider_controller.py - Controles Deslizantes

**Responsabilidade**: Sistema principal de controle do veículo via sliders

**Controles Disponíveis**:

- **Throttle**: Slider vertical (0-100%) para aceleração
- **Brake**: Slider vertical (0-100%) para frenagem
- **Steering**: Slider horizontal (-100 a +100) para direção
- **Feedback Visual**: Labels coloridos em tempo real
- **Thread Safety**: Envio assíncrono sem travar UI

### 7. components/simple_logger.py - Sistema de Logging

**Responsabilidade**: Sistema de log centralizado

**Níveis Suportados**: DEBUG, INFO, WARNING, ERROR
**Características**: Thread-safe, formatação com timestamps

## Protocolo de Comunicação

### Configuração de Rede (Modo IP Fixo)

```
Raspberry Pi: 192.168.5.33:9999 (dados) / :9998 (comandos)
Cliente:      192.168.5.12:9999   (dados) / :9998 (comandos)
```

### Fluxo de Conexão

1. **Raspberry Pi** inicia e começa envio para IP fixo do cliente
2. **Cliente** inicia e recebe stream de dados imediatamente
3. **Comunicação bidirecional** ativa desde o startup
4. **Controles em tempo real** sem overhead de descoberta

### Comandos de Controle

**Sintaxe**: `CONTROL:<TIPO>:<VALOR>`

**Comandos Disponíveis**:

- `THROTTLE:0-100` - Aceleração
- `BRAKE:0-100` - Força de frenagem
- `STEERING:-100 a +100` - Ângulo de direção
- `BRAKE_BALANCE:0-100` - Distribuição de freio (frente/trás)
- `GEAR_UP` - Mudança para marcha superior
- `GEAR_DOWN` - Mudança para marcha inferior

## Características da Interface

### Layout Responsivo Moderno

- **Janela Principal**: 1400x900px (redimensionável)
- **Grid 2-Colunas**: Utilização máxima da largura da tela
- **Scroll Vertical**: Suporte completo com mouse wheel
- **Canvas-Based**: Sistema de scroll responsivo

### Painel de Instrumentos F1

- **RPM Gauge**: Tacômetro digital em tempo real
- **Gear Display**: Indicador numérico grande (1-5)
- **Throttle Display**: Porcentagem com feedback colorido
- **Speed Display**: Velocidade calculada em km/h

### Integração de Vídeo

- **Display Integrado**: Vídeo incorporado na interface principal
- **Performance Otimizada**: Pipeline de vídeo otimizado para Tkinter
- **Aspect Ratio**: Preservação automática das proporções
- **Status em Tempo Real**: Informações de resolução e FPS

## Execução e Comandos

### Inicialização

```bash
cd codigo/client
python3 main.py [opções]
```

### Opções de Linha de Comando

```bash
python3 main.py --port 9999 --buffer 128 --debug
```

### Controles em Tempo Real

**Requisito**: Clicar na janela da interface para ativar controles de teclado

**Mapeamento de Teclas**:

- `M`: Subir marcha (GEAR_UP)
- `N`: Descer marcha (GEAR_DOWN)

**Controles por Sliders**:

- **Throttle**: Slider vertical para aceleração (0-100%)
- **Brake**: Slider vertical para frenagem (0-100%)
- **Steering**: Slider horizontal para direção (-100 a +100)
- **Brake Balance**: Slider horizontal para distribuição de freio (0-100%)

## Dependências Principais

### Pacotes Python

```python
# Interface gráfica
tkinter, PIL (Pillow)

# Processamento de vídeo
opencv-python, numpy

# Rede e threading
socket, threading, queue

# Utilitários
time, json, struct
```

### Arquitetura de Threading

- **Thread Principal**: Interface Tkinter (não-daemon)
- **Thread de Rede**: Recepção UDP (daemon)
- **Thread de Vídeo**: Processamento de frames (daemon)
- **Comunicação**: Sistema de filas thread-safe

## Tratamento de Erros e Cleanup

### Shutdown Limpo

1. **Signal Handlers**: Captura SIGINT/SIGTERM
2. **Parada Ordenada**: Componentes parados em ordem reversa
3. **Thread Cleanup**: Timeout controlado para threads daemon
4. **Tkinter Cleanup**: Limpeza agressiva de recursos
5. **Força Saída**: `os._exit(0)` para evitar problemas de garbage collection

### Tratamento de Erros

- **Conexão de Rede**: Reconexão automática e timeouts
- **Processamento de Vídeo**: Proteção contra frames corrompidos
- **Interface**: Proteção contra destruição de widgets
- **Sensor Data**: Validação de dados e valores padrão

## Melhorias Implementadas

### Arquitetura Modular (Nova)

- **Aplicação Modularizada**: Separação da F1ClientApplication em gerenciadores especializados
- **Managers Pattern**: Responsabilidades específicas (ComponentsManager, ThreadsManager, LifecycleManager)
- **Manutenibilidade**: Código mais fácil de entender, debugar e estender
- **Responsabilidade Única**: Cada manager tem uma função específica e bem definida
- **Escalabilidade**: Estrutura preparada para futuras expansões

### Otimizações de Performance

- **Fixed IP Mode**: Elimina overhead de descoberta de rede
- **Frame Dropping**: Mantém display em tempo real
- **Asynchronous Controls**: Prevents UI freezing
- **Thread Optimization**: Daemon threads para componentes secundários

### Interface Melhorada

- **2-Column Responsive Layout**: Uso otimizado do espaço
- **Integrated Video**: Eliminação de janelas separadas
- **Advanced Scrolling**: Sistema completo de scroll com mouse
- **F1-Style Dashboard**: Instrumentos profissionais

### Estabilidade

- **Tkinter Cleanup Fixes**: Eliminação de crashes na saída
- **Thread Safety**: Locks e filas para comunicação segura
- **Error Recovery**: Degradação elegante quando componentes falham
- **Memory Management**: Gerenciamento adequado de referências

## Notas de Desenvolvimento

### Padrões de Código

- **PEP 8**: Conformidade com convenções Python
- **Type Hints**: Usados extensivamente para manutenibilidade
- **Docstrings**: Documentação abrangente em português
- **Modular Architecture**: Separação clara de responsabilidades

### Filosofia de Design

- **Real-time First**: Otimizado para baixa latência
- **User Experience**: Interface intuitiva estilo F1
- **Reliability**: Tratamento robusto de erros
- **Performance**: Otimizações em todos os níveis

### Estrutura de Packages

- **core/**: Lógica fundamental e configurações
  - **application/**: Aplicação modularizada com managers especializados
  - **managers/**: Gerenciadores de responsabilidades específicas
- **components/**: Interface e comunicação
- **Imports Relativos**: Uso de imports relativos nos packages
- **Clean Entry Point**: main.py minimalista (103 linhas)
- **Modular Design**: Separação clara de responsabilidades em arquivos temáticos

---

**Versão**: 2.0
**Autor**: Sistema F1 Remote Control
**Última Atualização**: Setembro 2025
