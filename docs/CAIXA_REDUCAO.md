# Caixa de Redução - Discussão

Documento para discutir a necessidade de caixa de redução entre motor e diferencial.

## Status Atual

- **Data**: 2025-12-18
- **Status**: Proposta - análise de viabilidade
- **Configuração atual**: Motor RC 775 conectado diretamente ao diferencial

---

## Problema Atual

O motor RC 775 conectado diretamente ao diferencial resulta em velocidades **excessivamente altas** para um carrinho RC controlável.

### Dados do Sistema

| Componente | Valor |
|------------|-------|
| Motor | RC 775 |
| RPM motor | 6000-10000 (típico 9000 sob carga) |
| Diâmetro roda | 63mm |
| Circunferência roda | π × 0.063 = 0.198m |
| Redução atual | Nenhuma (1:1) |

### Velocidades Atuais (SEM redução)

```
Fórmula: Velocidade (km/h) = (RPM × circunferência × 60) / 1000
```

| Marcha | Limite PWM | RPM Motor | Velocidade | Problema |
|--------|------------|-----------|------------|----------|
| 1ª | 40% | 3600 | 42.8 km/h | Muito rápido para arranque |
| 2ª | 60% | 5400 | 64.2 km/h | Difícil controlar |
| 3ª | 80% | 7200 | 85.5 km/h | Perigoso |
| 4ª | 100% | 9000 | 106.9 km/h | Incontrolável |
| 5ª | 100% | 9000 | 106.9 km/h | Incontrolável |

**Conclusão**: Velocidades irrealistas para um carrinho RC de ~30cm.

---

## Solução Proposta

Adicionar **caixa de redução** entre o motor e o diferencial.

```
┌─────────────────────────────────────────────────────────────────────┐
│                    CONFIGURAÇÃO PROPOSTA                            │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ANTES (atual):                                                     │
│  Motor RC 775 ──────────────────────────► Diferencial → Rodas      │
│  (9000 RPM)                                 (9000 RPM)              │
│                                                                     │
│  DEPOIS (proposto):                                                 │
│  Motor RC 775 ──► Caixa Redução 5:1 ──► Diferencial → Rodas        │
│  (9000 RPM)         (÷5)                  (1800 RPM)               │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Análise de Reduções

### Comparativo de Velocidades

| Redução | 1ª (40%) | 2ª (60%) | 3ª (80%) | 4ª/5ª (100%) | Torque |
|---------|----------|----------|----------|--------------|--------|
| 1:1 (atual) | 42.8 km/h | 64.2 km/h | 85.5 km/h | 106.9 km/h | 1x |
| **3:1** | 14.3 km/h | 21.4 km/h | 28.5 km/h | 35.6 km/h | 3x |
| **5:1** | 8.6 km/h | 12.8 km/h | 17.1 km/h | 21.4 km/h | 5x |
| 10:1 | 4.3 km/h | 6.4 km/h | 8.5 km/h | 10.7 km/h | 10x |

### Recomendação por Uso

| Uso | Redução | Velocidade Máx | Justificativa |
|-----|---------|----------------|---------------|
| Pista lisa | 3:1 | 35.6 km/h | Bom equilíbrio velocidade/controle |
| **Misto (recomendado)** | **5:1** | **21.4 km/h** | Melhor controle + torque alto |
| Off-road/inclinações | 10:1 | 10.7 km/h | Máximo torque |

---

## Opções de Hardware

### Opção 1: Caixa de Redução Planetária

```
┌──────────────┐
│  Engrenagem  │
│  Planetária  │
│              │
│  ┌───────┐   │
│  │ Sol   │   │  ← Entrada (motor)
│  └───┬───┘   │
│      │       │
│  ┌───┴───┐   │
│  │Planeta│   │
│  └───┬───┘   │
│      │       │
│  ┌───┴───┐   │
│  │ Anel  │   │  ← Saída (diferencial)
│  └───────┘   │
└──────────────┘
```

| Modelo | Redução | Preço | Prós | Contras |
|--------|---------|-------|------|---------|
| 36mm Planetária | 3.71:1 | ~R$40 | Compacta | Pode ser fraca |
| 42mm Planetária | 5.18:1 | ~R$60 | Boa relação | Tamanho médio |
| 52mm Planetária | 10:1 | ~R$80 | Alto torque | Grande |

### Opção 2: Engrenagens Retas (Spur Gears)

| Configuração | Redução | Preço | Prós | Contras |
|--------------|---------|-------|------|---------|
| Pinhão 12T + Coroa 48T | 4:1 | ~R$25 | Barato, simples | Barulho, espaço |
| Pinhão 10T + Coroa 50T | 5:1 | ~R$25 | Boa redução | Precisa de caixa |
| Kit 2 estágios | 9:1 | ~R$50 | Alta redução | Complexo |

### Opção 3: Correia/Polia

| Configuração | Redução | Preço | Prós | Contras |
|--------------|---------|-------|------|---------|
| GT2 16T + 60T | 3.75:1 | ~R$30 | Silenciosa | Pode escorregar |
| HTD 15T + 75T | 5:1 | ~R$40 | Mais torque | Precisa tensionar |

---

## Cálculo Detalhado: Redução 5:1

### Velocidades Resultantes

```python
# Parâmetros
motor_rpm = 9000  # RPM máximo sob carga
reducao = 5.0
circunferencia = 0.198  # metros (roda 63mm)

