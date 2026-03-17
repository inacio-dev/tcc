# Sistema de Transmissão e Zonas de Eficiência — Evolução

Este documento registra a evolução completa do sistema de transmissão: do modelo original (tabela if/else), passando pela proposta intermediária (Gaussiana, descartada), até o modelo final implementado (sistema de 1ª ordem com função de transferência G(s) = K/(τs+1)).

---

## 1. Modelo Original (Tabela if/else)

### 1.1 Limitadores de Marcha

Mapeamento linear `throttle → PWM` com teto por marcha:

```python
gear_limiters = {
    1: 12,   # 1ª marcha: 0-12%  (intervalo  6% útil, zona morta 0-6%)
    2: 25,   # 2ª marcha: 0-25%  (intervalo 13%)
    3: 45,   # 3ª marcha: 0-45%  (intervalo 20%)
    4: 70,   # 4ª marcha: 0-70%  (intervalo 25%)
    5: 100,  # 5ª marcha: 0-100% (intervalo 30%)
}

final_pwm = (throttle_percent / 100.0) * gear_limiters[gear]
```

### 1.2 Zonas de Eficiência (código original)

Cada marcha tinha 3 zonas definidas por faixas fixas de PWM com multiplicadores discretos:

```python
def _calculate_efficiency_zone(self, current_pwm: float) -> tuple:
    if self.current_gear == 1:
        # 1ª MARCHA (limitador: 12%, zona morta: 0-6%)
        if current_pwm <= 12:
            return "IDEAL", 1.0

    elif self.current_gear == 2:
        # 2ª MARCHA (limitador: 25%, entra com ~12% da 1ª)
        if 10 <= current_pwm <= 21:
            return "IDEAL", 1.0
        elif (5 <= current_pwm < 10) or (21 < current_pwm <= 24):
            return "SUBOPTIMAL", 0.1
        elif current_pwm < 5 or current_pwm > 24:
            return "POOR", 0.04

    elif self.current_gear == 3:
        # 3ª MARCHA (limitador: 45%, entra com ~25% da 2ª)
        if 22 <= current_pwm <= 39:
            return "IDEAL", 1.0
        elif (14 <= current_pwm < 22) or (39 < current_pwm <= 43):
            return "SUBOPTIMAL", 0.1
        else:
            return "POOR", 0.04

    elif self.current_gear == 4:
        # 4ª MARCHA (limitador: 70%, entra com ~45% da 3ª)
        if 40 <= current_pwm <= 62:
            return "IDEAL", 1.0
        elif (30 <= current_pwm < 40) or (62 < current_pwm <= 68):
            return "SUBOPTIMAL", 0.1
        else:
            return "POOR", 0.04

    elif self.current_gear == 5:
        # 5ª MARCHA (limitador: 100%, entra com ~70% da 4ª)
        if 65 <= current_pwm <= 90:
            return "IDEAL", 1.0
        elif (50 <= current_pwm < 65) or (90 < current_pwm <= 96):
            return "SUBOPTIMAL", 0.1
        else:
            return "POOR", 0.04

    return "POOR", 0.04
```

### 1.3 Aceleração por Zona (ODE de 1ª ordem disfarçada)

A aceleração era uma integração de Euler com coeficiente por partes:

```python
def _apply_f1_zone_acceleration(self, dt):
    DEAD_ZONE_PWM = 6.0
    DEAD_ZONE_RATE = 20.0

    zone, rate_multiplier = self._calculate_efficiency_zone(self.current_pwm)
    # rate_multiplier: IDEAL=1.0, SUBOPTIMAL=0.1, POOR=0.04

    base_rate = 50.0 / (self.base_acceleration_time * 50)  # = 0.02 %/frame
    zone_rate = base_rate * rate_multiplier

    pwm_diff = self.target_pwm - self.current_pwm

    if pwm_diff > 0:  # ACELERANDO
        if self.current_pwm < DEAD_ZONE_PWM and self.target_pwm >= DEAD_ZONE_PWM:
            # Rampa rápida para atravessar zona morta (0-6%)
            step = base_rate * DEAD_ZONE_RATE * dt * 50
            self.current_pwm = min(self.current_pwm + step, DEAD_ZONE_PWM)
        else:
            step = min(zone_rate * dt * 50, pwm_diff)
            self.current_pwm += step

    else:  # DESACELERANDO
        if self.current_pwm <= DEAD_ZONE_PWM and self.target_pwm < DEAD_ZONE_PWM:
            step = base_rate * DEAD_ZONE_RATE * dt * 50
            self.current_pwm = max(self.current_pwm - step, 0.0)
        else:
            if rate_multiplier >= 1.0:    decel = 2.0   # IDEAL: 2x
            elif rate_multiplier >= 0.1:  decel = 5.0   # SUBOPTIMAL: 5x
            else:                         decel = 10.0  # POOR: 10x

            brake_boost = 1.0 + (self.brake_input / 100.0) * 9.0
            decel *= brake_boost

            step = min(base_rate * decel * dt * 50, abs(pwm_diff))
            self.current_pwm -= step
```

