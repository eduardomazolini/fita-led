# Progresso — fitas de LED (atualizado em 21/11/2026, noite)

## O que existe
- `natal.py`: controle das 3 fitas Hello Fairy pelo Bluetooth (`uv run natal.py ...`). Comandos: ligar,
  desligar, cor, brilho, efeito 1-20, estado, velocidade, pausar/continuar, musica, sequencia
  (natal, subida, arco-iris, cometa), parar, liberar [minutos], conectar, sincronizar [minutos],
  desligar-em <horas>|cancelar, procurar, piscar, servidor. `--fitas` aceita os nomes de fitas.json
  ou a posição (1, 2, 3 de baixo para cima).
  - MACs em `fitas.json` (fora do git; modelo `fitas.json.example`): `procurar` acha as
    "Hello Fairy-XXXX" (as conectadas não anunciam: `liberar` antes), pisca cada nova e pede o nome.
  - Comando que não chega fica pendente e o servidor aplica quando a fita reconecta (testado).
  - Sincronia: com as três no mesmo efeito, o servidor reenvia o efeito às três juntas a cada 5 min
    e logo que uma fita reconecta (`sincronizar 0` desliga; `sincronizar 10` muda o intervalo).
    Ainda não observado se reenviar o efeito o recomeça do zero.
  - `estado` mostra a contagem regressiva de desligamento, se houver (bytes 3-5 do estado).
- `ir.py`: fitas da árvore por infravermelho, pelo emissor Tuya "IR Sala". Chega às três ao mesmo tempo,
  sem conexão. `uv run ir.py lista`; `uv run ir.py ligar + brilho-50`; `uv run ir.py cor roxo`.
  - `ir-emissor.json` (modo 600): id, ip, chave local, versão e control_type do emissor. Gerado por
    `uv run tuya/chave-emissor.py` (login por QR do Smart Life + varredura da rede; ver tuya/README.md).
    Rodar de novo se o emissor for reconfigurado no app (a chave muda) ou mudar de IP.
  - `ir-fitas.json`: as 24 teclas com nome (formato `nec:00:CC`).
- `gattdemo.py`: fita "GATT--DEMO" (MR Star / Lenze Colorful), conexão direta. `procurar` acha pelo
  anúncio (nome GATT--DEMO ou serviço 0x2022), confere os serviços (fff0/fff3/fff4 + OTA 5833ff01),
  pisca e grava o MAC em fitas.json → "gattdemo";, sem servidor. 117 efeitos com nome em
  português, nas abas do app (básico, abrir e fechar, transição, água corrente, à direita = rastro,
  executando; mais fluxo e extra, que o app esconde); `efeito N [velocidade] [brilho]`, cor, brilho,
  velocidade, sentido (Positivo/Reverso no app), microfone (clássico, suave, dinâmico, disco),
  demo por categoria, temporizador liga/desliga com dias (e leitura do gravado), relógio.
  **Nada testado na fita**: ela não apareceu no scan em 21/11. Conferir se `BC 01 01 01` liga.
- Serviço systemd do usuário `natal-led.service` (`~/.config/systemd/user/`), habilitado:
  roda `natal.py servidor`. Log: `journalctl --user -u natal-led -f`. Só sobe com login (linger off).
- `cenas/index.html`: animações dos 20 efeitos e dos 4 estilos do modo música.
- `PROTOCOLO-hellofairy.md`, `PROTOCOLO-gattdemo-mrstar.md`: protocolos extraídos dos apps.
- `SOM-E-COR.md`: como os apps transformam som em cor (e os defeitos do app MR Star / Lenze).
- `privado/`: material de pesquisa, explicado em `privado/README.md`: APKs, scripts de análise
  (varre_ir.py, mapeia_ir.py,
  paleta_ir.py, musica_app.py) e o resultado bruto da varredura IR (ir-varredura.json).

## Descobertas
- Controlador BSL11, firmware 2.0.0, PID 4004 ("ball light"). Sem atualização de firmware.
- Escrita BLE COM confirmação (sem ela a fita perde comandos em rajada).
- Cada fita tem microfone próprio. Música: estilos 1 Energia, 2 Ritmo, 3 Rolagem, 4 Espectro.
  Sensibilidade 85 boa (70 pede som alto; 100 fica sempre acesa). Energia apaga no silêncio.

