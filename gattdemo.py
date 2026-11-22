# /// script
# requires-python = ">=3.10"
# dependencies = ["bleak>=0.22"]
# ///
"""Controle de fita de LED BLE que anuncia "GATT--DEMO" (apps MR Star / Lenze Colorful).

Uso (de dentro desta pasta):
  uv run gattdemo.py procurar [segundos]           (acha a fita, confere os serviços, pisca e grava o
                 MAC em fitas.json → "gattdemo"; rodar num terminal)
  uv run gattdemo.py ligar | desligar
  uv run gattdemo.py cor vermelho [brilho 0-100]       (ou um matiz 0-359; "branco" = sem saturação)
  uv run gattdemo.py brilho 60                          (0-100)
  uv run gattdemo.py efeito 55 [velocidade] [brilho]    (0-100 cada; ou pelo nome: efeito água corrente 40 80)
  uv run gattdemo.py efeitos [categoria|texto]          (lista por categoria, como nas abas do app:
                 básico, abrir e fechar, transição, água corrente, à direita, executando;
                 e as que o app esconde: fluxo, extra)
  uv run gattdemo.py velocidade 50                      (velocidade do efeito, 0-100)
  uv run gattdemo.py sentido normal | invertido         (sentido em que o efeito corre; o app manda esse
                 comando, mas o botão pode não aparecer na tela)
  uv run gattdemo.py microfone [estilo] [sensibilidade] (microfone da própria fita; estilos:
                 1 clássico, 2 suave, 3 dinâmico, 4 disco; sensibilidade 0-100)
  uv run gattdemo.py microfone desligar                 (sai do modo microfone)
  uv run gattdemo.py demo [de] [até] [segundos]         (passa pelos efeitos mostrando o nome; Ctrl+C para)
  uv run gattdemo.py demo transição [segundos]          (só uma categoria)
  uv run gattdemo.py temporizador [ver]               (mostra os horários gravados na fita)
  uv run gattdemo.py temporizador liga 18:30 [dias]     (a fita liga sozinha nesse horário;
                 dias: todos, semana, fim ou seg,qua,sex)
  uv run gattdemo.py temporizador desliga 23:00 [dias]  (a fita desliga sozinha nesse horário)
  uv run gattdemo.py temporizador liga|desliga cancelar (desativa aquele horário)
  uv run gattdemo.py relogio                            (acerta o relógio da fita pela hora do notebook)
  uv run gattdemo.py estado                             (o último comando que este script mandou)

Vários comandos de uma vez, numa conexão só, separados por "+":
  uv run gattdemo.py ligar + efeito 55 + velocidade 30 + brilho 80

A fita não devolve estado: "estado" mostra o que este script mandou por último
(guardado em gattdemo-estado.json), não o que o app do celular possa ter mudado.
Protocolo e origem de cada comando: PROTOCOLO-gattdemo-mrstar.md.
Modo música (reagir à música tocando no notebook): não implementado; caminho em PROTOCOLO-gattdemo-mrstar.md,
seção "Música pelo notebook (futuro)".
"""
import asyncio
import json
import os
import sys
import time

from bleak import BleakClient, BleakScanner

CONFIG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fitas.json")  # → "gattdemo": MAC
SERVICO = "0000fff0-0000-1000-8000-00805f9b34fb"
OTA = "5833ff01"  # início do UUID do serviço OTA do chip Lenze ST17H66 (só para reconhecer; nunca escrever)
ANUNCIO_NOME = "GATT--DEMO"
ANUNCIO_SERVICO = "00002022-0000-1000-8000-00805f9b34fb"
ESCRITA = "0000fff3-0000-1000-8000-00805f9b34fb"
NOTIFY = "0000fff4-0000-1000-8000-00805f9b34fb"
# Nunca escrever no serviço 5833ff01 (OTA do chip) nem mandar os comandos de configuração
# 02 (ordem RGB) e 03 (número de LEDs): só mudam se o hardware mudar.

