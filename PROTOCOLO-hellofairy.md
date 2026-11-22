# Protocolo BLE "Hello Fairy" (com.hsr.hellofairy 3.3.6) — engenharia reversa

Fonte: jadx 1.5.1 em `scratchpad/src-hellofairy/sources` (abaixo, caminhos relativos a essa pasta).
Recursos (strings, layouts) extraídos à parte, só para leitura, com `jadx --no-src` em `scratchpad/res-hf/resources/res/`.
Métodos que o jadx não conseguiu decompilar foram refeitos com `--show-bad-code` em `scratchpad/bad/`.
Nada foi enviado por Bluetooth.

Legenda: **[C]** = confirmado no código (arquivo indicado) · **[I]** = inferido (nome de campo/fluxo, não testado).
Todos os exemplos têm o checksum correto (calculado por script).

---

## 0. Transporte e enquadramento

* Serviço `49535343-fe7d-4ae5-8fa9-9fafd205e455`; escrita em `…8841-43f4-a8d4-ecbe34729bb3`; notificação em `…1e4d-4bd9-ba61-23c647249616` **[C]** `e/h/c/n/m0.java`.
  Há outros UUIDs definidos no mesmo arquivo (`1d14d6ee-…`, `f7bf3564-…`, `984227f3-…`) que não são usados pelos comandos `k0`. O serviço `5833ff01-…` é de OTA (`com/hsr/sslight/ui/module/OTA/ST17H66`): **não usar**.
* MTU: o app pede 247 (`e/h/c/n/v3.java`). Usa `v3.b = MTU-7` (padrão 16) como tamanho de bloco ao fatiar dados de pixel/arquivos.

### Cabeçalho A (0xAA): quase todos os comandos  **[C]** `m0.java` classe `c`, `k0.java`
```
AA  cmd  len  payload[len]  chk
chk = (soma de todos os bytes anteriores, incluindo o AA) & 0xFF
```
Inteiros de 2 bytes são **big-endian** (`e.g.a.c.a.s0()`). Inteiros de 4 bytes também são BE (`y3/a.a()`).

### Cabeçalho B (0xBB): "CmdHead_B"  **[C]** `m0.java` (fluxo confirmado no bytecode, `bad/m0c.java`)
* Se `cmd == 0x01` (classe `r0`): o quadro é **só `BB` + payload**, sem cmd, sem tamanho e sem checksum.
  O app usa isso para mandar, a cada ~10 ms, o **nível do microfone do celular**: `BB <nivel 0-100>` (`e/h/c/q/r2/o.java`, `e/h/c/q/d3/n/a.java`). Só é usado quando o dispositivo declara musicMode = 1 (TLV 8 das informações do dispositivo).
* Senão (classe `h1`, cmd 0x33, transferência de arquivo GIF): `BB cmd len(4 bytes BE) payload BB`. O último byte é o próprio 0xBB, **não é checksum**.
* Respostas BB: `BB cmd len(4) payload`. O app não confere checksum nelas (`bad/com.hsr.sslight.ble.BleModel.java`, `onNotify`).

### Notificações  **[C]** `bad/com.hsr.sslight.ble.BleModel.java` (onNotify)
`AA cmd len payload chk`: o app confere `chk` = soma de `bytes[0..len+2]`. Ele entrega o payload à classe registrada para aquele `cmd` (lista em `BleModel.java` ~l.430-520): m1(01), v1(06), w1(07), i1(09), n1(0B), j1(A0), k1(0A), o1(0C), d1(E0), e1(0F), além de outras que entram conforme a tela aberta.

### Codificação de cor em 1 byte (pixel/DIY por LED)  **[C]** `e/h/c/q/w2/c.java` `c()`/`d()`
* `0..180` = matiz/2 (cor saturada; matiz 0-360 → 0-180)
* `255` = branco (saturação < 0,1) · `254` = apagado/preto · `253` = cor especial `R.color.color_button2` (provavelmente branco quente) **[I]**
* Em produtos "frio/quente", o byte vira saturação mapeada para 250..0.
* Alguns produtos usam a variante RGB (3 bytes) dos mesmos comandos (flag `RGB_ColorBoard==1`).

