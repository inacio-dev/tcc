#!/usr/bin/env python3
"""
test_g923.py - Script de teste do Logitech G923

Testa detecção, leitura de eixos/botões e force feedback do G923 via evdev.

Uso:
    python3 test_g923.py

Setup necessário (ver requirements.txt):
    1. sudo usb_modeswitch -v 046d -p c26d -M 0f00010142 -C 0x03 -m 01 -r 81
    2. sudo usermod -a -G input $USER  (requer re-login)

Log:
    Todos os prints são salvos em client/tests/test_g923.log
"""

import builtins
import datetime
import os
import sys
import time

try:
    import evdev
    from evdev import InputDevice, ecodes, ff
except ImportError:
    print("ERRO: módulo 'evdev' não instalado")
    print("  pip install evdev")
    sys.exit(1)


# ================================================================
# LOGGING: tee para terminal + arquivo
# ================================================================

_log_file = None
_original_print = builtins.print
_original_input = builtins.input


def _setup_logging():
    """Abre arquivo de log e substitui print/input para duplicar saída"""
    global _log_file
    log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_g923.log")
    _log_file = open(log_path, "w", encoding="utf-8")
    _log_file.write(f"=== test_g923.py - {datetime.datetime.now().isoformat()} ===\n\n")
    builtins.print = _tee_print
    builtins.input = _tee_input


def _close_logging():
    """Restaura print/input e fecha arquivo de log"""
    global _log_file
    builtins.print = _original_print
    builtins.input = _original_input
    if _log_file:
        _log_file.close()
        _log_file = None


def _tee_print(*args, **kwargs):
    """Print que escreve no terminal E no arquivo de log"""
    _original_print(*args, **kwargs)
    if _log_file:
        # Converte para string como print faria
        sep = kwargs.get("sep", " ")
        end = kwargs.get("end", "\n")
        text = sep.join(str(a) for a in args) + end
        _log_file.write(text)
        _log_file.flush()


def _tee_input(prompt=""):
    """Input que loga o prompt e a resposta do usuário"""
    if _log_file and prompt:
        _log_file.write(prompt)
        _log_file.flush()
    result = _original_input(prompt)
    if _log_file:
        _log_file.write(result + "\n")
        _log_file.flush()
    return result


# ================================================================
# TESTES
# ================================================================


def find_g923():
    """Busca o G923 nos dispositivos de input"""
    print("=" * 60)
    print("TESTE 1: Detecção do G923")
    print("=" * 60)

    devices = [InputDevice(path) for path in evdev.list_devices()]

    if not devices:
        print("FALHA: Nenhum dispositivo de input encontrado")
        print("  - Verifique se está no grupo 'input': groups $USER")
        print("  - Rode: sudo usermod -a -G input $USER")
        return None

    print(f"\nDispositivos encontrados ({len(devices)}):")
    g923 = None

    for dev in devices:
        name = dev.name
        is_g923 = any(
            n.lower() in name.lower()
            for n in ["G923", "Driving Force", "Logitech G923"]
        )
        marker = " <<<< G923" if is_g923 else ""
        print(f"  {dev.path}: {name}{marker}")

        if is_g923 and g923 is None:
            caps = dev.capabilities()
            if ecodes.EV_ABS in caps:
                g923 = dev
            else:
                dev.close()
        else:
            dev.close()

    if g923:
        print(f"\nOK: G923 encontrado em {g923.path}")
        print(f"    Nome: {g923.name}")
    else:
        print("\nFALHA: G923 não encontrado")
        print("  - Verifique se o volante está plugado via USB")
        print("  - Rode: sudo usb_modeswitch -v 046d -p c26d -M 0f00010142 -C 0x03 -m 01 -r 81")

    return g923