LIGA, DESLIGA = 1, 0  # o app usa 00 com o interruptor marcado; o cheap-leds diz 01 = liga
ESTADO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gattdemo-estado.json")

CORES = {
    "vermelho": 0, "laranja": 25, "amarelo": 55, "verde": 120, "ciano": 180,
    "azul": 240, "roxo": 275, "rosa": 320, "magenta": 300, "branco": None,
}
ESTILOS_MIC = {1: "clássico", 2: "suave", 3: "dinâmico", 4: "disco"}

# id: nome. Traduzido do app; os marcados em APP aparecem nas abas do app.
EFEITOS = {
    1: "ciclo automático", 2: "sinfonia", 3: "energia colorida", 4: "saltos coloridos",
    5: "saltos vermelho-verde-azul", 6: "saltos amarelo-azul-roxo", 7: "estroboscópio 7 cores",
    8: "estroboscópio vermelho-verde-azul", 9: "estroboscópio amarelo-roxo-azul",
    10: "degradê 7 cores", 11: "degradê alternado vermelho-amarelo",
    12: "degradê alternado vermelho-roxo", 13: "degradê alternado verde",
    14: "degradê alternado verde-amarelo", 15: "degradê alternado azul-roxo",
    16: "corrida vermelha", 17: "corrida verde", 18: "corrida azul", 19: "corrida amarela",
    20: "corrida ciano", 21: "corrida roxa", 22: "corrida branca",
    23: "perseguição colorida", 24: "perseguição vermelho-verde-azul",
    25: "perseguição amarelo-ciano-roxo", 26: "tremular colorido",
    27: "tremular vermelho-verde-azul", 28: "tremular amarelo-ciano-roxo",
    29: "pincelada colorida", 30: "pincelada vermelho-verde-azul",
    31: "pincelada amarelo-ciano-roxo", 32: "pincelada colorida abre-fecha",
    33: "pincelada vermelho-verde-azul abre-fecha", 34: "pincelada amarelo-ciano-roxo abre-fecha",
    35: "abre-fecha 7 cores", 36: "abre-fecha vermelho-verde-azul",
    37: "abre-fecha amarelo-ciano-roxo", 38: "abre-fecha vermelho", 39: "abre-fecha verde",
    40: "abre-fecha azul", 41: "abre-fecha amarelo", 42: "abre-fecha ciano", 43: "abre-fecha roxo",
    44: "abre-fecha branco", 45: "claro-escuro 7 cores", 46: "claro-escuro azul-vermelho-verde",
    47: "claro-escuro violeta-verde-amarelo", 48: "claro-escuro 6 cores vermelho",
    49: "claro-escuro 6 cores verde", 50: "claro-escuro 6 cores azul",
    51: "claro-escuro 6 cores ciano", 52: "claro-escuro 6 cores amarelo",
    53: "claro-escuro 6 cores roxo", 54: "claro-escuro 6 cores branco",
    55: "água corrente 7 cores", 56: "água corrente azul-verde-vermelho",
    57: "água corrente roxo-verde-amarelo", 58: "água corrente vermelho-verde",
    59: "água corrente verde-azul", 60: "água corrente amarelo-azul",
    61: "água corrente amarelo-ciano", 62: "água corrente azul-roxo",
    63: "água corrente preto-branco", 64: "fluxo branco-vermelho-branco",
    65: "fluxo branco-verde-branco", 66: "fluxo branco-azul-branco",
    67: "fluxo branco-amarelo-branco", 68: "fluxo branco-verde-branco (2)",
    69: "fluxo branco-roxo-branco", 70: "fluxo vermelho-branco-vermelho",
    71: "fluxo verde-branco-verde", 72: "fluxo azul-branco-azul",
    73: "fluxo amarelo-branco-amarelo", 74: "fluxo azul-branco-azul (2)",
    75: "fluxo roxo-branco-roxo", 76: "rastro 7 cores", 77: "rastro vermelho",
    78: "rastro verde", 79: "rastro azul", 80: "rastro amarelo", 81: "rastro ciano",
    82: "rastro roxo", 83: "rastro branco", 84: "ponto correndo vermelho",
    85: "ponto correndo verde", 86: "ponto correndo azul", 87: "ponto correndo amarelo",
    88: "ponto correndo ciano", 89: "ponto correndo roxo", 90: "ponto correndo branco",
    91: "correndo 7 cores", 92: "correndo azul-verde-vermelho", 93: "correndo roxo-ciano-amarelo",
    94: "correndo azul-roxo-ciano-amarelo", 95: "correndo azul-verde-ciano-amarelo",
    96: "ponto vermelho em fundo branco", 97: "ponto verde em fundo vermelho",
    98: "ponto azul em fundo verde", 99: "ponto amarelo em fundo azul",
    100: "pontos azuis em fundo amarelo", 101: "pontos roxos em fundo azul",
    102: "pontos brancos em fundo roxo", 103: "pontos brancos em fundo vermelho",
    104: "7 cores em fundo vermelho", 105: "7 cores em fundo verde", 106: "7 cores em fundo azul",
    107: "7 cores em fundo amarelo", 108: "7 cores em fundo verde (2)",
    109: "7 cores em fundo roxo", 110: "7 cores em fundo branco",
    111: "ponto verde em fundo azul", 112: "ponto verde em fundo vermelho (2)",
    113: "ponto vermelho em fundo azul", 114: "pontos azuis em fundo amarelo (2)",
    115: "pontos amarelos em fundo roxo", 116: "pontos brancos em fundo amarelo",
    117: "pontos amarelos em fundo branco",
}
# Abas do app (aba "Modos"), na ordem dele. "À direita" é a tradução do app para "Tailing" (rastro).
# A aba "fluxo" (63-75) existe no código, mas o app não mostra.
CATEGORIAS = {
    "básico": [1, 2, 3, 4, 7, 10, 26, 27, 29, 30, 31, 32],
    "abrir e fechar": list(range(35, 45)),
    "transição": list(range(45, 55)),
    "água corrente": list(range(55, 63)),
    "fluxo": list(range(63, 76)),
    "à direita": list(range(76, 84)),
    "executando": list(range(84, 94)),
}
APP = {n for c, ids in CATEGORIAS.items() if c != "fluxo" for n in ids}
DIAS = ["seg", "ter", "qua", "qui", "sex", "sab", "dom"]  # bit 0 = segunda (ordem do app)