### 1.4 Tabela Resumo das Zonas

```
Marcha | Zona Morta | POOR      | SUBÓTIMA   | IDEAL   | SUBÓTIMA  | POOR
-------|------------|-----------|------------|---------|-----------|--------
1ª     | 0-6%       | —         | —          | 6-12%   | —         | —
2ª     | 0-6%       | 6-8%     (*)  | 8-10%      | 10-21%  | 21-24%    | 24-25%
3ª     | 0-6%       | 6-14%    (*)  | 14-22%     | 22-39%  | 39-43%    | 43-45%
4ª     | 0-6%       | 6-30%    (*)  | 30-40%     | 40-62%  | 62-68%    | 68-70%
5ª     | 0-6%       | 6-50%    (*)  | 50-65%     | 65-90%  | 90-96%    | 96-100%

(*) zona morta 0-6% é comum a todas, o POOR começa em 6% efetivamente

Multiplicadores de aceleração:
- IDEAL:     1.0x  → base_rate * 1.0  = 2.0 %/s
- SUBÓTIMA:  0.1x  → base_rate * 0.1  = 0.2 %/s
- RUIM:      0.04x → base_rate * 0.04 = 0.08 %/s

Multiplicadores de desaceleração:
- IDEAL:     2.0x  → base_rate * 2.0  = 4.0 %/s
- SUBÓTIMA:  5.0x  → base_rate * 5.0  = 10.0 %/s
- RUIM:      10.0x → base_rate * 10.0 = 20.0 %/s

base_rate = 50 / (50 * 50) = 0.02 %/frame = 2.0 %/s @ 50Hz
base_acceleration_time = 50s
```

### 1.5 Problemas do Modelo Original

1. **Transições abruptas**: ao cruzar a fronteira entre zonas (ex: PWM vai de 21% para 21.1% na 2ª marcha), o multiplicador salta de 1.0 para 0.1 instantaneamente, causando um "tranco" na aceleração
2. **Manutenção frágil**: 5 blocos if/elif com ~80 linhas de comparações hardcoded; ajustar uma zona requer editar múltiplos pontos
3. **Difícil de modelar**: na monografia, descrever o sistema como "tabela de comparações" é menos elegante do que uma equação

---

## 2. Proposta Intermediária: Gaussiana (DESCARTADA)

> **Status**: Esta proposta foi analisada mas **NÃO foi implementada**. Está documentada aqui como registro histórico do processo de decisão.

### 2.1 Motivação Física

Motores reais possuem curvas de torque/eficiência que se assemelham a distribuições gaussianas: há um ponto ótimo de operação (pico) e a eficiência decai suavemente ao se afastar dele. Ao modelar as zonas de eficiência como gaussianas, obteríamos:

- Transições suaves (sem degraus)
- Comportamento fisicamente plausível
- Equação compacta e citável na monografia

### 2.2 Equação do Multiplicador de Zona (proposta)

```
                    -(PWM - μ(g))²
rate(PWM, g) = exp( ────────────── )
                      2·σ(g)²
```

Onde:
- `μ(g)` = centro da zona ideal da marcha `g`
- `σ(g)` = largura da curva (controla quão rápido a eficiência decai)
- Saída: valor contínuo entre 0 e 1 (piso em 0.04 para nunca parar)

### 2.3 Derivação dos Parâmetros

Os centros `μ(g)` eram calculados como o ponto médio da zona IDEAL original:

```
μ(1) = (6 + 12) / 2   =  9.0
μ(2) = (10 + 21) / 2   = 15.5
μ(3) = (22 + 39) / 2   = 30.5
μ(4) = (40 + 62) / 2   = 51.0
μ(5) = (65 + 90) / 2   = 77.5
```