### Anúncio BLE (identificação do produto)  **[C]** `com/hsr/sslight/app/DeviceStore.java`
Manufacturer data (AD 0xFF) = `04 05 PID(4 bytes BE) flags …`; flags bit0 = ligado, bit4 = suporta DIY.
O PID define a UI, a lista de cenas e o número de LEDs (`ProductInfoProvider`).
Se o anúncio não tiver `04 05`, o aparelho é tratado como "compat" e identificado pelo nome do modelo: BSL1/2/17/23 → categoria 0, BSL5 → G40, BSL4 → morango, … (`ProductInfoProvider.java` l.482-489). **BSL11 não aparece nessa tabela**, então o produto é identificado pelo PID do anúncio.

---

## 1. Tabela de comandos (app → dispositivo)

Classe em `e/h/c/n/`. "Q" = consulta (payload vazio, com resposta).

| cmd | classe | payload | Significado / tela que envia | Exemplo |
|---|---|---|---|---|
| 00 | l1 | vazio · ou `00 pwd…` (senha) | Info do dispositivo / login com senha. `t3.java`: sempre a 1ª coisa após conectar (com senha se houver). [C] | `AA 00 00 AA` |
| 01 | m1 | vazio | Estado (ver §3). Enviado ao conectar (`t3.c()`). [C] | `AA 01 00 AB` |
| 02 | q2 | `01`/`00` | Liga/desliga. MainActivity, MainGroupActivity. [C] | `AA 02 01 01 AE` / `AA 02 01 00 AD` |
| 03 | l2 | sub `00`: branco: `00 brilho(2) temp(2) modo(1) vel(1)` | Modo branco quente/frio (`e/h/c/q/l3/v.java`, `l3/r.java`). modo: 0 = estático, 1 = gradiente, 2 = strobe (`x3`/`i3`); vel = 6-x (escala 1..5). brilho 0-1000. [C] | `AA 03 06 00 03 E8 03 E8 00 05 8E` |
| 03 | l2 | sub `01`: `01 H(2) S(2) V(2)` | Cor HSV: H 0-360, S e V 0-1000. Aba "Light". [C, já testado] | `AA 03 07 01 00 F0 03 E8 03 E8 7B` (azul) |
| 03 | l2 | sub `02`: `02 N brilho(2)` | Cena/efeito pré-definido N, brilho 0-1000 (app = %×10). Scene_List, `e/h/c/q/b3/y0.java`, `d3/o.java`. [C, testado] | `AA 03 04 02 05 03 E8 A3` |
| 03 | l2 | sub `03`: `03 (modo<<4 \| auto) sens brilho(2) H(2) S(2)` | Música pelo microfone do aparelho (`e/h/c/q/b3/r0.java`, `r2/q.java`). modo = índice da tela (+4 se o TLV8 musicMode for 1 ou 3); auto 0/1; sens 0-100; brilho 0-1000; H 0-360; S 0-1000. [C] | `AA 03 0A 03 10 32 03 E8 00 00 03 E8 D2` |
| 04 | b2 | `segundos(4 BE) ação(1)` | Contagem regressiva; ação 1 = ligar, 0 = desligar (`e/h/c/q/m2.java`). A resposta traz os segundos. [C] | 1 h até desligar: `AA 04 05 00 00 0E 10 00 D1` |
| 05 | c2 | `unix(4 BE) sinal(1: 1=+,0=−) offsetMin(2)` | Acerta o relógio. Enviado ao conectar, inclusive em grupo (`MainGroupActivity`). [C] | `AA 05 07 69 20 1F 80 00 00 B4 92` |
| 06 | v1 | Q: vazio · set: 4 bytes do timer | Timers 1-4 (consulta: resposta de 16 bytes = 4 timers). Também grava qualquer timer (o índice vai no próprio timer). `ui/timing/SettingTimingActivity.java`, `e/h/c/q/k3/k.java`. [C] | `AA 06 00 B0` |
| 07 | w1 | vazio | Consulta timers 5-8 (16 bytes). [C] | `AA 07 00 B1` |
| 09 | i1/n3 | vazio | Bateria: resposta `maj min nível%`. [C] | `AA 09 00 B3` |
| 0A | k1 / d2 | Q vazio · set `N` | **"Number of LED address" / "Device in series"**: quantos módulos de `One_Serial_Number` LEDs (25 por padrão) há encadeados **no mesmo controlador**. Resposta Q: `atual(1-based) máximo`. Total de LEDs = N × One_Serial_Number. `ui/settings/DeviceInSeriesActivity.java`. [C] | `AA 0A 00 B4`; `AA 0A 01 02 B7` |
| 0B | n1/p3 · o2 | Q: `00` (n1) ou `00 00` (p3) · set `01 m` | Modo de energia: m 0 = economia (SAVING), 1 = normal (POWER). Resposta `x m`. `e/h/c/q/h2.java`. [C] | `AA 0B 01 00 B6`; `AA 0B 02 01 00 B8` |
| 0C | p2 / u2 / o1 | set `vel` · Q vazio | **Velocidade do efeito** 1-100 (barra `SetSpeedView`, máx 100; Scene4/7 enviam progresso+1). Resposta Q: `vel`. `e/h/c/q/a3/s.java`, `h3/q.java`, `h3/r.java`, `SceneGifCommonActivity`. [C] | `AA 0C 01 32 E9` (50); `AA 0C 00 B6` |
| 0D | f2 | `num 01 vel dir(=1) brilho modo estado` | DIY1 (blocos), configuração. vel 1-100, brilho 0-100, modo 1 = Flow, 2 = Jump, 3 = Breathe, 4 = Static (`bad/…Diy1Activity.java`). estado: 0 = início/preview, 1 e 2 = enviados em sequência ao salvar/rodar, 3 = apagar (`e/h/c/q/b3/v.java`). [C nos valores; I no sentido de 1/2] | `AA 0D 07 01 01 32 01 64 01 00 58` |
| 0D | e2 | `num 0F blocoIni blocoFim R G B` | DIY1: cor de uma faixa de blocos (1-based; 20 blocos por padrão, `DiyModel.createDefaultNew`). Blocos vizinhos da mesma cor são agrupados. [C] | blocos 1-5 vermelhos: `AA 0D 07 01 0F 01 05 FF 00 00 D3` |
| 0E | h2 | `num 01 vel brilho modo estado` | DIY2 (gradiente de 3 a 6 cores). modo 1 = Jump, 2 = Breathe (`Diy2Activity.java`). estado como no 0D. [C] | `AA 0E 06 01 01 32 64 02 00 58` |
| 0E | g2 | `num 04 RGB×3` / `num 05 RGB×3` | DIY2: cores 1-3 (sub 04) e 4-6 (sub 05); faltantes = 000000. [C] | `AA 0E 0B 01 04 FF 00 00 00 FF 00 00 00 FF C5` |
| 0F | e1 | Q vazio · set `01`/`00` | **Habilita/desabilita o controle IR**. Resposta `enable`. `e/h/c/q/h2.java` `l()`. [C] | `AA 0F 01 01 BB` / `AA 0F 01 00 BA` / Q `AA 0F 00 B9` |
| 11 | n2 | `01` = pausa, `00` = continua | **Pausa do efeito** (botão ⏸ do `widget/SetSpeedView.java`). [C] | `AA 11 01 01 BD` / `AA 11 01 00 BC` |
| 12 | i2 | `brilho 0-100` | Brilho de cena DIY/GIF/loop (`b3/v.java`, `scene_loop_list_Fragment`). [C] | `AA 12 01 32 EF` |
| 13 | t0 | `00` | Desligamento da caixa de bateria (modo de baixo consumo). **NÃO ENVIAR**: depois o BLE some e só o controle remoto religa (string `batteryboxshutdown_tips2`). [C] | — |
| 14 | v2 | Q · set `val(2)` | Limite de corrente (modo de fábrica `FactoryPattern_Set_dimming`). **NÃO ENVIAR**. [C] | — |
| 15 | t2 | Q · set `PID(4)` | Grava o PID do produto (fábrica, `FactoryPattern_Set_PID`). **NÃO ENVIAR**: muda a identidade do aparelho. [C] | — |
| 16 | v0 | Q · set `1 byte` | Resposta de 3 bytes; usado em `MainCombinationActivity`/`o1/i.java` (função de produto específico). [C/I] | `AA 16 00 C0` |
| 17 | u0 | Q | Calibração de música (fábrica): 10 valores de 16 bits LE. [C] | — |
| 18 | w0 | vários | "Mural" (quadros de LED), por zona: `num H(2) S V vel stop modo [cores]`. [C] | — |
| 19 | y1 | `00` = desliga · `01 tempo bitmap…` | **Loop de cenas favoritas**. bitmap: bit i = cena i+1 (8 por byte, LSB primeiro). `ui/scene/More/MoreBottomDialog.java`. "tempo" = `f1348d.b` (intervalo por cena) [I]. | cenas 1-5, 10: `AA 19 04 01 0A 1F 00 F1`; off `AA 19 01 00 C4` |
| 20 | f3 | `idx total modo` **ou** `idx total modo ledOffset(2) ledTotal(2)` | **"SplicingSerialNumber": posição do aparelho num grupo** (ver §2.7). `MainGroupActivity.g()`. [C] | ver §2.7 |
| 30/31/32/33 | e3/g1/r2/h1 | arquivos | Sistema de arquivos para GIF/DIY/imagem (consulta/adição/apagamento, dados em 0x31 ou BB 0x33). r2 (0x32) tem 13 subcomandos: 1 = toca GIF n(2), 2 = loop de cenas `en cnt (n+100)(2)…`, 3 = loop de DIY, 4 = brilho… (`r2.java`). [C] Complexo; não necessário. | — |
| A0 | p1/j1 | `modo(0=AB,1=A,2=B) on` | Luz combinada A/B (produto BWSL1/2). [C] | `AA A0 02 00 01 4D` |
| A5 | r3 | Q · set `estado` | Estrela da ponta da árvore (`ui/main_mode/tree_top_star.java`). [C] | `AA A5 00 4F` |
| A6 | o3 | `00 01 … MTU-8` | Teste de MTU. Inofensivo, mas desnecessário. [C] | — |
| AF | g3 | Q vazio · set `v` | Ganho de brilho (`h2.java`, `ui/settings/LuminanceGain0_100`). [C] | `AA AF 00 59` |
| B0-BA | a1,j3,m3,k3,y0,l3,s0,z0,h3 | ver §2.5 | "AssemblyUnitDiy": DIY por zonas e **por LED**. [C] | ver §2.5 |
| CD | f1 | `n itens…` | Estado de emenda (joint) e espelhamento: cortinas/matrizes. [C] | — |
| CE | c1 | Q | Depuração de fábrica. [C] | — |
| CF | d3 | vazio / `x` | **RESTAURAR PADRÃO DE FÁBRICA** (log "恢复出厂设置"; `DeviceInfoActivity`). Apaga a senha. **NÃO ENVIAR**. [C] | — |
| D0 | w2 | `dir brilho vel tipo` (ou 3 bytes alt.) | Modo de "imagem DIY": dir 0 = estático, 1 = cima, 2 = baixo, 3 = esq., 4 = dir., 5 = flash, 6 = respiração; vel 0-100; tipo 0 = imagem fixa, 2 = dinâmica, 4, 7 = animação de vários quadros (`DiyGlobalPictureConfig.java`, `s3/c.java`). [C nos campos, I no significado do tipo] | `AA D0 04 00 64 32 00 14` |
| D1 | x2 | `idx(2) cor(1)` ou `idx(2) R G B` | **Pinta 1 LED em tempo real** (idx 0-based). `ui/diy_picture/CanvasImpl.sendCmd*`. [C] | LED0 vermelho: `AA D1 03 00 00 00 7E`; LED9 RGB: `AA D1 05 00 09 FF 00 00 88` |
| D3 | a3 | texto | Texto DIY (matriz). [C] | — |
| D4/D8/D9/DB/DC/DD | z2/s2/x1/q3/j2/b3 | — | Texto/cortina/partes (produtos matriz/cortina). [C] | — |
| D6 | t1 | `cor(1)` ou `R G B` | **Preenche todos os LEDs com uma cor** (254 = apaga a tela). `DiyLampBeadsCanvasView.sendDyeingCanvasCmd`. [C] | `AA D6 01 00 81` (vermelho); `AA D6 01 FE 7F` (apaga) |
| D7 | c3 | `quadro op` | Controle de quadros da animação DIY (op 0 = início, 2 = fim/próximo) (`s3/c.java`). [I] | — |
| DA | y2 | `quadro [idx(2) cor(1)]…` ou `quadro [idx(2) R G B]…` | **Dados de pixel em lote** para um quadro (fatiados em `(MTU-8)/5` LEDs). `s3/c.java`, `ChristmasCanvasHelp`. [C] | — |
| E0 | d1 | Q vazio · set `00` normal / `01` invertido | "Device flip": inverte o sentido da fita. `h2.java k()`. [C] | `AA E0 01 01 8C`; Q `AA E0 00 8A` |