# Cálculo por marcha
marchas = {
    1: 0.40,  # 40% do RPM
    2: 0.60,  # 60% do RPM
    3: 0.80,  # 80% do RPM
    4: 1.00,  # 100% do RPM
    5: 1.00,  # 100% do RPM
}

for marcha, fator in marchas.items():
    rpm_motor = motor_rpm * fator
    rpm_roda = rpm_motor / reducao
    velocidade_ms = (rpm_roda * circunferencia) / 60
    velocidade_kmh = velocidade_ms * 3.6
    print(f"{marcha}ª: {rpm_roda:.0f} RPM → {velocidade_kmh:.1f} km/h")
```

**Resultado:**
```
1ª:  720 RPM →  8.6 km/h  (ótimo para arranque)
2ª: 1080 RPM → 12.8 km/h  (aceleração controlada)
3ª: 1440 RPM → 17.1 km/h  (velocidade média)
4ª: 1800 RPM → 21.4 km/h  (alta velocidade)
5ª: 1800 RPM → 21.4 km/h  (máxima)
```

### Torque Resultante

```
Torque na roda = Torque motor × Redução × Eficiência

Com redução 5:1 e eficiência 90%:
Torque roda = Torque motor × 5 × 0.9 = 4.5× maior
```

**Benefícios:**
- Arrancada muito mais forte
- Capacidade de subir inclinações
- Menor stress no motor (trabalha em faixa mais eficiente)
- Melhor controle em baixa velocidade

---

## Impacto no Software

### Mudanças Necessárias

Se implementar redução física, o software de zonas de eficiência continua funcionando normalmente - ele limita PWM, não RPM.

**Nenhuma mudança de código necessária!**

O sistema de marchas atual já simula diferentes "potências":
- 1ª marcha: máx 40% PWM → baixa velocidade, alto torque
- 5ª marcha: máx 100% PWM → alta velocidade

Com a redução mecânica, essas velocidades simplesmente ficam mais realistas.

### Calibração do Conta-Giros

Após instalar redução, atualizar `MOTOR_MAX_RPM` para refletir RPM na roda:

```python
# Antes (sem redução)
MOTOR_MAX_RPM = 9000

# Depois (com redução 5:1)
MOTOR_MAX_RPM = 1800  # 9000 / 5
```

---

## Montagem Física

### Posicionamento

```
Vista Superior do Chassi:

    ┌─────────────────────────────────────┐
    │              FRENTE                 │
    │                                     │
    │  ┌─────────┐                        │
    │  │  Motor  │                        │
    │  │ RC 775  │                        │
    │  └────┬────┘                        │
    │       │                             │
    │  ┌────┴────┐                        │
    │  │  Caixa  │  ← NOVA PEÇA           │
    │  │ Redução │                        │
    │  └────┬────┘                        │
    │       │                             │
    │  ┌────┴────┐                        │
    │  │ Diferen-│                        │
    │  │  cial   │                        │
    │  └────┬────┘                        │
    │       │                             │
    │   ────┴────                         │
    │   Eixo Traseiro                     │
    │                                     │
    │              TRASEIRA               │
    └─────────────────────────────────────┘
```

### Acoplamento

| Método | Dificuldade | Precisão | Custo |
|--------|-------------|----------|-------|
| Acoplamento flexível | Fácil | Média | ~R$15 |
| Eixo com chaveta | Média | Alta | ~R$25 |
| Flange parafusado | Difícil | Muito alta | ~R$40 |

---

## Comparativo Final

| Aspecto | Sem Redução | Com Redução 5:1 |
|---------|-------------|-----------------|
| Velocidade máx | 107 km/h | 21 km/h |
| Torque nas rodas | 1x | 4.5x |
| Controle | Difícil | Fácil |
| Consumo bateria | Alto (motor forçado) | Menor (motor eficiente) |
| Arrancada | Fraca (patina) | Forte |
| Subidas | Não consegue | Consegue |
| Custo adicional | R$0 | R$40-80 |

---

## Recomendação Final

**Instalar caixa de redução planetária 5:1**

**Motivo:**
1. Velocidades realistas (8-21 km/h)
2. Torque 4.5x maior
3. Melhor controle
4. Motor trabalha em faixa eficiente
5. Custo acessível (~R$60)

---

## Próximos Passos

1. [ ] Medir espaço disponível no chassi
2. [ ] Escolher modelo de caixa de redução
3. [ ] Comprar caixa + acoplamentos
4. [ ] Montar e testar
5. [ ] Atualizar `MOTOR_MAX_RPM` no código (opcional)
6. [ ] Calibrar encoder de velocidade (se instalado)

---

## Histórico

| Data | Mudança |
|------|---------|
| 2025-12-18 | Documento inicial - análise de velocidades |