Os σ(g) seriam calibrados para que `rate ≈ 0.1` nas bordas da zona SUBÓTIMA original (equivale a ~2σ do centro):

```
σ(1) = (12 - 6) / 2   = 3.0
σ(2) = (21 - 10) / 2   = 5.5
σ(3) = (39 - 22) / 2   = 8.5
σ(4) = (62 - 40) / 2   = 11.0
σ(5) = (90 - 65) / 2   = 12.5
```

Verificação: na borda da zona ideal (ex: 2ª marcha, PWM=21):
```
rate(21, 2) = exp(-(21 - 15.5)² / (2 * 5.5²))
            = exp(-30.25 / 60.5)
            = exp(-0.5)
            ≈ 0.607
```
Isso significaria que na borda da zona IDEAL, a eficiência seria ~60% (não 100%), mais realista que o degrau abrupto de 1.0 → 0.1 do modelo original.

### 2.4 Por que a Gaussiana foi descartada

Apesar de elegante, a abordagem gaussiana apresentava problemas práticos:

1. **Tuning difícil**: os parâmetros μ e σ por marcha criavam um espaço de calibração de 10 variáveis (2 por marcha), difícil de ajustar empiricamente no veículo real
2. **Comportamento não-intuitivo**: o decaimento suave dificultava o debug — "qual é o multiplicador atual?" não tinha resposta simples
3. **Não era uma ODE padrão**: a equação `dPWM/dt = rate(PWM,g) * base_rate * sign(target-PWM)` não correspondia a nenhum modelo de controle clássico, dificultando a análise na monografia
4. **Overengineering**: para um sistema embarcado com 5 marchas discretas e zonas bem definidas, a suavidade contínua era desnecessária — o operador troca de marcha manualmente via paddle shifters, e as transições entre zonas são eventos raros

A decisão foi manter zonas discretas (IDEAL/SUBOPTIMAL/POOR) mas reformular a dinâmica como um **sistema de 1ª ordem clássico** com função de transferência.

---

## 3. Modelo Final Implementado: Sistema de 1ª Ordem com G(s) = K/(τs+1)

### 3.1 Insight: a ODE original já era um sistema de 1ª ordem

Ao analisar o código original (Seção 1.3), percebeu-se que a lógica de aceleração já era, essencialmente, uma integração de Euler da ODE de 1ª ordem:

```
Código original:  step = zone_rate * dt * 50 = base_rate * rate_multiplier * dt * 50
Reescrevendo:     dPWM/dt ≈ step/dt = base_rate * rate_multiplier * 50
```

A única diferença era que o `step` era limitado a `pwm_diff` (clamp), e o `rate_multiplier` dependia da zona. Em essência, era uma ODE de 1ª ordem **disfarçada** com coeficientes por partes.

A reformulação tornou isso explícito usando a forma canônica de teoria de controle.

### 3.2 Função de Transferência

O sistema de transmissão é modelado como um sistema de 1ª ordem clássico:

```
         Y(s)       K
G(s) = ────── = ─────────
         U(s)    τ_eff·s + 1
```

Onde:
- `Y(s)` = PWM do motor (saída)
- `U(s)` = entrada (degrau unitário)
- `K` = ganho estático = `target_PWM` = limiter da marcha (throttle 100%)
- `τ_eff` = constante de tempo efetiva (depende da marcha e da zona)

### 3.3 Equação Diferencial (ODE)

A ODE correspondente no domínio do tempo:

```
τ_eff · dy/dt + y = K · u(t)

Reescrevendo:
  dy/dt = (K·u(t) - y) / τ_eff
        = (target - PWM) / τ_eff
```

Implementação no código (`motor.py:395-397`):

```python
# dPWM/dt = (target - PWM) / τ_eff
step = (pwm_diff / tau) * dt      # Integração de Euler
self.current_pwm += step
```

### 3.4 Resposta ao Degrau Unitário

Para entrada degrau u(t) = 1 (throttle instantâneo a 100%):

```
y(t) = K · (1 - e^(-t/τ_eff))
```

Propriedades:
- Em `t = 0`: `y = 0` (motor parado)
- Em `t = τ_eff`: `y = K · (1 - e⁻¹) = 0.632·K` (63.2% do valor final)
- Em `t = 3τ_eff`: `y ≈ 0.95·K` (95% — praticamente convergido)
- Em `t → ∞`: `y → K` (valor final = target)