def categoria(n: int) -> str:
    return next((c for c, ids in CATEGORIAS.items() if n in ids), "extra (fora do app)")


def achar_categoria(texto: str) -> list[int] | None:
    t = sem_acento(texto.lower())
    for c, ids in CATEGORIAS.items():
        if sem_acento(c).startswith(t):
            return ids
    if "extra".startswith(t):
        return [n for n in EFEITOS if not any(n in ids for ids in CATEGORIAS.values())]
    return None


def sem_acento(t: str) -> str:
    import unicodedata
    return "".join(ch for ch in unicodedata.normalize("NFD", t) if unicodedata.category(ch) != "Mn")


class Erro(Exception):
    pass


def quadro(cmd: int, *dados: int) -> bytes:
    return bytes([0xBC, cmd, len(dados), *dados, 0x55])


def dois(v: int) -> tuple[int, int]:
    return (v >> 8) & 0xFF, v & 0xFF


def pct(texto: str) -> int:
    v = int(texto)
    if not 0 <= v <= 100:
        raise Erro(f"valor fora de 0-100: {v}")
    return v


def achar_efeito(texto: str) -> int:
    if texto.isdigit():
        n = int(texto)
        if n not in EFEITOS:
            raise Erro(f"efeito {n} não existe (1-{max(EFEITOS)})")
        return n
    t = sem_acento(texto.lower())
    achados = [n for n, nome in EFEITOS.items() if t in sem_acento(nome)]
    if not achados:
        raise Erro(f"nenhum efeito com '{texto}' no nome (veja: uv run gattdemo.py efeitos)")
    if len(achados) > 1:
        print(f"vários efeitos com '{texto}'; usando o {achados[0]}. Outros: "
              + ", ".join(map(str, achados[1:])), file=sys.stderr)
    return achados[0]