Observações:
* O `f()` de cada classe só diz ao app se ele deve esperar resposta (-1 = não espera). Não aparece no fio.
* O número DIY (`num`) é o índice 1-based entre os DIYs do mesmo tipo salvos no app (`e.g.a.c.a.u()`).

---

## 2. Pontos pedidos

### 2.1 Velocidade de efeito  [C]
`AA 0C 01 <1-100> chk`. A consulta `AA 0C 00 B6` devolve `AA 0C 01 <vel> chk`. Vale para cenas (sub 02 do 0x03), DIY de imagem etc.
Para DIY1/DIY2 a velocidade vai dentro do 0x0D/0x0E. No branco (0x03 sub 00) é um campo de 1 byte (6-x).
Ex.: `AA 0C 01 0A C1` (vel 10) · `AA 0C 01 64 1B` (vel 100).

### 2.2 Pausa  [C]
`AA 11 01 01 BD` pausa; `AA 11 01 00 BC` continua (`widget/SetSpeedView.java`). Ao mexer na barra de velocidade, o app volta ao estado "tocando".

### 2.3 Nomes dos efeitos pré-definidos
* **Não há nomes em texto no APK.** As cenas aparecem como miniaturas GIF numeradas. A lista é **baixada por produto** de `https://hellofairyapp.s3.amazonaws.com/<PID>/Scene_Info.json` (ou `inParallel_<id>/Scene_Info.json` em grupo); os arquivos ficam em `files/Scene_show_res/<res>/Scene_<N>.gif`. Ver `com/hsr/sslight/ui/scene/DownloadScenePictures/DownloadScenePicturesUtils.java` l.270-300 e `e/h/c/q/b3/y0.java j()`. [C]
* A quantidade de cenas que o aparelho suporta vem nas informações do dispositivo, **TLV 3 "CMD_03_Scene_num"** (padrão 20 quando ausente) (`l1.java`, `s3/d.java`). [C]
* Produto padrão/genérico (PID 0 ou desconhecido): 6 cenas com IDs 1, 2, 3, 5, 6, 4 e imagens `R.mipmap.scene01..07` (`ProductInfoProvider.java` l.490-494). [C]
* Alguns PIDs têm listas fixas no código, por exemplo 31031: 1, 8, 9, 10, 11, 12, 19; 32032: 1-20 (`ui/scene/Scene_List.java`). [C]
* `strings.xml` só traz os nomes dos modos DIY (Static, Breathe, Jump, Flow) e do branco (Static, Gradient, Jump). [C] `res-hf/resources/res/values/strings.xml`
* Para descobrir os efeitos do BSL11: ler o PID no anúncio BLE (manufacturer data `04 05 PID…`) e varrer N = 1..(TLV3) com `AA 03 04 02 N 03 E8`. [I]