def test_capabilities(dev):
    """Mostra capabilities do dispositivo"""
    print("\n" + "=" * 60)
    print("TESTE 2: Capabilities")
    print("=" * 60)

    caps = dev.capabilities(verbose=True)

    # Eixos (EV_ABS)
    abs_caps = dev.capabilities().get(ecodes.EV_ABS, [])
    print(f"\nEixos (EV_ABS): {len(abs_caps)} encontrados")
    for code, info in abs_caps:
        name = ecodes.ABS.get(code, f"ABS_{code}")
        role = ""
        if code == ecodes.ABS_X:
            role = " → STEERING"
        elif code == ecodes.ABS_Y:
            role = " → THROTTLE (acelerador)"
        elif code == ecodes.ABS_Z:
            role = " → BRAKE"
        elif code == ecodes.ABS_RZ:
            role = " → (não usado nesta versão)"
        print(f"  {name} (code={code}): min={info.min}, max={info.max}, "
              f"flat={info.flat}, fuzz={info.fuzz}{role}")

    # Botões (EV_KEY)
    key_caps = dev.capabilities().get(ecodes.EV_KEY, [])
    print(f"\nBotões (EV_KEY): {len(key_caps)} encontrados")
    for code in key_caps:
        name = ecodes.KEY.get(code, ecodes.BTN.get(code, f"BTN_{code}"))
        role = ""
        if code == 292:
            role = " → GEAR_UP (paddle direito)"
        elif code == 293:
            role = " → GEAR_DOWN (paddle esquerdo)"
        print(f"  {name} (code={code}){role}")

    # Force Feedback (EV_FF)
    ff_caps = dev.capabilities().get(ecodes.EV_FF, [])
    has_ff = len(ff_caps) > 0
    print(f"\nForce Feedback (EV_FF): {len(ff_caps)} efeitos")
    for code in ff_caps:
        name = ecodes.FF.get(code, f"FF_{code}")
        marker = " <<<< USADO" if code == ecodes.FF_CONSTANT else ""
        print(f"  {name} (code={code}){marker}")

    if has_ff:
        print("\nOK: Force feedback disponível")
    else:
        print("\nAVISO: Force feedback NÃO disponível")

    return has_ff


def test_input_reading(dev):
    """Lê inputs em tempo real por alguns segundos"""
    print("\n" + "=" * 60)
    print("TESTE 3: Leitura de inputs em tempo real")
    print("=" * 60)
    print("\nMova o volante, pise nos pedais e aperte botões.")
    print("O teste dura 15 segundos. Pressione Ctrl+C para sair.\n")

    steer_min = 999999
    steer_max = -999999
    throttle_min = 999999
    throttle_max = -999999
    brake_min = 999999
    brake_max = -999999
    buttons_pressed = set()

    start = time.time()
    duration = 15

    try:
        while time.time() - start < duration:
            event = dev.read_one()
            if event is None:
                time.sleep(0.001)
                continue

            elapsed = time.time() - start

            if event.type == ecodes.EV_ABS:
                code = event.code
                val = event.value

                if code == ecodes.ABS_X:
                    steer_min = min(steer_min, val)
                    steer_max = max(steer_max, val)
                    print(f"  [{elapsed:5.1f}s] STEERING: {val} "
                          f"(range visto: {steer_min}-{steer_max})")
                elif code == ecodes.ABS_Y:
                    throttle_min = min(throttle_min, val)
                    throttle_max = max(throttle_max, val)
                    print(f"  [{elapsed:5.1f}s] THROTTLE: {val} "
                          f"(range visto: {throttle_min}-{throttle_max})")
                elif code == ecodes.ABS_Z:
                    brake_min = min(brake_min, val)
                    brake_max = max(brake_max, val)
                    print(f"  [{elapsed:5.1f}s] BRAKE:    {val} "
                          f"(range visto: {brake_min}-{brake_max})")
                elif code == ecodes.ABS_RZ:
                    print(f"  [{elapsed:5.1f}s] ABS_RZ:   {val} (não usado)")

            elif event.type == ecodes.EV_KEY:
                code = event.code
                state = "PRESS" if event.value == 1 else "RELEASE"
                name = ecodes.KEY.get(code, ecodes.BTN.get(code, f"BTN_{code}"))
                buttons_pressed.add((code, name))
                print(f"  [{elapsed:5.1f}s] BUTTON:   {name} (code={code}) → {state}")

    except KeyboardInterrupt:
        pass

    print(f"\n--- Resumo ({time.time() - start:.1f}s) ---")
    if steer_max > steer_min:
        print(f"  Steering range: {steer_min} a {steer_max}")
    else:
        print("  Steering: não movido")
    if throttle_max > throttle_min:
        print(f"  Throttle range: {throttle_min} a {throttle_max}")
    else:
        print("  Throttle: não pressionado")
    if brake_max > brake_min:
        print(f"  Brake range: {brake_min} a {brake_max}")
    else:
        print("  Brake: não pressionado")
    if buttons_pressed:
        print(f"  Botões usados: {', '.join(n for _, n in sorted(buttons_pressed))}")
    else:
        print("  Botões: nenhum pressionado")