A derivada (taxa de variação):
```
ẏ(t) = (K/τ_eff) · e^(-t/τ_eff) = (K - y(t)) / τ_eff
```

### 3.5 Constante de Tempo τ_eff

A constante de tempo efetiva combina dois fatores:

```
τ_eff(g, zona) = τ_base(g) × M_zona
```

**τ_base por marcha** — cresce com a marcha (marchas altas = mais "pesadas"):

```
Marcha | τ_base | Significado
-------|--------|------------------------------------------
1ª     |   2s   | Resposta rápida (intervalo PWM curto: 6-16%)
2ª     |   4s   | Moderada
3ª     |   6s   | Intermediária
4ª     |   8s   | Lenta
5ª     |  10s   | Mais lenta (intervalo PWM longo: 64-100%)
```

**Multiplicador por zona** — penaliza marcha errada:

```
Zona       | M_zona | Efeito
-----------|--------|-----------------------------------------------
IDEAL      |   1.0  | τ_eff = τ_base → resposta rápida
SUBOPTIMAL |  10.0  | τ_eff = 10×τ_base → resposta 10× mais lenta
POOR       |  25.0  | τ_eff = 25×τ_base → resposta 25× mais lenta
```

**Tabela completa de τ_eff:**

```
Marcha | τ_base | τ_IDEAL | τ_SUBOPTIMAL | τ_POOR
-------|--------|---------|--------------|--------
1ª     |   2s   |    2s   |     20s      |   50s
2ª     |   4s   |    4s   |     40s      |  100s
3ª     |   6s   |    6s   |     60s      |  150s
4ª     |   8s   |    8s   |     80s      |  200s
5ª     |  10s   |   10s   |    100s      |  250s
```

Exemplo: na 3ª marcha, zona POOR, `τ_eff = 6 × 25 = 150s`. Isso significa que o motor levaria ~150s para atingir 63.2% do target — efetivamente "travado", forçando o operador a trocar para a marcha correta.

### 3.6 Parâmetros por Marcha (GEAR_PARAMS)

```python
GEAR_PARAMS = {
    # gear: (limiter, ideal_low, ideal_high, τ_base)
    1: (16,   6,  12,  2.0),   # K=16%,  ideal  6-12%
    2: (30,  10,  25,  4.0),   # K=30%,  ideal 10-25%
    3: (52,  22,  45,  6.0),   # K=52%,  ideal 22-45%
    4: (78,  40,  70,  8.0),   # K=78%,  ideal 40-70%
    5: (100, 64,  95, 10.0),   # K=100%, ideal 64-95%
}
```

Mudanças em relação ao modelo original (Seção 1):
- **Limitadores expandidos**: 1ª subiu de 12→16%, 2ª de 25→30%, 3ª de 45→52%, 4ª de 70→78% — dá margem para zona SUBOPTIMAL acima do IDEAL
- **Zonas ideais ampliadas**: com sobreposição entre marchas adjacentes (ex: 2ª ideal 10-25% sobrepõe 1ª ideal 6-12% na faixa 10-12%), garantindo que no ponto de troca o PWM já está na zona IDEAL da próxima marcha
- **τ_base introduzido**: substitui o `base_rate` + `rate_multiplier` por uma constante de tempo com significado físico

### 3.7 Classificação de Zonas

A classificação agora usa margem proporcional (25% da largura ideal) em vez de faixas hardcoded:

```python
def _classify_zone(self, current_pwm):
    _, ideal_low, ideal_high, _ = self.GEAR_PARAMS[self.current_gear]
    limiter = self.GEAR_PARAMS[self.current_gear][0]

    ideal_width = ideal_high - ideal_low
    sub_margin = max(ideal_width * 0.25, 2.0)  # mínimo 2%

    sub_low = ideal_low - sub_margin
    sub_high = min(ideal_high + sub_margin, limiter)

    if ideal_low <= current_pwm <= ideal_high:
        return "IDEAL"
    elif sub_low <= current_pwm <= sub_high:
        return "SUBOPTIMAL"
    return "POOR"
```

**Zonas resultantes:**