### 2.4 DIY multicor (efeito customizado)  [C]
**DIY1 (blocos, cmd 0x0D)**: a fita é dividida em 20 blocos (padrão do app).
1. `AA 0D 07 num 01 vel 01 brilho modo 00 chk` (configuração, estado 0)
2. Para cada faixa contínua da mesma cor: `AA 0D 07 num 0F ini fim R G B chk` (blocos 1-based)
3. `… estado 01` e depois `… estado 02` (fim/ativar)
4. Apagar: `AA 0D 07 num 01 00 01 brilho 00 03 chk`

Modo (transição): 1 = Flow/corrida, 2 = Jump/salto, 3 = Breathe/respiração, 4 = Static. vel 1-100; brilho 0-100.
Exemplo arco-íris (blocos 1-4 vermelhos, 5-8 verdes…, num 1, Flow, vel 50, brilho 100):
`AA 0D 07 01 01 32 01 64 01 00 58` → `AA 0D 07 01 0F 01 04 FF 00 00 D2` → `AA 0D 07 01 0F 05 08 00 FF 00 DA` → … → `AA 0D 07 01 01 32 01 64 01 01 59` → `AA 0D 07 01 01 32 01 64 01 02 5A`.

**DIY2 (gradiente, cmd 0x0E)**: até 6 cores.
`AA 0E 06 num 01 vel brilho modo estado`, depois `AA 0E 0B num 04 R1G1B1 R2G2B2 R3G3B3`, `AA 0E 0B num 05 R4…R6`, e estado 1 e 2. modo 1 = Jump, 2 = Breathe.