### Infravermelho (21/11/2026, confirmado pelo usuário olhando a árvore)
NEC, endereço 00, teclas 00-17 (controle de 24 teclas); as outras 232 do endereço 00 não fazem nada.
O código só leva o número da tecla: não dá para mandar matiz arbitrário por IR.

| tecla | nome em ir.py | efeito |
|---|---|---|
| 00 / 01 | mais / menos | brilho ±10 (no modo música: sensibilidade ±10) |
| 02 / 03 | desligar / ligar | 03 liga em branco |
| 04 / 05 / 06 | vermelho / verde / azul | cor fixa, mantém o brilho |
| 07 / 0B / 0F | brilho-25 / -50 / -100 | brilho fixo |
| 08 / 09 / 0A | desligar-1h / -4h / -8h | contagem regressiva; a fita pisca para confirmar |
| 0C / 0D / 0E | musica-1 / -2 / -3 | Energia, Ritmo, Rolagem |
| 10 11 12 14 15 | efeito-1 2 3 5 6 | efeitos prontos |
| 13 / 17 | proximo / anterior | próxima cor, efeito ou estilo, conforme o modo |
| 16 | modo-efeitos | foi ao efeito 1 nos testes |

Ciclo do "próximo" no modo cor (16 posições): 0, 15, 30, 45, 60 | 120, 135, 150, 165, 180 |
240, 255, 270, 285, 300 | branco. `ir.py cor` usa vermelho/verde/azul + N × próximo (roxo testado nas 3).
O emissor responde de forma intermitente na rede local (às vezes some por minutos; o app pela nuvem
funciona). Não é a chave.

### Diagnóstico da conexão BLE (21/11/2026, tarde)
Farejador nRF52840 (nRF Sniffer v5, `/dev/ttyACM1`):
- Baixo e meio recebem o CONNECT_IND mas quase nunca respondem (4-24% dos SCAN_REQ, cima ~90%).
  Quando respondem, respondem no tempo certo: a falha é ausência de resposta, não deriva de relógio.
- Descartado: distância/sinal, parâmetros de conexão (debugfs, somem no reboot), religar da tomada.
- Dongle como adaptador HCI (Zephyr) foi pior que o Intel. O dongle está hoje com o nRF Sniffer.
- Saídas: manter a conexão (servidor + pendentes), infravermelho para o básico, ou trocar os
  controladores de baixo e do meio.
- Se o notebook ficar com conexão fantasma ("Connected: yes" sem processo), `bluetoothctl power off/on`.

## Situação no fim da sessão
- Servidor rodando, as três conectaram às 18:33. Baixo e meio no efeito 5, brilho 100; a de cima
  apareceu em efeitos diferentes (14, 15, 18) sem comando: causa não verificada.
- Contagem regressiva de 8 h (do teste da tecla 0A) cancelada nas três.

## Pendências
1. Testar gattdemo.py na fita GATT--DEMO (ligar/desligar, efeitos, microfone, temporizador).
2. Ver se reenviar o efeito recomeça a animação (sincronia) com o usuário olhando.
3. Testar os estilos de música 3 e 4 no silêncio; se nenhum servir, fazer pelo notebook.
4. Modo música pelo notebook (PipeWire → cor/volume), caminho em PROTOCOLO-gattdemo-mrstar.md e SOM-E-COR.md.
5. Testar `liberar` / `conectar` de verdade.
6. Com o usuário olhando: Extend do grupo (`AA 20`), ciclo de cenas (`AA 19`), DIY (`AA 0D/0E`).
7. Opcional: ESP32 perto da árvore para manter as conexões sem o notebook.

## Cuidados
- Nunca escrever no serviço OTA 5833ff01 nem mandar os comandos "NÃO ENVIAR" do protocolo.
- Fita GATT--DEMO: liberada pelo usuário em 21/11 para o gattdemo.py.
- Testes por IR/BLE mexem na árvore: usuário autorizou à vontade em 21/11; não tirar conclusões além
  do que foi medido (o usuário reclamou de conclusão especulativa).
