# /// script
# requires-python = ">=3.10"
# dependencies = ["bleak>=0.22"]
# ///
"""Controle das 3 fitas Hello Fairy da árvore de Natal.

Uso (de dentro desta pasta):
  uv run natal.py ligar
  uv run natal.py desligar
  uv run natal.py cor vermelho [brilho 0-100]     (ou um matiz 0-359)
  uv run natal.py brilho 60
  uv run natal.py efeito 12 [brilho]               (efeitos 1-20; veja cenas/index.html)
  uv run natal.py estado
  uv run natal.py musica [estilo] [sensibilidade 0-100] [cor]   (microfone da própria fita;
                 estilos: 1 energia, 2 ritmo, 3 rolagem, 4 espectro; sensibilidade 85 é boa)
  uv run natal.py desligar-em 2                    (a fita desliga sozinha daqui a 2 h; "cancelar" tira;
                 as teclas IR c08/c09/c0a fazem o mesmo com 1, 4 e 8 h)
  uv run natal.py velocidade 50                    (velocidade dos efeitos internos, 1-100)
  uv run natal.py pausar | continuar               (congela/solta o efeito interno)
  uv run natal.py sequencia [natal|subida|arco-iris|cometa] [--velocidade 1.0] [--brilho 100]
  uv run natal.py parar                            (só com servidor: para a sequência e restaura)
  uv run natal.py liberar [minutos]                (solta as fitas para o app do celular)
  uv run natal.py conectar                         (o servidor volta a pegar as fitas)
  uv run natal.py sincronizar [minutos]            (reinicia o efeito nas três juntas; com minutos,
                 muda o intervalo da sincronia automática do servidor; 0 desliga)

Fitas: os MACs ficam em fitas.json (fora do git; modelo em fitas.json.example), gerado por
  uv run natal.py procurar          (acha as "Hello Fairy-XXXX", pisca cada nova e pergunta o nome)
  uv run natal.py piscar meio       (pisca uma fita para saber qual é)
Opção --fitas escolhe quais fitas: os nomes de fitas.json (ou 1, 2, 3 de baixo para cima),
separados por vírgula (padrão: todas).
Se uma fita estiver sem conexão, o servidor guarda o comando e aplica quando ela reconectar.

Modo servidor (recomendado): conectar nessas fitas falha com frequência, mas depois de
conectadas a ligação é estável. O servidor conecta uma vez, mantém as três conectadas
(reconecta sozinho se cair) e atende os comandos na hora:
  uv run natal.py servidor        (deixe rodando num terminal; Ctrl+C encerra)
Com o servidor rodando, os outros comandos passam por ele automaticamente, e a
sequência roda dentro dele (o comando volta na hora; use "parar" para encerrar).
"liberar" desconecta as três e o servidor para de tentar conectar: sem minutos, até um
"conectar"; com minutos, volta a tentar sozinho depois desse tempo (se o celular ainda
estiver conectado, a fita não aparece e o servidor só a pega quando o celular soltar).
Sem servidor, "liberar" derruba qualquer conexão do notebook com as fitas (bluetoothctl).
Sincronia: cada fita roda o efeito pelo próprio relógio e elas se desencontram com o
tempo. Quando as três estão no mesmo efeito, o servidor reenvia o efeito às três ao mesmo
tempo a cada SINCRONIA_MIN minutos (e logo que uma fita reconecta), e elas recomeçam juntas.
Sem servidor, cada comando conecta, executa e desconecta; a sequência roda até Ctrl+C
e depois devolve as fitas ao estado em que estavam.
"""
import argparse
import asyncio
import json
import os
import sys
import time

from bleak import BleakClient, BleakScanner

CONFIG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fitas.json")


def carregar_fitas() -> dict[str, str]:
    """Fitas da árvore (nome → MAC, de baixo para cima) em fitas.json → "arvore".
    Gerado por `natal.py procurar`; modelo em fitas.json.example."""
    try:
        with open(CONFIG) as f:
            return dict(json.load(f).get("arvore", {}))
    except (OSError, ValueError):
        return {}


def gravar_fitas(fitas: dict[str, str]):
    try:
        with open(CONFIG) as f:
            tudo = json.load(f)
    except (OSError, ValueError):
        tudo = {}
    tudo["arvore"] = fitas
    with open(CONFIG, "w") as f:
        json.dump(tudo, f, indent=1, ensure_ascii=False)


