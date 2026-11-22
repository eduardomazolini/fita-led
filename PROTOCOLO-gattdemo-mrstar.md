# Fita "GATT--DEMO": protocolo (MR Star / Lenze Colorful)

Aparelho: nome anunciado `GATT--DEMO`, serviço anunciado `0x2022`.
Apps que falam com ela: **MR Star** (`com.frok.mrstar` 1.0.0; código da FINDN) e **Colorful da Lenze**
(`com.lenzetech.jyx` 1.1.6, instalado em 2023). Os dois mandam exatamente os mesmos comandos.
APKs em `privado/apks/`. Fontes: código decompilado (jadx) dos dois apps + github.com/nukemberg/cheap-leds e
github.com/user154lt/GATT--DEMO-Data.

**Nada aqui foi testado na fita ainda.**

## Ligação BLE
- Serviço `0000fff0-…`, escrita em `0000fff3-…` (sem resposta), notify `0000fff4-…`.
- **A fita não devolve estado**: não dá para ler como ela está nem restaurar depois de um teste.
- `5833ff01-…` é OTA de firmware (chip Lenze ST17H66): **não escrever**.

## Formato
`BC <cmd> <tamanho> <dados…> 55`. Sem checksum. Números de 2 bytes em big-endian (alto = v/256, baixo = v%256).
(Em alguns pontos o app usa v/255 e v%255, um erro do app que só faz diferença acima de 254.)

| Cmd | Quadro | Função | Onde no app |
|---|---|---|---|
| 01 | `BC 01 01 xx 55` | liga/desliga. O app manda `00` com o interruptor marcado e `01` desmarcado; o cheap-leds diz que `01` liga e `00` desliga. Confirmar na fita | color.java / AdjustFragment |
| 02 | `BC 02 01 n 55` | ordem das cores do chip: 1 RGB, 2 RBG, 3 GRB, 4 GBR, 5 BRG, 6 BGR (configuração; não mexer à toa) | ColorfulActivity |
| 03 | `BC 03 02 N(2) 55` | número de LEDs da fita (8 a 300) (configuração) | ColorfulActivity |
| 04 | `BC 04 06 H(2) S(2) 00 00 55` | cor fixa: matiz 0-360, saturação 0-1000 | color.java |
| 05 | `BC 05 06 B(2) 00 00 00 00 55` | brilho (barra de 3 a 1000) | color/mode |
| 06 | `BC 06 02 id(2) 55` | efeito pronto (lista abaixo) | mode.java |
| 07 | `BC 07 01 d 55` | sentido do efeito: 0 normal, 1 invertido | mode.java |
| 08 | `BC 08 01 v 55` | velocidade (barra de 0 a 100) | mode.java |
| 09 | `BC 09 06 H(2) S(2) 00 00 55` | cor do modo música (vem do microfone do celular) | VoiceDBModule |
| 0B | `BC 0B 07 ano(2) mês dia h m s 55` | acerta o relógio da fita | TimerUtils |
| 0C | `BC 0C 01 01 55` | ativa os timers | timer.java |
| 0D | `BC 0D 06 01 a e dias h m 55` | timer: a = 1 ligar / 0 desligar; e = 1 ativo / 0 inativo; dias = bits dos dias da semana | timer.java |
| 0F | `BC 0F 01 x 55` | microfone da fita: 1 liga, 0 desliga | mic.java |
| 11 | `BC 11 01 n 55` | estilo do modo microfone (1 a 4) | mic.java |
| 12 | `BC 12 01 n 55` | sensibilidade do microfone (barra) | mic.java |
| 12 | `BC 12 06 H(2) S(2) FF FF 55` | cor em tom de branco ("changClor_02") | color.java |
| 13 | `BC 13 02 v(2) 55` | seletor de branco/temperatura (CustomColorPicker2/ColorView02) | color.java |

## Efeitos (comando 06), nomes do app
O app mostra 1-4, 7, 10, 26, 27, 29-32, 35-62 e 76-93. Os outros números têm nome, mas não aparecem nas abas,
e podem não existir no firmware.