```
Marcha | Zona Morta | POOR        | SUBOPTIMAL  | IDEAL   | SUBOPTIMAL  | POOR
-------|------------|-------------|-------------|---------|-------------|--------
1ª     | 0-6%       | —           | (4.0-6%)    | 6-12%   | 12-14%      | 14-16%
2ª     | 0-6%       | 6-6.2%      | 6.2-10%     | 10-25%  | 25-28.8%    | 28.8-30%
3ª     | 0-6%       | 6-16.2%     | 16.2-22%    | 22-45%  | 45-50.8%    | 50.8-52%
4ª     | 0-6%       | 6-32.5%     | 32.5-40%    | 40-70%  | 70-77.5%    | 77.5-78%
5ª     | 0-6%       | 6-56.2%     | 56.2-64%    | 64-95%  | 95-100%     | —
```

### 3.8 Desaceleração

Na desaceleração, o sistema usa a mesma ODE mas com τ reduzido para maior responsividade ao soltar o acelerador:

```python
# Desaceleração: τ dividido por 3 (mais responsivo ao soltar)
tau_decel = tau / 3.0

# Freio multiplica a responsividade (0%=1x, 100%=10x)
brake_boost = 1.0 + (self.brake_input / 100.0) * 9.0
tau_decel /= brake_boost
```

Isso mantém a mesma forma de G(s) = K/(τs+1) mas com:
- `τ_decel = τ_eff / 3` → desacelera 3× mais rápido que acelera
- `τ_decel = τ_eff / (3 × brake_boost)` → com freio a 100%, desacelera 30× mais rápido

### 3.9 Zona Morta (0-6%)

Abaixo de 6% PWM o motor não tem torque suficiente para girar. O sistema usa uma rampa rápida linear (40 %/s) para atravessar esta região:

```python
if self.current_pwm < DEAD_ZONE_PWM and self.target_pwm >= DEAD_ZONE_PWM:
    self.current_pwm = min(self.current_pwm + 40.0 * dt, DEAD_ZONE_PWM)
```

Tempo para atravessar: `6% / 40 %/s = 0.15s` (imperceptível).

### 3.10 Conta-giros (Tachometer)

O conta-giros mapeia o PWM atual para 0-100% dentro da zona ideal da marcha:

```python
def _tachometer_percent(self, current_pwm):
    _, ideal_low, ideal_high, _ = self.GEAR_PARAMS[self.current_gear]
    if current_pwm <= ideal_low: return 0.0
    if current_pwm >= ideal_high: return 100.0
    return ((current_pwm - ideal_low) / (ideal_high - ideal_low)) * 100.0
```

Quando tachometer ≥ 95%, é hora de subir de marcha.

---

## 4. Comparação: Original vs. Gaussiana vs. Final

### 4.1 Tabela Comparativa

```
Aspecto              | Original (if/else)     | Gaussiana (descartada) | Final (G(s)=K/(τs+1))
---------------------|------------------------|------------------------|------------------------
Linhas de código     | ~127 (5 blocos if/elif)| ~20 (equações)         | ~50 (ODE + classify)
Transições           | Degrau abrupto         | Suave (contínua)       | Degrau (3 zonas)
Nº de parâmetros     | ~30 (faixas hardcoded) | 10 (μ,σ por marcha)   | 4 por marcha + 3 mult.
Modelo matemático    | Nenhum (tabela)        | Gaussiana + ODE        | G(s)=K/(τs+1) clássico
Citável na monografia| Não (tabela arbitrária)| Sim (equação)          | Sim (teoria de controle)
Debug/tuning         | Visual (log zones)     | Difícil (contínuo)     | Fácil (τ por zona)
Análise Laplace      | Impossível             | Não-linear             | Direta (polo em -1/τ)
Resposta ao degrau   | Implícita              | Não-padrão             | y(t) = K(1-e^(-t/τ))
```

### 4.2 Por que o modelo final é superior

1. **Fundamentação teórica**: G(s) = K/(τs+1) é um sistema de 1ª ordem clássico, amplamente estudado em teoria de controle. Pode ser analisado no domínio de Laplace, tem resposta ao degrau analítica, e o comportamento é completamente determinado por K e τ.

2. **Simplicidade com expressividade**: apenas 4 parâmetros por marcha (limiter, ideal_low, ideal_high, τ_base) + 3 multiplicadores globais controlam todo o comportamento. Muito menos que as ~30 faixas hardcoded do original.

3. **Zonas discretas são suficientes**: o operador troca marchas manualmente via paddle shifters. As transições entre zonas (IDEAL→SUBOPTIMAL→POOR) são eventos infrequentes e discretos por natureza — não necessitam de suavização gaussiana.