def ler_estado() -> dict:
    try:
        with open(ESTADO) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def gravar_estado(e: dict):
    e["quando"] = time.strftime("%d/%m %H:%M")
    try:
        with open(ESTADO, "w") as f:
            json.dump(e, f, ensure_ascii=False, indent=1)
    except OSError:
        pass


def montar(acao: str, v: list[str], est: dict) -> list[bytes]:
    """Traduz um comando em quadros e atualiza o estado guardado."""
    if acao == "ligar":
        est["ligada"] = True
        return [quadro(0x01, LIGA)]
    if acao == "desligar":
        est["ligada"] = False
        return [quadro(0x01, DESLIGA)]
    if acao == "cor":
        if not v:
            raise Erro("Informe a cor: " + ", ".join(CORES) + " ou um matiz 0-359")
        c = v[0].lower()
        if c in CORES:
            h, s = (0, 0) if CORES[c] is None else (CORES[c], 1000)
        else:
            h, s = int(c) % 360, 1000
        q = [quadro(0x01, LIGA), quadro(0x04, *dois(h), *dois(s), 0, 0)]
        est.update(ligada=True, modo=f"cor {c}")
        if len(v) > 1:
            q += montar("brilho", v[1:], est)
        return q
    if acao == "brilho":
        b = pct(v[0])
        est["brilho"] = b
        return [quadro(0x05, *dois(max(b * 10, 3)), 0, 0, 0, 0)]  # o app nunca manda abaixo de 3
    if acao == "efeito":
        if not v:
            raise Erro("Informe o efeito (número ou parte do nome). Lista: uv run gattdemo.py efeitos")
        # efeito <número ou nome> [velocidade] [brilho], como a tela "Modos" do app
        nums = []
        while len(v) > 1 and v[-1].isdigit() and len(nums) < 2:
            nums.insert(0, v.pop())
        n = achar_efeito(" ".join(v))  # aceita nome com espaços: efeito água corrente vermelho
        est.update(ligada=True, modo=f"efeito {n} ({EFEITOS[n]})")
        q = [quadro(0x01, LIGA), quadro(0x06, *dois(n))]
        if nums:
            q += montar("velocidade", nums[:1], est)
        if len(nums) > 1:
            q += montar("brilho", nums[1:], est)
        return q
    if acao == "velocidade":
        s = pct(v[0])
        est["velocidade"] = s
        return [quadro(0x08, s)]
    if acao == "sentido":
        inv = bool(v) and v[0].lower().startswith("inv")
        est["sentido"] = "invertido" if inv else "normal"
        return [quadro(0x07, 1 if inv else 0)]
    if acao == "microfone":
        if v and v[0].lower() in ("desligar", "off", "sair"):
            est["modo"] = "microfone desligado"
            return [quadro(0x0F, 0)]
        estilo = int(v[0]) if v else 1
        if estilo not in ESTILOS_MIC:
            raise Erro("estilos: " + ", ".join(f"{k} {n}" for k, n in ESTILOS_MIC.items()))
        q = [quadro(0x01, LIGA), quadro(0x0F, 1), quadro(0x11, estilo)]
        modo = f"microfone, estilo {estilo} ({ESTILOS_MIC[estilo]})"
        if len(v) > 1:
            q.append(quadro(0x12, pct(v[1])))
            modo += f", sensibilidade {v[1]}"
        est.update(ligada=True, modo=modo)
        return q
    if acao == "temporizador":
        # BC 0D 06 01 a e dias h m 55: a = 1 acender / 0 apagar; e = 1 ativo; dias: bit 0 = segunda.
        # O bit 7 dos dias é o inverso de "ativo" (o app faz assim). Acerta o relógio antes.
        qual = {"liga": "liga", "ligar": "liga", "acender": "liga",
                "desliga": "desliga", "desligar": "desliga", "apagar": "desliga"}.get(v[0] if v else "")
        if len(v) < 2 or not qual:
            raise Erro("uso: temporizador liga|desliga HH:MM [dias] | temporizador liga|desliga cancelar")
        a = 1 if qual == "liga" else 0
        if v[1] in ("cancelar", "off", "nao", "não"):
            est.setdefault("temporizador", {})[qual] = "cancelado"
            return [quadro(0x0D, 1, a, 0, 0x80, 0, 0)]
        h, m = (int(x) for x in v[1].split(":"))
        dias = parse_dias(v[2:])
        bits = sum(1 << i for i in dias)
        est.setdefault("temporizador", {})[qual] = f"{h:02}:{m:02} " + ",".join(DIAS[i] for i in dias)
        return montar("relogio", [], est) + [quadro(0x0D, 1, a, 1, bits, h, m)]
    if acao == "relogio":
        t = time.localtime()
        return [quadro(0x0B, *dois(t.tm_year), t.tm_mon, t.tm_mday, t.tm_hour, t.tm_min, t.tm_sec)]
    raise Erro(f"comando desconhecido: {acao}\n" + __doc__)