FITAS = carregar_fitas()  # de baixo para cima
NOME_ANUNCIO = "Hello Fairy"  # as fitas anunciam "Hello Fairy-XXXX" (XXXX = fim do MAC)
ESCRITA = "49535343-8841-43f4-a8d4-ecbe34729bb3"
NOTIFY = "49535343-1e4d-4bd9-ba61-23c647249616"

SINCRONIA_MIN = 5  # intervalo padrão da sincronia automática dos efeitos (servidor)

CORES = {
    "vermelho": 0, "laranja": 25, "amarelo": 55, "verde": 120, "ciano": 180,
    "azul": 240, "roxo": 275, "rosa": 320, "magenta": 300, "branco": None,
}


def pacote(*b: int) -> bytes:
    b = bytes(b)
    return b + bytes([sum(b) & 0xFF])


def cmd_hsv(h: int, s: int, v: int) -> bytes:
    """h 0-359, s 0-1000, v 0-1000"""
    h, s, v = int(h) % 360, max(0, min(1000, int(s))), max(0, min(1000, int(v)))
    return pacote(0xAA, 3, 7, 1, h >> 8, h & 255, s >> 8, s & 255, v >> 8, v & 255)


def cmd_efeito(n: int, v: int) -> bytes:
    v = max(0, min(1000, int(v)))
    return pacote(0xAA, 3, 4, 2, n, v >> 8, v & 255)


CMD_LIGAR = pacote(0xAA, 2, 1, 1)
CMD_DESLIGAR = pacote(0xAA, 2, 1, 0)
CMD_ESTADO = pacote(0xAA, 1, 0)
CMD_PAUSAR = pacote(0xAA, 0x11, 1, 1)
CMD_CONTINUAR = pacote(0xAA, 0x11, 1, 0)


def cmd_velocidade(v: int) -> bytes:
    return pacote(0xAA, 0x0C, 1, max(1, min(100, int(v))))


SOCKET = os.path.join(os.environ.get("XDG_RUNTIME_DIR", "/tmp"), "natal-led.sock")


class Fita:
    def __init__(self, nome: str, mac: str):
        self.nome, self.mac = nome, mac
        self.cliente: BleakClient | None = None
        self.estado: bytes | None = None
        self.estado_salvo: bytes | None = None  # foto do estado antes de uma sequência
        self.estado_t = 0.0  # quando chegou o último estado
        self._ultimo_envio: bytes | None = None
        self.auto_reconectar = True  # no servidor, quem reconecta é a rotina de manutenção
        self._trava_conexao = asyncio.Lock()
        # comandos que não chegaram (fita caiu ou estava desconectada); o servidor reaplica
        # quando ela reconecta, para nenhum comando se perder em silêncio
        self.pendentes: list[bytes] = []

    def _notificacao(self, _, dados: bytearray):
        if len(dados) >= 11 and dados[1] == 1:
            self.estado = bytes(dados)
            self.estado_t = time.monotonic()

    async def conectar(self, tentativas: int = 6) -> bool:
        async with self._trava_conexao:
            if self.conectada:
                return True
            return await self._conectar(tentativas)

    async def _conectar(self, tentativas: int) -> bool:
        # Medido em 21/11/2026: conectar falha ~metade das vezes (problema do BlueZ/Intel
        # com esse chip, não de sinal), e quando dá certo pode levar 10-25 s. Por isso o
        # limite de 30 s e várias tentativas. Depois de conectada, a ligação fica estável.
        for t in range(tentativas):
            try:
                dev = await BleakScanner.find_device_by_address(self.mac, timeout=12)
                if not dev:
                    continue
                c = BleakClient(dev, timeout=30)
                await c.connect()
                await c.start_notify(NOTIFY, self._notificacao)
                self.cliente = c
                await c.write_gatt_char(ESCRITA, CMD_ESTADO, response=False)
                await asyncio.sleep(0.5)
                return True
            except Exception as e:
                print(f"  {self.nome}: tentativa {t + 1} falhou ({type(e).__name__})", file=sys.stderr)
                await asyncio.sleep(2)
        return False

    @property
    def conectada(self) -> bool:
        return self.cliente is not None and self.cliente.is_connected

    async def enviar(self, p: bytes, repetir_igual: bool = True) -> bool:
        """Manda um pacote. Devolve True se a fita confirmou o recebimento."""
        if not repetir_igual and p == self._ultimo_envio:
            return True
        if not self.conectada:
            if not self.auto_reconectar or not await self.conectar(3):
                return False
        try:
            # escrita COM confirmação: sem ela, em rajadas (sequências) a fita perde comandos
            # sem avisar (testado em 21/11/2026: a fita do meio não recebeu nenhum)
            await self.cliente.write_gatt_char(ESCRITA, p, response=True)
            self._ultimo_envio = p
            return True
        except Exception:
            self.cliente = None  # reconecta no próximo envio
            return False

    async def aplicar(self, pacotes: list[bytes]) -> bool:
        """Manda uma sequência de pacotes que define o estado da fita (ex.: ligar + cor).
        O que não chegar fica em self.pendentes; um comando novo substitui o pendente."""
        self.pendentes = []
        for i, p in enumerate(pacotes):
            if not await self.enviar(p):
                self.pendentes = list(pacotes[i:])
                return False
        return True

    def salvar_estado(self):
        self.estado_salvo = self.estado

    async def restaurar(self):
        s = self.estado_salvo or self.estado
        self.estado_salvo = None
        if not s:
            return
        pac = []
        if s[7] == 2:
            # no estado, o brilho do efeito vem em 0-100; o comando usa 0-1000
            pac.append(cmd_efeito(s[8], ((s[9] << 8) | s[10]) * 10))
        elif s[7] == 1 and len(s) >= 14:
            pac.append(pacote(0xAA, 3, 7, 1, *s[8:14]))
        elif s[7] == 3 and len(s) >= 16:
            pac.append(pacote(0xAA, 3, 0x0A, 3, *s[8:16]))  # modo música
        if s[6] == 0:
            pac.append(CMD_DESLIGAR)
        await self.aplicar(pac)

    async def desconectar(self):
        if self.cliente:
            try:
                await asyncio.sleep(0.3)
                await self.cliente.disconnect()
            except Exception:
                pass
            self.cliente = None

    def descrever(self) -> str:
        s = self.estado
        if not s:
            return "sem resposta de estado"
        lig = "ligada" if s[6] else "desligada"
        cd = (s[3] << 16) | (s[4] << 8) | s[5]  # contagem regressiva em segundos (0 = nenhuma)
        if cd:
            lig += f" (contagem regressiva: {cd // 3600}h{cd % 3600 // 60:02d}min)"
        if s[7] == 2:
            return f"{lig}, efeito {s[8]}, brilho {(s[9] << 8) | s[10]}%"
        if s[7] == 3 and len(s) >= 11:
            return f"{lig}, modo música (microfone da fita), estilo {s[8] >> 4}, sensibilidade {s[9]}"
        if s[7] == 1 and len(s) >= 14:
            h, sat, v = (s[8] << 8) | s[9], (s[10] << 8) | s[11], (s[12] << 8) | s[13]
            return f"{lig}, cor matiz {h}°, saturação {sat / 10:.0f}%, brilho {v / 10:.0f}%"
        return f"{lig}, modo {s[7]}"