def test_force_feedback(dev):
    """Testa force feedback com múltiplas abordagens para diagnóstico"""
    print("\n" + "=" * 60)
    print("TESTE 4: Force Feedback (Diagnóstico)")
    print("=" * 60)

    import stat

    # Info do dispositivo
    print(f"\n  Dispositivo: {dev.path}")
    print(f"  Nome: {dev.name}")

    # Verifica permissão de escrita
    try:
        st = os.stat(dev.path)
        mode = st.st_mode
        print(f"  Permissões: {oct(mode)[-3:]} (escrita grupo: {bool(mode & stat.S_IWGRP)})")
        print(f"  fd: {dev.fd}")
    except Exception as e:
        print(f"  Erro ao verificar permissões: {e}")

    # Verifica driver do kernel
    try:
        # Busca o driver do dispositivo
        event_name = os.path.basename(dev.path)
        driver_path = f"/sys/class/input/{event_name}/device/driver"
        if os.path.islink(driver_path):
            driver = os.path.basename(os.readlink(driver_path))
            print(f"  Driver kernel: {driver}")
        else:
            print(f"  Driver kernel: (não encontrado em {driver_path})")
    except Exception as e:
        print(f"  Driver kernel: erro - {e}")

    # Lista efeitos FF suportados
    ff_caps = dev.capabilities().get(ecodes.EV_FF, [])
    ff_names = []
    for code in ff_caps:
        name = ecodes.FF.get(code, f"FF_{code}")
        if isinstance(name, tuple):
            name = name[0]
        ff_names.append((code, name))
    print(f"  Efeitos FF: {', '.join(n for _, n in ff_names)}")

    print("\nSegure o volante! Testando múltiplas abordagens...\n")
    time.sleep(1)

    def run_ff_test(label, setup_fn, description):
        """Executa um teste FF individual com Enter para continuar"""
        print(f"\n  [{label}] {description}")
        effect_id = -1
        try:
            effect_id = setup_fn()
            input("      >>> Pressione ENTER para parar e ir ao próximo teste...")
        except Exception as e:
            print(f"      ERRO: {e}")
        finally:
            if effect_id >= 0:
                try:
                    dev.write(ecodes.EV_FF, effect_id, 0)
                    dev.erase_effect(effect_id)
                except Exception:
                    pass
        return effect_id >= 0

    results = {}

    # ---- TESTE A: FF_AUTOCENTER ----
    def test_a():
        dev.write(ecodes.EV_FF, ecodes.FF_AUTOCENTER, 0xFFFF)
        print("      Ativo! Tente mover o volante - deve resistir ao centro")
        return 0  # sem effect_id, retorna dummy
    results["A"] = run_ff_test("A", test_a, "FF_AUTOCENTER (centralização)")
    try:
        dev.write(ecodes.EV_FF, ecodes.FF_AUTOCENTER, 0)
    except Exception:
        pass

    # ---- TESTE B: FF_GAIN ----
    print("\n  [B] FF_GAIN (ganho global)")
    try:
        dev.write(ecodes.EV_FF, ecodes.FF_GAIN, 0xFFFF)
        print("      FF_GAIN=0xFFFF (100%) - aplicado para os próximos testes")
        results["B"] = True
    except Exception as e:
        print(f"      ERRO: {e}")
        results["B"] = False

    # ---- TESTE C: FF_CONSTANT direita (8%) ----
    def test_c():
        level = int(32767 * 0.08)  # 8% = 2621
        eff = ff.Effect(
            ecodes.FF_CONSTANT, -1, 0xC000,
            ff.Trigger(0, 0), ff.Replay(0xFFFF, 0),
            ff.EffectType(ff_constant_effect=ff.Constant(level, ff.Envelope(0, 0, 0, 0))),
        )
        eid = dev.upload_effect(eff)
        dev.write(ecodes.EV_FF, eid, 1)
        print(f"      Ativo (id={eid})! Deve puxar para a DIREITA (8%, level={level})")
        return eid
    results["C"] = run_ff_test("C", test_c, "FF_CONSTANT direita (8%)")

    # ---- TESTE D: FF_CONSTANT esquerda (8%) ----
    def test_d():
        level = int(32767 * 0.08)  # 8% = 2621
        eff = ff.Effect(
            ecodes.FF_CONSTANT, -1, 0x4000,
            ff.Trigger(0, 0), ff.Replay(0xFFFF, 0),
            ff.EffectType(ff_constant_effect=ff.Constant(level, ff.Envelope(0, 0, 0, 0))),
        )
        eid = dev.upload_effect(eff)
        dev.write(ecodes.EV_FF, eid, 1)
        print(f"      Ativo (id={eid})! Deve puxar para a ESQUERDA (8%, level={level})")
        return eid
    results["D"] = run_ff_test("D", test_d, "FF_CONSTANT esquerda (8%)")

    # ---- TESTE D2: FF_CONSTANT direita (15%) ----
    def test_d2():
        level = int(32767 * 0.15)  # 15% = 4915
        eff = ff.Effect(
            ecodes.FF_CONSTANT, -1, 0xC000,
            ff.Trigger(0, 0), ff.Replay(0xFFFF, 0),
            ff.EffectType(ff_constant_effect=ff.Constant(level, ff.Envelope(0, 0, 0, 0))),
        )
        eid = dev.upload_effect(eff)
        dev.write(ecodes.EV_FF, eid, 1)
        print(f"      Ativo (id={eid})! Força MODERADA para a DIREITA (15%, level={level})")
        return eid
    results["D2"] = run_ff_test("D2", test_d2, "FF_CONSTANT direita (15%)")

    # ---- TESTE D3: FF_CONSTANT direita (30%) ----
    def test_d3():
        level = int(32767 * 0.30)  # 30% = 9830
        eff = ff.Effect(
            ecodes.FF_CONSTANT, -1, 0xC000,
            ff.Trigger(0, 0), ff.Replay(0xFFFF, 0),
            ff.EffectType(ff_constant_effect=ff.Constant(level, ff.Envelope(0, 0, 0, 0))),
        )
        eid = dev.upload_effect(eff)
        dev.write(ecodes.EV_FF, eid, 1)
        print(f"      Ativo (id={eid})! Força FORTE para a DIREITA (30%, level={level})")
        return eid
    results["D3"] = run_ff_test("D3", test_d3, "FF_CONSTANT direita (30%) - CUIDADO")

    # ---- TESTE E: FF_SPRING ----
    def test_e():
        cond = (ff.Condition * 2)(
            ff.Condition(32767, 32767, 16384, 16384, 0, 0),
            ff.Condition(0, 0, 0, 0, 0, 0),
        )
        eff = ff.Effect(
            ecodes.FF_SPRING, -1, 0,
            ff.Trigger(0, 0), ff.Replay(0xFFFF, 0),
            ff.EffectType(ff_condition_effect=cond),
        )
        eid = dev.upload_effect(eff)
        dev.write(ecodes.EV_FF, eid, 1)
        print(f"      Ativo (id={eid})! Mova o volante - deve ter resistência elástica")
        return eid
    results["E"] = run_ff_test("E", test_e, "FF_SPRING (mola de centralização)")

    # ---- TESTE F: FF_DAMPER ----
    def test_f():
        cond = (ff.Condition * 2)(
            ff.Condition(32767, 32767, 32767, 32767, 0, 0),
            ff.Condition(0, 0, 0, 0, 0, 0),
        )
        eff = ff.Effect(
            ecodes.FF_DAMPER, -1, 0,
            ff.Trigger(0, 0), ff.Replay(0xFFFF, 0),
            ff.EffectType(ff_condition_effect=cond),
        )
        eid = dev.upload_effect(eff)
        dev.write(ecodes.EV_FF, eid, 1)
        print(f"      Ativo (id={eid})! Mova o volante - deve ter peso/amortecimento")
        return eid
    results["F"] = run_ff_test("F", test_f, "FF_DAMPER (amortecimento)")

    # ---- TESTE G: FF_PERIODIC ----
    def test_g():
        eff = ff.Effect(
            ecodes.FF_PERIODIC, -1, 0,
            ff.Trigger(0, 0), ff.Replay(0xFFFF, 0),
            ff.EffectType(
                ff_periodic_effect=ff.Periodic(
                    ecodes.FF_SINE, 9830, 0, 0, 500,
                    ff.Envelope(0, 0, 0, 0),
                )
            ),
        )
        eid = dev.upload_effect(eff)
        dev.write(ecodes.EV_FF, eid, 1)
        print(f"      Ativo (id={eid})! Deve vibrar a 2Hz")
        return eid
    results["G"] = run_ff_test("G", test_g, "FF_PERIODIC FF_SINE (vibração 2Hz)")

    # ---- TESTE H: FF_RUMBLE ----
    def test_h():
        eff = ff.Effect(
            ecodes.FF_RUMBLE, -1, 0,
            ff.Trigger(0, 0), ff.Replay(0xFFFF, 0),
            ff.EffectType(
                ff_rumble_effect=ff.Rumble(32767, 32767)
            ),
        )
        eid = dev.upload_effect(eff)
        dev.write(ecodes.EV_FF, eid, 1)
        print(f"      Ativo (id={eid})! Deve tremer/vibrar")
        return eid
    results["H"] = run_ff_test("H", test_h, "FF_RUMBLE (rumble motor)")

    # Resumo
    print("\n  --- Resumo ---")
    for label, ok in results.items():
        status = "OK" if ok else "FALHOU"
        print(f"      [{label}] {status}")


def main():
    _setup_logging()

    try:
        print()
        print("╔══════════════════════════════════════════════════════════╗")
        print("║         TESTE DO LOGITECH G923 - F1 RC Car             ║")
        print("╚══════════════════════════════════════════════════════════╝")
        print()

        # Teste 1: Detecção
        dev = find_g923()
        if not dev:
            sys.exit(1)

        # Teste 2: Capabilities
        has_ff = test_capabilities(dev)

        # Teste 3: Leitura de inputs
        test_input_reading(dev)

        # Teste 4: Force Feedback
        if has_ff:
            resp = input("\nDeseja testar force feedback? (s/n): ").strip().lower()
            if resp in ("s", "y", "sim", "yes", ""):
                test_force_feedback(dev)
            else:
                print("  Force feedback pulado.")
        else:
            print("\nForce feedback não disponível, pulando teste 4.")

        dev.close()
        print("\n" + "=" * 60)
        print("TESTES CONCLUÍDOS")
        print("=" * 60)

        log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_g923.log")
        print(f"\nLog salvo em: {log_path}")

    finally:
        _close_logging()


if __name__ == "__main__":
    main()