Código: `e/h/c/q/b3/v.java` (envio ao tocar na lista), `ui/diy/Diy1Activity.java`, `Diy2Activity.java`, `e/h/c/n/e2,f2,g2,h2.java`.

### 2.5 Controle por LED / segmento / "pixel"  [C]
Depende do produto aceitar DIY (flag bit4 do anúncio, `DIY_Type` nas informações do dispositivo, `DiyGlobalPictureConfig.isSupportDiy`). **Testar no BSL11.**
* **1 LED**: `AA D1 03 idxH idxL cor chk` ou `AA D1 05 idxH idxL R G B chk` (idx 0-based).
* **Todos**: `AA D6 01 cor chk` / `AA D6 03 R G B chk`.
* **Lote por quadro**: `AA DA len quadro [idxH idxL cor]…` ou `[idxH idxL R G B]…`. Animação com vários quadros (`e/h/c/n/s3/c.java d()`): `D0(dir,vel,tipo=7)`, `D7(1,0)`, `D0(…,0)`, depois para cada quadro i: (i>0: `D7(i,2)`, `D7(i+1,0)`) e `DA` com os pixels; no fim `D7(n,2)`. [C fluxo; I semântica de D7]
* **AssemblyUnitDiy (zonas)** (`com/hsr/sslight/AssemblyUnitDiy/data/DiyGlobalPartsConfig.java`):
  * B0 `a1` entra no modo e informa o total de LEDs: `ledNum(2) x 00` (ou matriz `Y X x 01`).
  * **B5 `y0`: `ini(2) fim(2) cor…` = cor por LED em lote** (fatiado pelo MTU). Ex. `AA B5 08 00 00 00 04 00 3C 78 FF 1E` (LEDs 0-3 = vermelho, matiz 120, matiz 240, branco).
  * B9 `z0`: `zona ini(2) fim(2) cor…` (pixels de uma zona). B2 `m3`: seleção dos LEDs de uma zona (`zona matiz/2 qtd bitmap…`). B3 `k3`: modo da zona `zona modo vel brilho cena/dir stop`. B6 `l3`: liga/desliga por zona `[on]×zonas`. BA `h3`: brilho por zona. B8 `s0`: animação da zona. B1 `j3`: `a b 00 00`.