async def consultar(fitas: list[Fita], espera: float = 3.0):
    """Pede o estado e espera a resposta nova de cada fita (algumas demoram ~1-2 s)."""
    t0 = time.monotonic()
    await asyncio.gather(*[f.enviar(CMD_ESTADO) for f in fitas])
    while time.monotonic() - t0 < espera:
        if all(f.estado_t > t0 for f in fitas if f.conectada):
            return
        await asyncio.sleep(0.1)


async def conectar_todas(fitas: list[Fita]) -> list[Fita]:
    # BlueZ se atrapalha conectando várias ao mesmo tempo: uma de cada vez.
    ok = []
    for f in fitas:
        print(f"Conectando {f.nome} ({f.mac[-5:]})...", file=sys.stderr)
        if await f.conectar():
            ok.append(f)
        else:
            print(f"  não consegui conectar na fita {f.nome}", file=sys.stderr)
    return ok


# ---------- sequências: cada uma devolve (h, s, v) por fita no instante t ----------
# i = índice da fita (0 = embaixo), n = total de fitas, t = tempo em "passos"

def seq_natal(i, n, t):
    # vermelho / verde / branco subindo pela árvore
    paleta = [(0, 1000), (120, 1000), (0, 0)]
    h, s = paleta[(int(t) - i) % len(paleta)]
    return h, s, 1000