def parse_dias(v: list[str]) -> list[int]:
    """'todos' (padrão), 'semana' (seg-sex), 'fim' (sáb e dom) ou lista: seg,qua,sex."""
    t = sem_acento(" ".join(v).lower().replace(" ", ","))
    if not t or t.startswith("todo"):
        return list(range(7))
    if t.startswith("semana") or t == "uteis":
        return list(range(5))
    if t.startswith("fim"):
        return [5, 6]
    dias = []
    for d in t.split(","):
        if d[:3] not in DIAS:
            raise Erro(f"dia desconhecido: {d} (use seg ter qua qui sex sab dom, todos, semana, fim)")
        dias.append(DIAS.index(d[:3]))
    return sorted(set(dias))


def mac_configurado() -> str:
    try:
        with open(CONFIG) as f:
            mac = json.load(f).get("gattdemo", "")
    except (OSError, ValueError):
        mac = ""
    if not mac:
        raise Erro("Fita não configurada. Rode: uv run gattdemo.py procurar")
    return mac


def gravar_mac(mac: str):
    try:
        with open(CONFIG) as f:
            tudo = json.load(f)
    except (OSError, ValueError):
        tudo = {}
    tudo["gattdemo"] = mac
    with open(CONFIG, "w") as f:
        json.dump(tudo, f, indent=1, ensure_ascii=False)


async def procurar(segundos: float):
    """Acha candidatas pelo anúncio e confere pelos serviços. O nome "GATT--DEMO" é o padrão do
    módulo BLE barato e aparece em vários produtos; o que identifica ESTA família é o conjunto:
    anúncio do serviço 0x2022 + serviço fff0 com fff3 (escrita) e fff4 (notify) + OTA 5833ff01.
    Mesmo assim, a prova final é fazer a fita piscar."""
    print(f"Procurando por {segundos:g} s (a fita não pode estar conectada ao celular)...", flush=True)
    achados = await BleakScanner.discover(timeout=segundos, return_adv=True)
    cand = []
    for d, adv in achados.values():
        nome = adv.local_name or d.name or ""
        uuids = [u.lower() for u in adv.service_uuids]
        if nome == ANUNCIO_NOME or ANUNCIO_SERVICO in uuids:
            cand.append((d, nome, adv.rssi, ANUNCIO_SERVICO in uuids))
    if not cand:
        raise Erro("Nenhuma candidata. A fita está na tomada? Feche o app do celular e tente de novo.")
    conferidas = []
    for d, nome, rssi, tem2022 in sorted(cand, key=lambda x: -x[2]):
        print(f"  {d.address}  {nome or '(sem nome)':12} {rssi:4} dBm  anúncio 0x2022: "
              f"{'sim' if tem2022 else 'não'}", flush=True)
        try:
            async with BleakClient(d, timeout=20) as c:
                srv = {s.uuid.lower() for s in c.services}
                chars = {ch.uuid.lower() for s in c.services for ch in s.characteristics}
            ok = SERVICO in srv and ESCRITA in chars and NOTIFY in chars
            tem_ota = any(u.startswith(OTA) for u in srv)
            print(f"    serviços: fff0 {'sim' if SERVICO in srv else 'não'}, fff3/fff4 "
                  f"{'sim' if ESCRITA in chars and NOTIFY in chars else 'não'}, OTA 5833ff01 "
                  f"{'sim' if tem_ota else 'não'} → {'confere' if ok else 'NÃO é desta família'}")
            if ok:
                conferidas.append(d.address)
        except Exception as e:
            print(f"    não consegui conectar para conferir ({type(e).__name__})")
    return conferidas