4. **Interpretabilidade**: "τ_eff = 6s na zona IDEAL da 3ª marcha" tem significado físico claro — o motor atinge 63.2% do target em 6 segundos. Isso é mais útil para debug do que "rate = 0.607".

### 4.3 Por que NÃO usar ODE de 2ª Ordem

Uma ODE de 2ª ordem (`d²PWM/dt² = K*(target-PWM) - B*(dPWM/dt)`) introduziria:
- Overshoot e oscilação ao redor do target
- Necessidade de tuning de K e B por marcha
- Comportamento oscilatório indesejado em sistema de controle real (PWM oscilando = motor vibrando)

A ODE de 1ª ordem é suficiente: dá convergência monotônica ao target, sem overshoot, e é determinística.

---

## 5. Verificação Numérica

### 5.1 Consistência G(s) ↔ ODE ↔ Resposta ao Degrau

Para a 3ª marcha (K=52%, τ_IDEAL=6s):

```
G(s) = 52 / (6s + 1)

Resposta ao degrau:
  y(t) = 52 · (1 - e^(-t/6))

Derivada:
  ẏ(t) = (52/6) · e^(-t/6) = (52 - y(t)) / 6

Em t=0:  ẏ(0) = 52/6 = 8.67 %/s
Em t=6s: y(6) = 52·(1-e⁻¹) = 52·0.632 = 32.87% → ẏ(6) = (52-32.87)/6 = 3.19 %/s ✓
Em t=18s: y(18) = 52·(1-e⁻³) = 52·0.950 = 49.4% (95% do target) ✓
```

### 5.2 Tempos de Troca de Marcha (simulação throttle 100%)

```
Troca   | Tempo  | PWM     | τ antes → depois
--------|--------|---------|------------------
1ª→2ª   | 1.83s  | 11.71%  | 2s → 4s
2ª→3ª   | 6.46s  | 24.26%  | 4s → 6s
3ª→4ª   | 13.81s | 43.86%  | 6s → 8s
4ª→5ª   | 24.04s | 68.50%  | 8s → 10s
```

A cada troca, o PWM do ponto de troca já está dentro da zona IDEAL da próxima marcha (pela sobreposição dos intervalos), então τ_eff não sofre penalidade de zona.

### 5.3 Campo de Direções: ẏ = (K-y)/τ_eff

Exemplos de taxa de variação para a 3ª marcha (K=52, τ_base=6s):

```
PWM   | Zona       | τ_eff  | ẏ = (52-PWM)/τ_eff
------|------------|--------|--------------------
 6%   | POOR       | 150s   | (52-6)/150  = 0.31 %/s  ← quase parado
16%   | SUBOPTIMAL |  60s   | (52-16)/60  = 0.60 %/s  ← lento
22%   | IDEAL      |   6s   | (52-22)/6   = 5.00 %/s  ← rápido!
34%   | IDEAL      |   6s   | (52-34)/6   = 3.00 %/s
45%   | IDEAL      |   6s   | (52-45)/6   = 1.17 %/s  ← desacelerando (perto do target)
```

A taxa na zona POOR (0.31 %/s) é 16× menor que na zona IDEAL (5.0 %/s), forçando o operador a trocar de marcha para a faixa correta.

---

## 6. Gráficos Gerados

Os gráficos do sistema estão em `monografia/figuras/` e são gerados por `scripts/generate_motor_charts.py`:

| Arquivo | Descrição |
|---------|-----------|
| `zonas_eficiencia_marchas.png` | Zonas por marcha (barras horizontais) |
| `tau_efetivo_marchas.png` | τ_eff vs PWM por marcha (escala log) |
| `resposta_degrau_marchas.png` | y(t) = K(1-e^(-t/τ)) por marcha |
| `simulacao_completa_marchas.png` | Aceleração 1ª→5ª + conta-giros |
| `contagiros_marchas.png` | Mapeamento conta-giros por marcha |
| `tau_detalhado_calculos.png` | τ por marcha com cálculos + G(s) + tabelas |
| `tau_evolucao_simulacao.png` | Evolução temporal de τ na simulação |
| `ode_equacao_diferencial.png` | Decomposição da ODE: y(t), erro, τ, ẏ |
| `ode_campo_direcoes.png` | Campo de direções ẏ = (K-y)/τ por marcha |