### 2.6 Timer / agenda  [C] `e/h/c/n/r1.java`, `v1.java`, `w1.java`, `b2.java`
Formato de 4 bytes por timer:
* b0: bit0 = repetir; bits1..7 = Seg..Dom
* b1: hora · b2: minuto
* b3: bit0 = ação (1 liga, 0 desliga), bit1 = habilitado, bit3 = (padrão 1), bits4-6 = índice 0-7, bit7 = já executado

Consultas: `AA 06 00 B0` (1-4) e `AA 07 00 B1` (5-8). Gravar: `AA 06 04 b0 b1 b2 b3 chk`.
Ex.: timer 0, todo dia às 18:00, liga e habilitado: `AA 06 04 7F 12 00 0B 50`.
Contagem regressiva: `AA 04 05 seg(4) ação chk`.
O relógio é acertado com 0x05 ao conectar (o app faz isso sempre).

### 2.7 Grupo / sincronia de vários aparelhos (importante para as 3 fitas)  [C] `com/hsr/sslight/ui/MainGroupActivity.java` (`g()`, `bad/…MainGroupActivity.java` l.620-632), `e/h/c/q/t2/m.java`, `t2/t.java`, `ui/diy_picture/CanvasImpl.java`
* **Não existe protocolo de rádio entre as fitas.** O app **conecta-se a todas ao mesmo tempo** e cada comando é enviado a toda a lista de MACs (`BleModel.i(List<mac>, cmd)`). Ao conectar cada uma, manda `AA 01 00` (estado) e 0x05 (relógio).
* Há 2 tipos de grupo:
  * `b=0` "grupo" comum (`CreateGroupBottomDialog`): todas fazem o mesmo efeito em paralelo.
  * `b=1` "**Extend**"/ordenado (`GroupSortBottomDialog`, string `extend_sorting_tips`: "ordene conforme a disposição real das fitas, ① é a do início"): **efeito contínuo em sequência**.
