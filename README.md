# fita-led

Controle pelo Linux de fitas de LED Bluetooth baratas, sem o app do celular:

- **Hello Fairy** (controlador BSL11, app Hello Fairy / Hysiry): fios de bolinhas de árvore de Natal.
  Bluetooth (`natal.py`) e infravermelho por um emissor IR Tuya (`ir.py`).
- **"GATT--DEMO"** (apps MR Star e Lenze Colorful): fita comum de quarto (`gattdemo.py`).

Os protocolos foram extraídos dos apps Android e testados nas fitas; estão documentados aqui.
Os textos estão em português.

## Requisitos
- Linux com BlueZ e um adaptador Bluetooth LE.
- [uv](https://docs.astral.sh/uv/) (cada script declara as próprias dependências; `uv run` instala).
- Para o infravermelho: um emissor IR Tuya (Smart Life) na mesma rede.

## Começo rápido

```bash
# 1. achar as fitas Hello Fairy, piscar cada uma e dar um nome (grava fitas.json)
uv run natal.py procurar
# 2. usar
uv run natal.py ligar
uv run natal.py cor azul 60
uv run natal.py efeito 12
uv run natal.py musica 2 85          # microfone da própria fita
uv run natal.py estado
```

Conectar nessas fitas falha com frequência (ver PROGRESSO.md, "Diagnóstico da conexão"); depois de
conectada, a ligação é estável. Por isso existe o modo servidor, que mantém as fitas conectadas,
guarda os comandos que não chegaram e sincroniza os efeitos:

```bash
uv run natal.py servidor             # ou como serviço systemd do usuário (ver PROGRESSO.md)
```

Infravermelho (chega a todas as fitas ao mesmo tempo, sem conexão):

```bash
uv run tuya/chave-emissor.py         # uma vez: chave e IP do emissor (login por QR do app)
uv run ir.py lista
uv run ir.py ligar + brilho-50 + cor roxo
```

Fita GATT--DEMO:

```bash
uv run gattdemo.py procurar          # acha, confere os serviços, pisca e grava o MAC
uv run gattdemo.py efeitos transição
uv run gattdemo.py efeito água corrente 40 80
```

## Arquivos

| arquivo | o que é |
|---|---|
| `natal.py` | fitas Hello Fairy por Bluetooth (comandos, sequências, servidor) |
| `ir.py`, `ir-fitas.json` | fitas Hello Fairy por infravermelho; as 24 teclas do controle |
| `gattdemo.py` | fita GATT--DEMO (117 efeitos com nome, microfone, temporizador) |
| `tuya/` | descoberta do emissor IR Tuya (como achar id, chave, IP) |
| `fitas.json.example`, `ir-emissor.json.example` | modelos dos arquivos locais (os de verdade ficam fora do git) |
| `PROTOCOLO-hellofairy.md`, `PROTOCOLO-gattdemo-mrstar.md` | protocolos BLE |
| `SOM-E-COR.md` | como os apps transformam som em cor |
| `cenas/` | animações dos efeitos Hello Fairy (`cenas/index.html`) |
| `PROGRESSO.md` | diário do projeto: descobertas, diagnóstico, pendências |

## Cuidados
- Nunca escrever no serviço OTA `5833ff01…` das fitas nem mandar os comandos marcados "NÃO ENVIAR"
  nos protocolos: podem apagar ou inutilizar o controlador.
- `fitas.json`, `ir-emissor.json` e `tuya/segredos.json` são locais (MACs, chave e login); não publicar.

As animações em `cenas/` vêm do servidor público do fabricante (Hello Fairy) e pertencem a ele.
