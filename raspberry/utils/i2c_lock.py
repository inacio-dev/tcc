"""Lock I2C com intercalação justa (weighted fair queuing).

Resolve o problema de starvation no barramento I2C compartilhado
entre PCA9685 (servos), BMI160 (IMU) e INA219 (energia).
"""

import threading


class PriorityI2CLock:
    """Lock I2C com intercalação justa (weighted fair queuing).

    Prioridades com peso (turnos consecutivos permitidos):
        0 = Alta  (steering/brake): 3 turnos seguidos
        1 = Média (BMI160):         2 turnos seguidos
        2 = Baixa (INA219):         1 turno seguido

    Após esgotar seus turnos, a prioridade cede vez para as demais.
    Isso evita starvation: BMI160 nunca fica bloqueado indefinidamente.

    Exemplo de intercalação com servo e BMI160 disputando:
        servo → servo → servo → BMI160 → BMI160 → servo → ...
    """

    PRIORITY_HIGH = 0    # Steering, Brake
    PRIORITY_MEDIUM = 1  # BMI160
    PRIORITY_LOW = 2     # INA219

    # Turnos consecutivos antes de ceder vez
    WEIGHT = {0: 3, 1: 2, 2: 1}

    def __init__(self):
        self._lock = threading.Lock()
        self._cond = threading.Condition(self._lock)
        self._waiting = [0, 0, 0]  # Contadores por prioridade
        self._busy = False
        self._run_count = 0   # Acessos consecutivos da mesma prioridade
        self._run_prio = -1   # Última prioridade que executou

    def _can_acquire(self, priority: int) -> bool:
        """Verifica se esta prioridade pode adquirir o lock agora."""
        if self._busy:
            return False

        others_waiting = any(
            self._waiting[p] > 0 for p in range(3) if p != priority
        )

        # Se excedeu peso e outros estão esperando → ceder vez
        if (self._run_prio == priority
                and self._run_count >= self.WEIGHT.get(priority, 1)
                and others_waiting):
            return False

        # Se prioridade maior está esperando e NÃO excedeu seu peso → esperar
        for p in range(priority):
            if self._waiting[p] > 0:
                higher_exceeded = (
                    self._run_prio == p
                    and self._run_count >= self.WEIGHT.get(p, 1)
                )
                if not higher_exceeded:
                    return False

        return True

    def acquire(self, priority: int = 1):
        """Adquire o lock com intercalação justa por peso."""
        with self._cond:
            self._waiting[priority] += 1
            while not self._can_acquire(priority):
                self._cond.wait()
            self._waiting[priority] -= 1
            self._busy = True

            if self._run_prio == priority:
                self._run_count += 1
            else:
                self._run_count = 1
                self._run_prio = priority

    def release(self):
        """Libera o lock e notifica threads esperando."""
        with self._cond:
            self._busy = False
            self._cond.notify_all()
