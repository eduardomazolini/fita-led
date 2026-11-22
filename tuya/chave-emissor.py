#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["tuya-device-sharing-sdk", "cryptography", "qrcode", "tinytuya"]
# ///
"""Gera ../ir-emissor.json (id, ip, chave local, versão) do emissor IR Tuya usado pelo ir.py.

A chave local vem da nuvem Tuya pelo login com QR code do app Smart Life (o mesmo da integração
Tuya do Home Assistant; não precisa de conta de desenvolvedor). O IP vem de uma varredura da rede
local (o emissor anuncia na porta UDP 6667). Rodar num terminal, porque o QR aparece na tela:

  uv run tuya/chave-emissor.py                 (lista os emissores IR da conta e pergunta qual)
  uv run tuya/chave-emissor.py "IR Sala"       (escolhe pelo nome que aparece no app)
  uv run tuya/chave-emissor.py --qr            (força novo login por QR)

Login por QR:
1. No app Smart Life: Eu → engrenagem (Configurações) → Conta e segurança → Código do usuário.
2. Digite o código quando pedir; aparece um QR.
3. No app, toque no leitor (canto superior direito da tela inicial), leia o QR e confirme.
O login fica em tuya/segredos.json (chmod 600) e é reaproveitado nas próximas vezes.

Rodar de novo quando o emissor for reconfigurado no app (a chave muda) ou mudar de IP.
"""

import json
import os
import sys
import time
from pathlib import Path

import qrcode
import tinytuya
from tuya_sharing import LoginControl, Manager, SharingTokenListener

# Identificadores públicos da integração Tuya do Home Assistant (homeassistant/components/tuya/const.py).
CLIENT_ID = "HA_3y9q4ak7g4ephrvke"
SCHEMA = "haauthorize"
PASTA = Path(__file__).parent
SEGREDOS = PASTA / "segredos.json"
SAIDA = PASTA.parent / "ir-emissor.json"


def gravar_secreto(arq: Path, dados):
    arq.touch(mode=0o600, exist_ok=True)
    os.chmod(arq, 0o600)
    arq.write_text(json.dumps(dados, indent=1, ensure_ascii=False))


def login_qr() -> dict:
    salvo = json.loads(SEGREDOS.read_text()).get("user_code", "") if SEGREDOS.exists() else ""
    codigo = input(f"Código do usuário do app Smart Life{' [Enter = o salvo]' if salvo else ''}: ").strip() or salvo
    login = LoginControl()
    r = login.qr_code(CLIENT_ID, SCHEMA, codigo)
    if not r.get("success"):
        raise SystemExit(f"Erro ao gerar o QR: {r.get('code')} {r.get('msg')}")
    token = r["result"]["qrcode"]
    qr = qrcode.QRCode(border=2)
    qr.add_data(f"tuyaSmart--qrLogin?token={token}")
    qr.print_ascii(invert=True)
    print("Leia o QR com o app Smart Life e confirme (espero até 2 minutos)...")
    for _ in range(60):
        ok, info = login.login_result(token, CLIENT_ID, codigo)
        if ok:
            break
        time.sleep(2)
    else:
        raise SystemExit("O QR não foi confirmado a tempo; rode de novo.")
    s = {"user_code": codigo, "terminal_id": info["terminal_id"], "endpoint": info["endpoint"],
         "token": {k: info[k] for k in ("t", "uid", "expire_time", "access_token", "refresh_token")}}
    gravar_secreto(SEGREDOS, s)
    return s


class GuardaToken(SharingTokenListener):
    """O Manager chama isto quando renova o token; gravamos para a próxima vez."""
    def update_token(self, token: dict):
        s = json.loads(SEGREDOS.read_text())
        s["token"] = token
        gravar_secreto(SEGREDOS, s)


def aparelhos(s: dict) -> list:
    m = Manager(CLIENT_ID, s["user_code"], s["terminal_id"], s["endpoint"], s["token"], GuardaToken())
    m.update_device_cache()
    return list(m.device_map.values())


def main():
    args = [a for a in sys.argv[1:] if a != "--qr"]
    nome = args[0] if args else None
    s = None if "--qr" in sys.argv or not SEGREDOS.exists() else json.loads(SEGREDOS.read_text())
    lista = None
    if s:
        try:
            lista = aparelhos(s)
        except Exception as e:
            print(f"Login salvo não funcionou ({e}); fazendo login por QR.")
    if lista is None:
        lista = aparelhos(login_qr())

    emissores = [d for d in lista if d.category == "wnykq"]  # categoria Tuya de emissor infravermelho
    if nome:
        d = next((d for d in lista if d.name == nome), None)
        if d is None:
            raise SystemExit(f"Não achei '{nome}' na conta. Emissores IR: "
                             + (", ".join(e.name for e in emissores) or "nenhum"))
    elif not emissores:
        raise SystemExit("A conta não tem emissor IR (categoria wnykq). Aparelhos: "
                         + ", ".join(f"{x.name} ({x.category})" for x in lista))
    elif len(emissores) == 1:
        d = emissores[0]
    else:
        for i, e in enumerate(emissores, 1):
            print(f"  {i}. {e.name}{'' if e.online else ' (offline)'}")
        d = emissores[int(input("Qual emissor fica de frente para as fitas? ")) - 1]
    print(f"Emissor: {d.name} (id {d.id}{'' if d.online else ', OFFLINE na nuvem'})")
    if not d.local_key:
        raise SystemExit(f"'{nome}' veio sem chave local.")

    print("Procurando o emissor na rede local (~20 s)...")
    achados = tinytuya.deviceScan(verbose=False, maxretry=15)
    local = next((v for v in achados.values() if v.get("gwId") == d.id), None)
    anterior = json.loads(SAIDA.read_text()) if SAIDA.exists() else {}
    if local:
        ip, versao = local["ip"], float(local.get("version") or 3.3)
    elif anterior.get("ip"):
        ip, versao = anterior["ip"], anterior.get("versao", 3.3)
        print(f"Não apareceu na rede agora; mantenho o IP anterior {ip}.")
    else:
        raise SystemExit("O emissor não apareceu na rede local; confira se está ligado e rode de novo.")

    # control_type: 1 = emissor antigo (DPs 201/202), 2 = novo (DPs 1-13). A detecção fala com o
    # emissor usando a chave, então também confere se ela está certa.
    tipo = anterior.get("control_type", 1)
    try:
        from tinytuya.Contrib import IRRemoteControlDevice
        ir = IRRemoteControlDevice(d.id, ip, d.local_key, version=versao)
        if ir.control_type:
            tipo = ir.control_type
            print(f"Emissor respondeu na rede local; control_type {tipo}.")
    except Exception as e:
        print(f"Não consegui falar com o emissor agora ({e}); fica control_type {tipo}. "
              "Ele às vezes some da rede local por alguns minutos; o ir.py tenta de novo a cada uso.")
    gravar_secreto(SAIDA, {"nome": d.name, "id": d.id, "ip": ip, "key": d.local_key,
                           "versao": versao, "control_type": tipo})
    print(f"Gravado {SAIDA} (chmod 600): {d.name}, {ip}, versão {versao}"
          f"{'' if anterior.get('key') in (None, d.local_key) else ' — a chave MUDOU'}.")


if __name__ == "__main__":
    main()