* Após conectar, o app envia a cada aparelho o **0x20 (f3)**:
  * forma curta (só para o PID 11400843): `AA 20 03 idx total modo chk`
  * forma longa (demais): `AA 20 07 idx total modo ledOffset(2) ledTotal(2) chk`
  * idx = posição 0-based na ordem do grupo; total = nº de aparelhos (em Extend conta só os conectados); modo = 1 se Extend, 0 se grupo comum; ledOffset = soma dos LEDs dos aparelhos anteriores; ledTotal = soma de todos (Led_Num do ProductInfo de cada um).
* Exemplo para 3 fitas de 50 LEDs em Extend:
  * fita ①: `AA 20 07 00 03 01 00 00 00 96 6B`
  * fita ②: `AA 20 07 01 03 01 00 32 00 96 9E`
  * fita ③: `AA 20 07 02 03 01 00 64 00 96 D1`

  Depois, mandar o mesmo efeito (ex. `AA 03 04 02 N 03 E8`) às três. Pela lógica, o firmware desenha só o seu trecho [offset, offset+n) de um efeito com `ledTotal` LEDs. [I: comportamento do firmware não testado; confirmar a contagem real de LEDs, ver 0x00 bytes 20-21 e 0x0A]
* A sincronia do tempo depende de os comandos chegarem quase juntos (não há "start at timestamp"). Para começar alinhado, mandar o efeito às três em sequência rápida e, se preciso, usar pausa/continua (0x11) em todas. [I]
* Diferente disso, o **0x0A "Device in series"** vale para módulos encadeados fisicamente **num único controlador** (N × 25 LEDs), não para várias fitas BLE.

### 2.8 Música  [C]
* Microfone do aparelho: `AA 03 0A 03 …` (§1).
* Microfone do celular: `BB <0-100>` a cada ~10 ms (cabeçalho B, sem checksum). Só se o TLV 8 = 1.

### 2.9 IR  [C]
`AA 0F 01 01 BB` (liga) / `AA 0F 01 00 BA` (desliga) / `AA 0F 00 B9` (consulta → `AA 0F 01 <en> chk`).