| id | nome |
|---|---|
| 1 | Automatic loop |
| 2 | Symphony |
| 3 | Colorful energy |
| 4 | Colorful jumps |
| 5 | Red-green-blue jumps |
| 6 | Yellow-blue-purple jumps |
| 7 | 7 colors strobe |
| 8 | Red-green-blue strobe |
| 9 | Yellow-purple-blue strobe |
| 10 | 7 colors gradient |
| 11 | Alternate red-yellow gradient |
| 12 | Alternate red-purple gradient |
| 13 | Green-green alternate gradient |
| 14 | Alternate green-yellow gradient |
| 15 | Blue-purple alternating gradient |
| 16 | Red horse racing |
| 17 | Green horse racing |
| 18 | Blue horse racing |
| 19 | Yellow horse racing |
| 20 | Cyan horse racing |
| 21 | Purple horse racing |
| 22 | White horse racing |
| 23 | Colorful chasing light |
| 24 | Red-green-blue follow-up |
| 25 | Yellow-cyan-purple follow-up light |
| 26 | Colorful fluttering |
| 27 | Red-green-blue fluttering |
| 28 | Yellow-cyan-purple fluttering |
| 29 | Colorful brushing |
| 30 | Red-green-blue color brushing |
| 31 | Yellow-cyan-purple color brushing |
| 32 | Colorful brush color brush closed-pull |
| 33 | Red-green-blue color brush closed-pull |
| 34 | Yellow-cyan-purple color brush closed-pull |
| 35 | 7 colors opening-closing |
| 36 | Red-green-blue opening-closing |
| 37 | Yellow-cyan-purple opening-closes |
| 38 | Red opening-closing |
| 39 | Green opening-closing |
| 40 | Blue opening-closing |
| 41 | Yellow opening-closing |
| 42 | Cyan opening-closing |
| 43 | purple opening-closing |
| 44 | White opening-closing |
| 45 | 7 colors light-dark transition |
| 46 | Blue-red-green light-dark transition |
| 47 | Violet-green-yellow light-dark transition |
| 48 | 6 colors light-dark transition red |
| 49 | 6 colors light-dark transition green |
| 50 | 6 colors light-dark transition blue |
| 51 | 6 colors light-dark transition cyan |
| 52 | 6 colors light-dark transition yellow |
| 53 | 6 colors light-dark transition purple |
| 54 | 6 colors light-dark transition white |
| 55 | 7 colors flowing water |
| 56 | Blue-green-red running water |
| 57 | Purple-green-yellow running water |
| 58 | Red-green running water |
| 59 | Green-blue running water |
| 60 | Yellow-blue running water |
| 61 | Yellow-cyan running water |
| 62 | Blue-purple running water |
| 63 | Black-white running water |
| 64 | White-red-white flow |
| 65 | White-green-white flow |
| 66 | White-blue-white flow |
| 67 | White-yellow-white flow |
| 68 | White-green-white flow |
| 69 | White purple-white flow |
| 70 | Red-white-red flow |
| 71 | Green-white-green flow |
| 72 | Blue-white-blue flow |
| 73 | yellow-white-yellow flow |
| 74 | Blue-white-blue flow |
| 75 | Purple-white-purple flow |
| 76 | 7 colors trailing |
| 77 | Red trailing |
| 78 | Green trailing |
| 79 | Blue trailing |
| 80 | Yellow trailing |
| 81 | Cyan tailing |
| 82 | Purple tailing |
| 83 | White trailing |
| 84 | Red running |
| 85 | Green running |
| 86 | Blue running |
| 87 | Yellow running |
| 88 | Cyan running |
| 89 | Purple running |
| 90 | White running |
| 91 | 7 colors running |
| 92 | Blue-green-red running |
| 93 | Purple-cyan-yellow running |
| 94 | Blue-purple-cyan-yellow running |
| 95 | Blue-green-cyan-yellow running |
| 96 | Red dot on white background running |
| 97 | Red background and green dot running |
| 98 | Green background and blue dot running |
| 99 | Yellow dot on the blue background running |
| 100 | Yellow background and blue dots running |
| 101 | Blue background and purple dots are running |
| 102 | White dots running on purple background |
| 103 | Red background and white dots running |
| 104 | 7 colors running with red background |
| 105 | 7 colors running with green background |
| 106 | 7 colors running with blue background |
| 107 | 7 colors yellow background running |
| 108 | Green background 7 colors running |
| 109 | 7 colors running with purple background |
| 110 | 7 colors running on white background |
| 111 | Blue background and green dot running |
| 112 | Red background and green dot running |
| 113 | Red dot on the blue background running |
| 114 | Yellow background and blue dots running |
| 115 | The yellow dots on the purple bottom running |
| 116 | Yellow background and white dots running |
| 117 | Yellow dots on white background running |

## Música pelo notebook (futuro, não implementado)
Ideia registrada em 21/11/2026: a fita reagir ao ritmo da música que toca no notebook (ou ao microfone),
como faz a aba "Música" do app.

**Como o app faz** (`utils/VoiceDBModule.java`): grava o microfone do celular; a cada **200 ms** lê a
amplitude máxima, multiplica pela sensibilidade (`volume * barra / 500`), escolhe uma cor numa tabela de
140 cores (`COLOR_LIST_140[volume % 140]`), com transparência `(volume - 30) * 0,02`, converte para HSV e
manda **`BC 09 06 H(2) S(2) 00 00 55`** (cor do modo música). Ou seja: a fita não analisa nada, só recebe
uma cor nova 5 vezes por segundo. A tela "Música" também manda `BC 04` (cor fixa) ao escolher uma cor.

**Caminho no Linux (PipeWire):**
1. Na mesa de som virtual (qpwgraph/Helvum, ou `pw-link`), criar um nó que recebe **uma cópia** da saída
   do aplicativo que toca música (ou o monitor da saída geral, `<saída>.monitor`), ou a entrada do
   microfone. Ex.: `pactl load-module module-null-sink sink_name=fita_led` e ligar a saída do app nele
   além dos alto-falantes; o script lê `fita_led.monitor`.
2. Script lê esse nó (ex.: `parec`/`pw-record` ou a biblioteca `sounddevice`), calcula a energia por
   bloco (e, para ritmo, detecção de batida por fluxo espectral nas graves).
3. Converte em cor/brilho e manda `BC 09` (ou `BC 04` + `BC 05`) por escrita sem resposta, a ~5-20 por
   segundo, numa conexão mantida aberta.
4. Mesmo caminho serve para as fitas da árvore (Hello Fairy aceita `BB <nível>` a cada ~10 ms, que é o
   modo microfone do celular do app delas; ver PROTOCOLO-hellofairy.md).
