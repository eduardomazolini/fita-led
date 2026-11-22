# /// script
# requires-python = ">=3.10"
# dependencies = ["tinytuya"]
# ///
"""Fitas da árvore por infravermelho, pelo emissor IR Tuya da sala ("IR Sala").

O IR chega às três fitas ao mesmo tempo, sem conexão Bluetooth: não tem as falhas de conexão
e as três recebem o comando juntas. Precisa que o emissor "enxergue" a árvore (o IR também
pega por reflexo na parede e no teto).

Códigos achados por varredura em 21/11/2026 (NEC, endereço 00, comandos 00-17; ver ir-fitas.json):
  ligar (liga em branco), desligar, vermelho, verde, azul, brilho-25, brilho-50, brilho-100,
  mais / menos (+-10 no brilho; no modo música, na sensibilidade), proximo / anterior (próxima cor,
  efeito ou estilo de música, conforme o modo), musica-1/2/3 (Energia, Ritmo, Rolagem),
  efeito-1/2/3/5/6, modo-efeitos (volta ao efeito 1);
  desligar-1h, desligar-4h, desligar-8h (contagem regressiva; a fita pisca para confirmar).
  Cancelar a contagem: pelo Bluetooth, uv run natal.py desligar-em cancelar.
Também dá para aprender do controle físico, se aparecer:
  uv run ir.py aprender ligar desligar mais-brilho menos-brilho ...
      (para cada nome, aponte o controle das fitas para o emissor e aperte o botão)
  uv run ir.py lista                 (botões aprendidos, com o código NEC quando der para ler)
  uv run ir.py ligar [vezes]         (manda um botão aprendido; "vezes" repete, ex.: brilho)
  uv run ir.py ligar + modo + modo   (vários botões em sequência)
  uv run ir.py cor laranja           (ou um matiz 0-359: vai para a mais próxima das 16 cores do
                 controle, apertando vermelho/verde/azul e depois "proximo" quantas vezes precisar)

Credenciais do emissor: ir-emissor.json nesta pasta (id, ip e chave local; não compartilhar).
Gerado por tuya/chave-emissor.py; rodar de novo se o emissor for reconfigurado no app ou mudar de IP.
Códigos aprendidos: ir-fitas.json nesta pasta.
"""
import json
import sys
import time
from pathlib import Path

from tinytuya.Contrib import IRRemoteControlDevice

PASTA = Path(__file__).parent
CODIGOS = PASTA / "ir-fitas.json"
EMISSOR = PASTA / "ir-emissor.json"  # id, ip e chave local do emissor (arquivo privado, 600)


class Erro(Exception):
    pass


def emissor() -> IRRemoteControlDevice:
    try:
        a = json.loads(EMISSOR.read_text())
    except (OSError, ValueError) as e:
        raise Erro(f"não consegui ler {EMISSOR} ({e})")
    # control_type 1 = emissor antigo (DPs 201/202). Passar fixo evita a detecção pela rede, que falha
    # quando o emissor demora a responder.
    return IRRemoteControlDevice(a["id"], a["ip"], a["key"], version=a.get("versao", 3.3),
                                 control_type=a.get("control_type", 1))


def nec_base64(texto: str) -> str:
    """'nec:EE:CC' (endereço e comando em hex) → código no formato do emissor Tuya."""
    _, end, cmd = texto.split(":")
    end, cmd = int(end, 16), int(cmd, 16)
    p = [9000, 4500]
    for byte in (end, end ^ 0xFF, cmd, cmd ^ 0xFF):
        for i in range(8):
            p += [560, 1690 if byte >> i & 1 else 560]
    p.append(560)
    return IRRemoteControlDevice.pulses_to_base64(p)


def ler() -> dict:
    return json.loads(CODIGOS.read_text()) if CODIGOS.exists() else {}


def nec(codigo: str) -> str:
    """Tenta ler o código como NEC (o protocolo mais comum nesses controles)."""
    if codigo.startswith("nec:"):
        return "NEC endereço {} comando {} (achado na varredura)".format(*codigo.split(":")[1:])
    p = IRRemoteControlDevice.base64_to_pulses(codigo)
    if len(p) < 67 or not (7000 < p[0] < 11000 and 3500 < p[1] < 5500):
        return f"{len(p)} pulsos (não é NEC)"
    bits = 0
    for i in range(32):
        bits |= (1 if p[3 + 2 * i] > 1100 else 0) << i
    end, iend, cmd, icmd = bits & 0xFF, (bits >> 8) & 0xFF, (bits >> 16) & 0xFF, bits >> 24
    ok = "" if cmd ^ icmd == 0xFF else " (inverso do comando não bate)"
    return f"NEC endereço {end:02X}{'' if end ^ iend == 0xFF else f'/{iend:02X}'} comando {cmd:02X}{ok}"