class Fita:
    def __init__(self, mac: str | None = None):
        self.mac = mac or mac_configurado()
        self.c: BleakClient | None = None
        self.com_resposta = False

    async def conectar(self, tentativas: int = 4):
        for t in range(tentativas):
            try:
                dev = await BleakScanner.find_device_by_address(self.mac, timeout=12)
                if not dev:
                    print(f"  fita GATT--DEMO não apareceu (tentativa {t + 1}); está ligada na tomada? "
                          "o celular está conectado nela?", file=sys.stderr)
                    continue
                c = BleakClient(dev, timeout=20)
                await c.connect()
                props = c.services.get_characteristic(ESCRITA).properties
                self.com_resposta = "write-without-response" not in props
                self.c = c
                self.recebidos: list[bytes] = []
                try:
                    await c.start_notify(NOTIFY, lambda _, d: self.recebidos.append(bytes(d)))
                except Exception:
                    pass
                return
            except Exception as e:
                print(f"  tentativa {t + 1} falhou ({type(e).__name__}: {e})", file=sys.stderr)
                await asyncio.sleep(2)
        raise Erro("Não consegui conectar na fita GATT--DEMO.")

    async def enviar(self, quadros: list[bytes]):
        for q in quadros:
            await self.c.write_gatt_char(ESCRITA, q, response=self.com_resposta)
            await asyncio.sleep(0.08)  # o app espera a confirmação de cada quadro; damos folga

    async def fechar(self):
        if self.c:
            try:
                await asyncio.sleep(0.3)
                await self.c.disconnect()
            except Exception:
                pass


def listar(filtro: str = ""):
    ids = achar_categoria(filtro) if filtro else None
    if ids is None:
        f = sem_acento(filtro.lower())
        ids = [n for n, nome in EFEITOS.items() if f in sem_acento(nome)]
    atual = None
    for n in ids:
        c = categoria(n)
        if c != atual:
            print(f"\n{c.upper()}" + ("   (aba que o app não mostra)" if c == "fluxo" else ""))
            atual = c
        print(f"{n:4}  {EFEITOS[n]}")


async def demo(fita: Fita, v: list[str], est: dict):
    seg = float(v.pop()) if v and v[-1].replace(".", "").isdigit() and \
        (len(v) == 3 or not v[0].isdigit()) else 8
    if v and not v[0].isdigit():
        ids = achar_categoria(" ".join(v))
        if ids is None:
            raise Erro("categorias: " + ", ".join(CATEGORIAS) + ", extra")
    else:
        de = int(v[0]) if v else 1
        ate = int(v[1]) if len(v) > 1 else max(EFEITOS)
        ids = [n for n in range(de, ate + 1) if n in EFEITOS]
    await fita.enviar([quadro(0x01, LIGA)])
    try:
        for n in ids:
            print(f"{n:4}  {EFEITOS[n]}  [{categoria(n)}]", flush=True)
            await fita.enviar([quadro(0x06, *dois(n))])
            est.update(ligada=True, modo=f"efeito {n} ({EFEITOS[n]})")
            await asyncio.sleep(seg)
    except asyncio.CancelledError:
        pass