def seq_subida(i, n, t):
    # uma fita acesa forte de cada vez, de baixo para cima, as outras fracas
    passo = int(t) % (n + 1)
    cor = (int(t) // (n + 1) * 60) % 360
    return cor, 1000, (1000 if i == passo else 80)


def seq_arco_iris(i, n, t):
    # arco-íris contínuo, cada fita 120° atrás da de baixo: parece subir
    return (t * 20 - i * (360 / n)) % 360, 1000, 1000


def seq_cometa(i, n, t):
    # um "cometa" dourado sobe com rastro e desaparece no topo
    ciclo = n + 2
    pos = t % ciclo
    d = pos - i
    if 0 <= d < 1:
        v = 1000
    elif 1 <= d < 2.5:
        v = int(1000 * (1 - (d - 1) / 1.5) ** 2)
    else:
        v = 0
    return 40, 700, max(v, 20)


# nome: (função, segundos entre atualizações, quanto t avança por atualização)
SEQUENCIAS = {"natal": (seq_natal, 1.0, 1.0), "subida": (seq_subida, 0.6, 1.0),
              "arco-iris": (seq_arco_iris, 0.25, 1.0), "cometa": (seq_cometa, 0.2, 0.25)}


async def rodar_sequencia(fitas: list[Fita], nome: str, velocidade: float, brilho: int):
    func, intervalo, passo_t = SEQUENCIAS[nome]
    intervalo /= max(velocidade, 0.05)
    escala = brilho / 100
    for f in fitas:
        await f.enviar(CMD_LIGAR)
    print(f"Sequência '{nome}' rodando. Ctrl+C para parar.", file=sys.stderr)
    t = 0.0
    while True:
        await asyncio.gather(*[
            f.enviar(cmd_hsv(*_aplica_brilho(func(i, len(fitas), t), escala)), repetir_igual=False)
            for i, f in enumerate(fitas)
        ])
        t += passo_t
        await asyncio.sleep(intervalo)


def _aplica_brilho(hsv, escala):
    h, s, v = hsv
    return h, s, max(10, v * escala)


ACOES = ["ligar", "desligar", "cor", "brilho", "efeito", "estado", "velocidade", "pausar",
         "continuar", "musica", "sequencia", "parar", "liberar", "conectar", "sincronizar", "desligar-em", "procurar", "piscar", "servidor"]


async def executar(fitas: list[Fita], acao: str, valores: list[str]) -> str:
    """Executa um comando simples nas fitas. Devolve o texto de resposta.
    Fitas desconectadas (ou que caírem no meio) ficam com o comando pendente."""
    pac: list[bytes] = []

    def todas(p):
        pac.append(p)

    if acao == "ligar":
        todas(CMD_LIGAR)
    elif acao == "desligar":
        todas(CMD_DESLIGAR)
    elif acao == "cor":
        if not valores:
            return "Informe a cor: " + ", ".join(CORES) + " ou um matiz 0-359"
        c = valores[0].lower()
        v = int(valores[1]) * 10 if len(valores) > 1 else 1000
        if c in CORES:
            h, s = (0, 0) if CORES[c] is None else (CORES[c], 1000)
        else:
            h, s = int(c), 1000
        todas(CMD_LIGAR)
        todas(cmd_hsv(h, s, v))
    elif acao == "brilho":
        v = int(valores[0]) * 10
        await consultar(fitas)
        por_fita = {}
        for f in fitas:
            s = f.estado
            if s and s[7] == 2:
                por_fita[f.nome] = [cmd_efeito(s[8], v)]
            elif s and s[7] == 1 and len(s) >= 14:
                por_fita[f.nome] = [cmd_hsv((s[8] << 8) | s[9], (s[10] << 8) | s[11], v)]
        await asyncio.gather(*[f.aplicar(por_fita[f.nome]) for f in fitas if f.nome in por_fita])
        return _resumo(fitas)
    elif acao == "efeito":
        n = int(valores[0])
        v = int(valores[1]) * 10 if len(valores) > 1 else 1000
        todas(CMD_LIGAR)
        todas(cmd_efeito(n, v))
    elif acao == "velocidade":
        todas(cmd_velocidade(int(valores[0])))
    elif acao == "musica":
        # modo música pelo microfone da própria fita: AA 03 0A 03 (modo<<4|auto) sens B(2) H(2) S(2)
        # sem cor = auto (a fita escolhe as cores); com cor = cor fixa
        modo = int(valores[0]) if valores else 1
        sens = int(valores[1]) if len(valores) > 1 else 70
        auto, h, sat = 1, 0, 1000
        if len(valores) > 2:
            c = valores[2].lower()
            auto = 0
            if c in CORES:
                h, sat = (0, 0) if CORES[c] is None else (CORES[c], 1000)
            else:
                h = int(c)
        todas(CMD_LIGAR)
        todas(pacote(0xAA, 3, 0x0A, 3, (modo << 4) | auto, sens, 0x03, 0xE8,
                           h >> 8, h & 0xFF, sat >> 8, sat & 0xFF))
    elif acao == "desligar-em":
        # contagem regressiva da própria fita: AA 04 05 segundos(4) ação (0 = desligar); 0 s cancela
        if not valores:
            return "uso: desligar-em <horas, ex. 1.5> | desligar-em cancelar"
        seg = 0 if valores[0].lower() in ("cancelar", "0", "nao", "não") else int(float(valores[0]) * 3600)
        todas(pacote(0xAA, 4, 5, *seg.to_bytes(4, "big"), 0))
    elif acao == "pausar":
        todas(CMD_PAUSAR)
    elif acao == "continuar":
        todas(CMD_CONTINUAR)
    elif acao == "estado":
        await consultar(fitas)
        return "\n".join(f"{f.nome:8} ({f.mac[-5:]}): "
                         f"{f.descrever() if f.conectada else 'desconectada'}" for f in fitas)
    else:
        return f"comando desconhecido: {acao}"
    await asyncio.gather(*[f.aplicar(pac) for f in fitas])
    return _resumo(fitas)


async def sincronizar(fitas: list[Fita]) -> str:
    """Se as fitas estão ligadas no mesmo efeito, manda o efeito a todas ao mesmo tempo
    para recomeçarem juntas (cada uma mantém o próprio brilho)."""
    fitas = [f for f in fitas if f.conectada]
    if len(fitas) < 2:
        return "sincronia: precisa de pelo menos duas fitas conectadas"
    await consultar(fitas)
    est = [f.estado for f in fitas]
    if not all(s and s[6] and s[7] == 2 for s in est):
        return "sincronia: nem todas estão ligadas num efeito"
    if len({s[8] for s in est}) != 1:
        return "sincronia: as fitas estão em efeitos diferentes"
    pac = {f.nome: cmd_efeito(f.estado[8], ((f.estado[9] << 8) | f.estado[10]) * 10) for f in fitas}
    ok = await asyncio.gather(*[f.enviar(pac[f.nome]) for f in fitas])
    nomes = [f.nome for f, o in zip(fitas, ok) if o]
    return f"efeito {est[0][8]} sincronizado em {', '.join(nomes)}"


def _resumo(fitas: list[Fita]) -> str:
    faltam = [f.nome for f in fitas if f.pendentes]
    if not faltam:
        return "ok"
    ok = [f.nome for f in fitas if not f.pendentes]
    return ((f"ok em {', '.join(ok)}; " if ok else "") +
            f"NÃO chegou em {', '.join(faltam)} (sem conexão; aplico assim que reconectar)")


def _parse_fitas(texto: str) -> list[str]:
    """Nomes de fitas.json, ou a posição (1 = a primeira, de baixo), separados por vírgula; ou "todas"."""
    if not FITAS:
        sys.exit("Nenhuma fita configurada. Rode: uv run natal.py procurar")
    nomes = []
    for n in texto.lower().replace(" ", "").split(","):
        if n == "todas":
            return list(FITAS)
        if n.isdigit() and 1 <= int(n) <= len(FITAS):
            n = list(FITAS)[int(n) - 1]
        if n not in FITAS:
            sys.exit(f"Fita desconhecida: {n} (use {', '.join(FITAS)}, 1-{len(FITAS)} ou todas)")
        if n not in nomes:
            nomes.append(n)
    return nomes


# ------------------------------- descoberta -------------------------------

async def procurar(segundos: float = 30) -> list[tuple[str, str, int]]:
    """Procura fitas Hello Fairy anunciando por perto. Devolve (MAC, nome, RSSI), da mais forte.
    Fita conectada (ao servidor, ao celular) não anuncia: libere antes."""
    achados = await BleakScanner.discover(timeout=segundos, return_adv=True)
    r = [(d.address, adv.local_name or d.name or "", adv.rssi) for d, adv in achados.values()
         if (adv.local_name or d.name or "").startswith(NOME_ANUNCIO)]
    return sorted(r, key=lambda x: -x[2])


async def piscar(mac: str, nome: str = "") -> bool:
    """Pisca a fita (vermelho / apagada, 3 vezes) e devolve ao estado em que estava."""
    f = Fita(nome or mac[-5:], mac)
    if not await f.conectar(4):
        return False
    try:
        await consultar([f])
        f.salvar_estado()
        for _ in range(3):
            await f.aplicar([CMD_LIGAR, cmd_hsv(0, 1000, 1000)])
            await asyncio.sleep(0.6)
            await f.aplicar([CMD_DESLIGAR])
            await asyncio.sleep(0.6)
        await f.restaurar()
        return True
    finally:
        await f.desconectar()


async def acao_procurar(args):
    seg = float(args.valores[0]) if args.valores else 30
    print(f"Procurando fitas '{NOME_ANUNCIO}-…' por {seg:g} s...", flush=True)
    achadas = await procurar(seg)
    conhecidas = {m.upper(): n for n, m in FITAS.items()}
    for mac, nome, rssi in achadas:
        print(f"  {mac}  {nome:18} {rssi:4} dBm  {conhecidas.get(mac.upper(), '(nova)')}")
    faltam = [n for n, m in FITAS.items() if m.upper() not in {a[0].upper() for a in achadas}]
    if faltam:
        print(f"Não apareceram: {', '.join(faltam)} (conectadas ao servidor ou ao celular não anunciam;"
              " use 'liberar' ou pare o servidor)")
    novas = [a for a in achadas if a[0].upper() not in conhecidas]
    if not novas:
        return
    if not sys.stdin.isatty():
        print("Rode num terminal para nomear e gravar as novas em fitas.json.")
        return
    print("\nPara cada fita nova, eu faço ela piscar em vermelho; diga o nome dela (ex.: embaixo, meio,"
          " cima). Enter = pular. Grave na ordem de baixo para cima.")
    fitas = dict(FITAS)
    for mac, nome, _ in novas:
        print(f"→ piscando {nome} ({mac})...", flush=True)
        if not await piscar(mac):
            print("  não consegui conectar (tente de novo depois)")
            continue
        n = input("  nome desta fita: ").strip().lower()
        if n:
            fitas[n] = mac
    if fitas != FITAS:
        gravar_fitas(fitas)
        print(f"Gravado em {CONFIG}: {', '.join(fitas)}. Para mudar a ordem, edite o arquivo.")


# ------------------------------- modo direto -------------------------------

async def direto(args):
    if args.acao == "procurar":
        await acao_procurar(args)
        return
    if args.acao == "piscar":
        alvos = _parse_fitas(args.valores[0] if args.valores else args.fitas)
        for n in alvos:
            print(f"{n}: {'piscou' if await piscar(FITAS[n], n) else 'não conectou'}")
        return
    if args.acao == "liberar":
        for n in _parse_fitas(args.fitas):
            proc = await asyncio.create_subprocess_exec(
                "bluetoothctl", "disconnect", FITAS[n],
                stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
            await proc.wait()
        print("fitas liberadas (o notebook não está mais conectado nelas)")
        return
    if args.acao == "conectar":
        print("'conectar' só faz sentido com o servidor rodando.")
        return
    if args.acao == "sincronizar" and args.valores:
        print("o intervalo da sincronia automática só existe com o servidor rodando.")
        return
    fitas = await conectar_todas([Fita(n, FITAS[n]) for n in _parse_fitas(args.fitas)])
    if not fitas:
        sys.exit("Nenhuma fita conectou.")
    try:
        if args.acao == "sequencia":
            nome = args.valores[0] if args.valores else "natal"
            if nome not in SEQUENCIAS:
                sys.exit("Sequências: " + ", ".join(SEQUENCIAS))
            await consultar(fitas)
            for f in fitas:
                f.salvar_estado()
            try:
                await rodar_sequencia(fitas, nome, args.velocidade, args.brilho)
            except asyncio.CancelledError:
                pass
            finally:
                print("\nParando e restaurando o estado anterior...", file=sys.stderr)
                await asyncio.gather(*[f.restaurar() for f in fitas])
        elif args.acao == "parar":
            print("'parar' só faz sentido com o servidor rodando.")
        elif args.acao == "sincronizar":
            print(await sincronizar(fitas))
        else:
            print(await executar(fitas, args.acao, args.valores))
        await asyncio.sleep(0.5)
    finally:
        await asyncio.gather(*[f.desconectar() for f in fitas])


# ------------------------------- servidor -------------------------------

class Servidor:
    def __init__(self):
        self.fitas = {n: Fita(n, m) for n, m in FITAS.items()}
        for f in self.fitas.values():
            f.auto_reconectar = False
        self.seq: asyncio.Task | None = None
        self.seq_fitas: list[Fita] = []
        self.trava = asyncio.Lock()
        self.acordar = asyncio.Event()
        self.liberado_ate = 0.0  # time.monotonic(); enquanto for maior, não conecta
        self.sincronia_min = SINCRONIA_MIN
        self.ultima_sincronia = time.monotonic()

    @property
    def liberado(self) -> bool:
        return time.monotonic() < self.liberado_ate

    def log(self, msg):
        print(time.strftime("%H:%M:%S"), msg, file=sys.stderr, flush=True)

    @property
    def seq_rodando(self) -> bool:
        return bool(self.seq and not self.seq.done())

    async def sincronizar(self, motivo: str):
        if self.seq_rodando or self.liberado:
            return
        fitas = [f for f in self.fitas.values() if f.conectada]
        if len(fitas) < 2:
            return
        async with self.trava:
            resp = await sincronizar(fitas)
        self.ultima_sincronia = time.monotonic()
        if "sincronizado" in resp:
            self.log(f"{resp} ({motivo})")

    async def manter_conectadas(self):
        # conecta uma de cada vez (o BlueZ se atrapalha com várias ao mesmo tempo) e,
        # a cada 20 s, consulta o estado de todas: serve de "keepalive" e detecta queda.
        while True:
            reconectou = False
            for f in self.fitas.values():
                if not f.conectada and not self.liberado:
                    self.log(f"conectando {f.nome}...")
                    ok = await f.conectar(tentativas=3)
                    self.log(f"{f.nome}: {'conectada' if ok else 'falhou, tento de novo depois'}")
                    reconectou = reconectou or ok
                    if ok and f.pendentes and not (self.seq and not self.seq.done()):
                        ok = await f.aplicar(f.pendentes)
                        self.log(f"{f.nome}: comando pendente {'aplicado' if ok else 'falhou de novo'}")
            if reconectou:
                await self.sincronizar("fita reconectou")
            elif self.sincronia_min and \
                    time.monotonic() - self.ultima_sincronia >= self.sincronia_min * 60:
                await self.sincronizar("automática")
            for f in self.fitas.values():
                if f.conectada and not (self.seq and not self.seq.done()):
                    try:
                        await f.cliente.write_gatt_char(ESCRITA, CMD_ESTADO, response=False)
                    except Exception:
                        f.cliente = None
            try:
                await asyncio.wait_for(self.acordar.wait(), 20)
            except asyncio.TimeoutError:
                pass
            self.acordar.clear()

    async def parar_seq(self) -> bool:
        if self.seq and not self.seq.done():
            self.seq.cancel()
            try:
                await self.seq
            except (asyncio.CancelledError, Exception):
                pass
            await asyncio.gather(*[f.restaurar() for f in self.seq_fitas])
            return True
        return False

    async def atender(self, leitor, escritor):
        try:
            pedido = json.loads((await leitor.readline()).decode())
            acao, valores = pedido["acao"], pedido.get("valores", [])
            fitas = [self.fitas[n] for n in pedido.get("fitas", list(FITAS))]
            async with self.trava:
                if acao == "liberar":
                    await self.parar_seq()
                    if valores:
                        minutos = float(valores[0])
                        self.liberado_ate = time.monotonic() + minutos * 60
                        quando = f"por {minutos:g} min (depois volto a conectar sozinho)"
                    else:
                        self.liberado_ate = float("inf")
                        quando = "até você mandar 'conectar'"
                    await asyncio.gather(*[f.desconectar() for f in self.fitas.values()])
                    resp = f"fitas liberadas para o celular {quando}"
                elif acao == "conectar":
                    self.liberado_ate = 0.0
                    self.acordar.set()
                    resp = "voltando a conectar nas fitas (pode levar até 1-2 min)"
                elif acao == "sincronizar":
                    if valores:
                        self.sincronia_min = float(valores[0])
                        resp = (f"sincronia automática a cada {self.sincronia_min:g} min"
                                if self.sincronia_min else "sincronia automática desligada") + "; "
                    else:
                        resp = ""
                    await self.parar_seq()
                    resp += await sincronizar([f for f in self.fitas.values() if f.conectada])
                    self.ultima_sincronia = time.monotonic()
                elif acao == "piscar":
                    # pisca usando a conexão que o servidor já tem (vermelho / apagada, 3 vezes)
                    await self.parar_seq()
                    alvos = [f for f in fitas if f.conectada]
                    await consultar(alvos)
                    for f in alvos:
                        f.salvar_estado()
                    for _ in range(3):
                        await asyncio.gather(*[f.aplicar([CMD_LIGAR, cmd_hsv(0, 1000, 1000)]) for f in alvos])
                        await asyncio.sleep(0.6)
                        await asyncio.gather(*[f.aplicar([CMD_DESLIGAR]) for f in alvos])
                        await asyncio.sleep(0.6)
                    await asyncio.gather(*[f.restaurar() for f in alvos])
                    sem = [f.nome for f in fitas if f not in alvos]
                    resp = (f"piscou: {', '.join(f.nome for f in alvos) or 'nenhuma'}"
                            + (f"; sem conexão: {', '.join(sem)}" if sem else ""))
                elif acao == "parar":
                    resp = "sequência parada, estado anterior restaurado" if await self.parar_seq() \
                        else "nenhuma sequência rodando"
                elif acao == "sequencia":
                    nome = valores[0] if valores else "natal"
                    if nome not in SEQUENCIAS:
                        resp = "Sequências: " + ", ".join(SEQUENCIAS)
                    else:
                        await self.parar_seq()
                        # guarda o estado antes, para restaurar no "parar"
                        await consultar([f for f in fitas if f.conectada])
                        for f in fitas:
                            f.salvar_estado()
                        self.seq_fitas = fitas
                        self.seq = asyncio.create_task(rodar_sequencia(
                            fitas, nome, pedido.get("velocidade", 1.0), pedido.get("brilho", 100)))
                        resp = f"sequência '{nome}' rodando (use 'parar' para encerrar)"
                else:
                    if acao != "estado":
                        await self.parar_seq()
                    resp = await executar(fitas, acao, valores)
                    if acao == "efeito":
                        self.ultima_sincronia = time.monotonic()  # acabaram de começar juntas
                    if self.liberado and any(not f.conectada for f in fitas):
                        resp += "\n(fitas liberadas para o celular; use 'conectar' para retomar)"
                    if acao != "estado":
                        self.acordar.set()  # tenta reconectar já quem ficou com pendência
            self.log(f"{acao} {' '.join(valores)} -> {resp.splitlines()[0]}")
        except Exception as e:
            resp = f"erro: {e!r}"
        try:
            escritor.write((resp + "\n").encode())
            await escritor.drain()
            escritor.close()
        except ConnectionError:
            pass  # o cliente desistiu (Ctrl+C) antes da resposta

    async def rodar(self):
        if os.path.exists(SOCKET):
            try:
                _, w = await asyncio.open_unix_connection(SOCKET)
                w.close()
                sys.exit("Já existe um servidor rodando.")
            except (ConnectionRefusedError, FileNotFoundError):
                os.unlink(SOCKET)
        srv = await asyncio.start_unix_server(self.atender, path=SOCKET)
        os.chmod(SOCKET, 0o600)
        self.log(f"servidor ouvindo em {SOCKET}")
        manter = asyncio.create_task(self.manter_conectadas())
        try:
            async with srv:
                await srv.serve_forever()
        finally:
            manter.cancel()
            await self.parar_seq()
            await asyncio.gather(*[f.desconectar() for f in self.fitas.values()])
            if os.path.exists(SOCKET):
                os.unlink(SOCKET)
            self.log("servidor encerrado, fitas desconectadas")


async def via_servidor(args) -> bool:
    """Manda o comando ao servidor, se houver um rodando. Devolve False se não houver."""
    try:
        leitor, escritor = await asyncio.open_unix_connection(SOCKET)
    except (FileNotFoundError, ConnectionRefusedError):
        return False
    alvo = args.valores[0] if args.acao == "piscar" and args.valores else args.fitas
    pedido = {"acao": args.acao, "valores": args.valores, "fitas": _parse_fitas(alvo),
              "velocidade": args.velocidade, "brilho": args.brilho}
    escritor.write((json.dumps(pedido) + "\n").encode())
    await escritor.drain()
    print((await leitor.read()).decode().rstrip())
    escritor.close()
    return True


async def principal(args):
    # se o processo for encerrado (kill/timeout), desconecta direito em vez de deixar
    # a fita presa numa conexão fantasma no notebook
    import signal
    tarefa = asyncio.current_task()
    asyncio.get_running_loop().add_signal_handler(signal.SIGTERM, tarefa.cancel)
    if args.acao == "servidor":
        if not FITAS:
            sys.exit("Nenhuma fita configurada. Rode: uv run natal.py procurar")
        await Servidor().rodar()
    elif args.acao == "procurar":
        await direto(args)  # o servidor não participa: a busca é pelo rádio
    elif not await via_servidor(args):
        await direto(args)


def main():
    p = argparse.ArgumentParser(description="Controle das fitas Hello Fairy da árvore")
    p.add_argument("acao", choices=ACOES)
    p.add_argument("valores", nargs="*")
    p.add_argument("--fitas", default="todas")
    p.add_argument("--velocidade", type=float, default=1.0, help="multiplicador (2 = duas vezes mais rápido)")
    p.add_argument("--brilho", type=int, default=100, help="brilho da sequência, 0-100")
    args = p.parse_args()
    try:
        asyncio.run(principal(args))
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass


if __name__ == "__main__":
    main()