### 2.10 Número de LEDs  [C]
* Leitura: info do dispositivo (0x00), bytes 20-21 `led_allNum`, byte 24 `One_Serial_Number` (LEDs por módulo).
* Ajuste: 0x0A (múltiplos de One_Serial_Number), só quando Device_Type = 0 e DIY_Type = 1 o app recalcula o total.
* No modo de zonas, B0 informa `ledNum`.

---

## 3. Respostas / notificações

### 0x01 estado (`e/h/c/n/m1.java`) [C]
payload: `cd(3 bytes BE: contagem regressiva em s) on(1) modo(1) dados…`
* modo 1 (HSV): `H(2) S(2) V(2)` (S e V 0-1000)
* modo 2 (cena): `N(1) brilho(2)` (0-100; o app multiplica por 10)
* modo 3 (música): `(modo<<4\|auto) sens brilho(2) H(2) S(2)`
* modo 0 (branco, payload de 11 bytes): `brilho(2) temp(2) modo vel`

No pacote completo: s[6] = on, s[7] = modo, s[8…] = dados (bate com `fairy.py`).

### 0x00 info do dispositivo (`e/h/c/n/l1.java`, `s3/d.java`) [C]
* bytes 0-4: versão FW ASCII ("2.0.0")
* bytes 5..(primeiro 0x00): modelo ASCII ("BSL11")
* se o payload tiver mais de 20 bytes:
  * [20-21] led_allNum (BE)
  * [22] Hardware_Serial_Number (módulos em série atuais)
  * [23] HW_Serial_MAX
  * [24] One_Serial_Number (LEDs por módulo)
  * [25] Device_Type
  * [26] DIY_Type
  * [27] nº de TLVs, a partir de [28]:
    * 1 = tipo (1 B)
    * 2 = suporta loop (0 B)
    * 3 = nº de cenas (1 B)
    * 4 = nº de partes + cena das partes (2 B)
    * 7 = câmera (0 B)
    * 8 = musicMode (1 B)
    * 9 = info de cena DIY (a, b, int32)
    * 10 = FW_NUM (13 chars)
* Exceção no código: FW 1.0.0 + BMSL64 com 50 LEDs → o app usa 25.

### Outras respostas [C]
* 0x06/0x07: 16 bytes = 4 timers.
* 0x09: `maj min bateria%`.
* 0x0A: `atual max`.
* 0x0B: `x modo`.
* 0x0C: `vel`.
* 0x0F: `en`.
* 0xE0: `00` = normal.
* 0xAF: ganho.
* 0xA5: estado da estrela.
* 0x04: segundos (4 B).
* 0x15: PID (4 B).

---

## 4. Riscos: NÃO ENVIAR
| cmd | motivo |
|---|---|
| **CF** (d3) | Restaura o padrão de fábrica (apaga senha e configurações). |
| **15** (t2) set | Regrava o PID: o app passa a ver outro produto. |
| **14** (v2) set | Limite de corrente (fábrica): pode sobrecarregar ou escurecer. |
| **13** (t0) | Desliga a caixa de bateria; o BLE some e só o controle remoto religa. |
| **00** com senha / telas de senha (`PasswordSet`) | Criar senha trava o acesso (só sai com reset). |
| **30/31/32/33** (arquivos) | Escreve na flash. Evitar sem entender bem. |
| **0A** set | Muda o nº de LEDs endereçados; reversível, mas pode estragar efeitos. Anotar o valor atual antes. |
| **17/CE**, telas `factory_pattern/*` | Fábrica/depuração. |
| **OTA** (serviço 5833ff01, `ui/module/OTA/ST17H66`) | Atualização de firmware: risco de inutilizar o aparelho. |
| Renomear | Não há comando de renomear nos comandos `k0`; o nome é guardado só no app (`n0.java`, SharedPreferences `SP_MAC`). |

Seguros para testar: 00, 01, 02, 03, 04, 05, 06/07 (consulta), 09, 0A/0B/0C/0F/E0/AF/A5 (consultas), 0C set, 11, 12, 19, 0D/0E (DIY), 20, D1/D6/DA/B5 (se suportados).