async def principal(args: list[str]):
    if not args or args[0] in ("-h", "--help", "ajuda"):
        print(__doc__)
        return
    comandos = []
    atual: list[str] = []
    for a in args:
        if a == "+":
            comandos.append(atual)
            atual = []
        else:
            atual.append(a)
    comandos.append(atual)
    comandos = [c for c in comandos if c]

    est = ler_estado()
    if comandos[0][0] == "procurar":
        seg = float(comandos[0][1]) if len(comandos[0]) > 1 else 20
        macs = await procurar(seg)
        if not macs:
            raise Erro("Nenhuma candidata conferiu.")
        for mac in macs:
            print(f"→ piscando {mac} (vermelho / azul, 3 vezes)...", flush=True)
            f = Fita(mac)
            await f.conectar(2)
            try:
                for _ in range(3):
                    await f.enviar([quadro(0x01, LIGA), quadro(0x04, 0, 0, *dois(1000), 0, 0)])
                    await asyncio.sleep(0.7)
                    await f.enviar([quadro(0x04, *dois(240), *dois(1000), 0, 0)])
                    await asyncio.sleep(0.7)
            finally:
                await f.fechar()
            if not sys.stdin.isatty():
                print("  (rode num terminal para confirmar e gravar)")
                continue
            if input("  Foi esta que piscou? [s/N] ").strip().lower().startswith("s"):
                gravar_mac(mac)
                print(f"  gravado em {CONFIG} → gattdemo. (A fita ficou azul; ela não informa o estado"
                      " anterior para eu devolver.)")
                return
        return
    if comandos[0][0] == "efeitos":
        listar(" ".join(comandos[0][1:]))
        return
    if comandos[0][0] == "temporizador" and comandos[0][1:2] in ([], ["ver"]):
        fita = Fita()
        await fita.conectar()
        try:
            await fita.enviar([quadro(0x0C, 1)])  # consulta (o app manda isso ao abrir a tela)
            await asyncio.sleep(2)
            achou = False
            for r in fita.recebidos:
                if len(r) >= 9 and r[0] == 0xBC and r[1] == 0x0D:
                    achou = True
                    dias = ",".join(DIAS[i] for i in range(7) if r[6] >> i & 1) or "nenhum dia"
                    print(f"{'liga' if r[4] else 'desliga':8} {'ativo' if r[5] else 'inativo':8} "
                          f"{r[7]:02}:{r[8]:02}  {dias}")
            if not achou:
                print("a fita não respondeu. Recebido: " + (" ".join(x.hex() for x in fita.recebidos) or "nada"))
        finally:
            await fita.fechar()
        return
    if comandos[0][0] == "estado":
        print(json.dumps(est, ensure_ascii=False, indent=1) if est else "nada enviado ainda")
        return
    # monta tudo antes de conectar, para erro de digitação não custar uma conexão
    quadros = [montar(c[0], c[1:], est) for c in comandos if c[0] != "demo"]
    fita = Fita()
    await fita.conectar()
    try:
        for c, q in zip([c for c in comandos if c[0] != "demo"], quadros):
            await fita.enviar(q)
        for c in comandos:
            if c[0] == "demo":
                await demo(fita, c[1:], est)
        gravar_estado(est)
        print("ok")
    finally:
        await fita.fechar()


def main():
    import signal
    try:
        loop = asyncio.new_event_loop()
        tarefa = loop.create_task(principal(sys.argv[1:]))
        loop.add_signal_handler(signal.SIGTERM, tarefa.cancel)
        loop.add_signal_handler(signal.SIGINT, tarefa.cancel)
        loop.run_until_complete(tarefa)
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
    except Erro as e:
        sys.exit(str(e))


if __name__ == "__main__":
    main()