def aprender(nomes: list[str]):
    ir = emissor()
    tudo = ler()
    for nome in nomes:
        print(f"→ aperte '{nome}' no controle das fitas, apontado para o emissor (30 s)...", flush=True)
        codigo = None
        ir.study_end()
        ir.study_start()
        fim = time.time() + 30
        try:
            ir.set_socketTimeout(2)
            while time.time() < fim and not codigo:
                r = ir._send_receive(None)
                dps = r.get("dps", {}) if isinstance(r, dict) else {}
                codigo = dps.get(ir.DP_LEARNED_ID) or dps.get(ir.DP_LEARNED_REPORT)
        finally:
            ir.study_end()
        if not isinstance(codigo, str):
            print(f"  nada capturado para '{nome}'; pulei", flush=True)
            continue
        tudo[nome] = codigo
        CODIGOS.write_text(json.dumps(tudo, indent=1, ensure_ascii=False))
        print(f"  ok: {nec(codigo)}", flush=True)
        time.sleep(1)


# Ciclo do botão "proximo" no modo cor (medido em 21/11/2026): 16 posições, saturação 100%.
# vermelho(0) 15 30 45 amarelo(60) | verde(120) 135 150 165 ciano(180) | azul(240) 255 270 285 300 | branco
PALETA = [0, 15, 30, 45, 60, 120, 135, 150, 165, 180, 240, 255, 270, 285, 300, None]
PONTOS = {0: "vermelho", 5: "verde", 10: "azul"}  # botões diretos e sua posição no ciclo
NOMES_COR = {"vermelho": 0, "laranja": 30, "amarelo": 60, "verde": 120, "ciano": 180, "azul": 240,
             "roxo": 270, "magenta": 300, "rosa": 300, "branco": None}


def passos_cor(texto: str) -> list[list[str]]:
    """Cor por nome ou matiz → botão de cor mais próximo + N vezes 'proximo'."""
    t = texto.lower()
    alvo = NOMES_COR[t] if t in NOMES_COR else int(t) % 360
    if alvo is None:
        return [["ligar"]]
    dist = lambda h: min(abs(h - alvo), 360 - abs(h - alvo))
    pos = min((i for i, h in enumerate(PALETA) if h is not None), key=lambda i: dist(PALETA[i]))
    base = max(p for p in PONTOS if p <= pos)
    return [[PONTOS[base]]] + [["proximo"]] * (pos - base)


def enviar(sequencia: list[list[str]]):
    seq = []
    for c in sequencia:
        seq += passos_cor(c[1]) if c[0] == "cor" and len(c) > 1 else [c]
    sequencia = seq
    tudo = ler()
    for c in sequencia:
        if c[0] not in tudo:
            raise Erro(f"botão '{c[0]}' não aprendido. Aprendidos: {', '.join(tudo) or 'nenhum'}")
    ir = emissor()
    for c in sequencia:
        vezes = int(c[1]) if len(c) > 1 else 1
        for _ in range(vezes):
            cod = tudo[c[0]]
            ir.send_button(nec_base64(cod) if cod.startswith("nec:") else cod)
            time.sleep(0.4)
    print("ok")


def main(args: list[str]):
    if not args or args[0] in ("-h", "--help", "ajuda"):
        print(__doc__)
    elif args[0] == "aprender":
        if len(args) < 2:
            raise Erro("diga os nomes dos botões: uv run ir.py aprender ligar desligar ...")
        aprender(args[1:])
    elif args[0] == "lista":
        tudo = ler()
        if not tudo:
            print("nenhum botão aprendido ainda")
        for n, c in tudo.items():
            print(f"{n:16} {nec(c)}")
    else:
        seq, atual = [], []
        for a in args:
            if a == "+":
                seq.append(atual)
                atual = []
            else:
                atual.append(a)
        seq.append(atual)
        enviar([s for s in seq if s])


if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except Erro as e:
        sys.exit(str(e))
    except KeyboardInterrupt:
        pass
