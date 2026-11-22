# Som → cor: como os apps fazem os efeitos de música

Levantado do código dos apps (jadx), 21/11/2026. Serve de base para fazer o modo música pelo notebook
(caminho em PROTOCOLO-gattdemo-mrstar.md, "Música pelo notebook (futuro)").

Há dois jeitos de reagir ao som, nos dois apps:
- **Microfone da própria fita:** o app só escolhe estilo e sensibilidade; quem ouve e decide as cores é
  o firmware da fita. Não dá para ver a regra; só observar.
- **Som do celular (microfone ou música tocando no app):** o app mede o som e manda à fita, várias vezes
  por segundo, o que ela deve mostrar. Essa regra está no código e está descrita abaixo.

---

## Fita GATT--DEMO (MR Star / Lenze Colorful, quadros `BC … 55`)

### Aba "Microfone": microfone da fita (firmware decide)
- `BC 0F 01 01 55` liga o microfone da fita (`00` desliga; o app desliga ao trocar para o microfone do celular).
- `BC 11 01 n 55` estilo: 1 **clássico**, 2 **suave**, 3 **dinâmico**, 4 **disco** (nomes do app:
  classic, soft, dynamic, disco).
- `BC 12 01 s 55` sensibilidade 0-100.
- A relação som → cor de cada estilo está no firmware; ainda não observada. Ao testar, anotar aqui o que
  cada estilo faz no silêncio e com som alto.

### Aba "Microfone", opção microfone do celular (`utils/VoiceDBModule.java`)
A cada **200 ms**:
1. `volume` = amplitude máxima do microfone desde a última leitura (0-32767, linear).
2. Calcula dB (`20·log10(volume)`, suavizado com fator 0,2), mas **não usa** o dB para a cor (só log).
3. `volume = volume × sensibilidade / 500` (sensibilidade = barra 0-100).
4. Cor = `PALETA[volume mod 140]` (paleta abaixo); transparência pretendida = `(volume − 30) × 0,02`.
5. Converte para HSV e manda **`BC 09 06 H(2) S(2) 00 00 55`** (cor do modo música). Não manda brilho.
6. Se R ou G der 0, não manda nada naquela leitura.

Ou seja, **a intensidade do som escolhe a posição no arco-íris**, mas com `mod 140` sobre um valor que
vai até milhares: a cor salta de forma quase aleatória a cada mudança de volume, e não "mais alto = mais
quente". No silêncio, volume ~0 → índice 0 (vermelho), mas o passo 6 descarta: a fita fica na última cor.

### Aba "Música": música tocando no próprio app (`colorful_ui/music.java`)
O app toca um arquivo de música do celular e analisa com o `Visualizer` do Android (~5 capturas/s):
1. **Volume:** `10·log10(média dos quadrados da forma de onda)` (dB, ~0-40).
2. **Frequência dominante:** pico do FFT; `freq = índice_do_pico × taxa / tamanho`.
3. Cor = `PALETA[freq mod 140]`; transparência pretendida = `(volume_dB − 30) × 0,02` (abaixo de 30 dB
   seria transparente, acima mais forte).
4. Manda **`BC 04 06 H(2) S(2) 00 00 55`** (cor fixa) a cada captura.

Ou seja, **o tom (grave/agudo) escolhe a cor e o volume deveria escolher a força**. Na prática a
taxa do Android vem em milli-hertz, então `freq` estoura ou fica enorme e o `mod 140` também embaralha.

### Paleta de 140 cores (`ColorUtils.COLOR_LIST_140`)
Arco-íris contínuo, de 0 a 139:
vermelho (0) → laranja (~20) → amarelo (40) → verde (60) → ciano (80) → azul (100) → magenta (120) →
volta ao vermelho (139). Passo de ~2,6° de matiz por índice.

### Defeitos do app (por que a cor parece aleatória)
- `ColorUtils.argb(a, r, g, b)` espera valores 0-1, mas recebe R, G e B em 0-255: cada canal é multiplicado
  por 255 e transborda para o canal vizinho. A cor que sai não é a da paleta. Simulado
  (`privado/analise/musica_app.py`): índice 20 (laranja) sai com matiz 63; 40 (amarelo) sai 0; 100 (azul) é
  descartado; 139 sai azul (238).
- A transparência (o "volume vira brilho") é jogada fora na conversão para RGB.
- Bytes com sinal (Java) passam direto para a conversão HSV.
- Matiz e saturação são divididos por 255 em vez de 256 (diferença pequena acima de 254).

**Para fazer melhor no notebook:** mesma ideia, sem os defeitos. Por exemplo: graves (batida) → pulso de
brilho (`BC 05`), tom dominante ou centroide do espectro → matiz suave na paleta (`BC 04` ou `BC 09`),
silêncio → cor de base com brilho baixo, sem apagar (o que o usuário pediu para as fitas da árvore).

---

## Fitas da árvore (Hello Fairy, quadros `AA … chk`)

### Microfone da fita (firmware decide)
`AA 03 0A 03 (estilo<<4 | auto) sens brilho(2) H(2) S(2) chk`
- estilos: 1 **Energia**, 2 **Ritmo**, 3 **Rolagem**, 4 **Espectro**.
- auto = 1: a fita escolhe as cores; auto = 0: usa a cor H/S (os 5 botões de cor do app).
- sensibilidade 0-100 (85 ficou boa; 70 pede som alto; 100 fica sempre acesa).
- Observado: Energia **apaga no silêncio**. Ritmo, Rolagem e Espectro: anotar ao testar.
- As animações dos 4 estilos estão em `cenas/musica/`.

### Microfone do celular (`e/h/c/q/d3/n/a.java`, `r2/o.java`)
Só quando o aparelho declara musicMode = 1 ou 3 (TLV 8 das informações do aparelho); nesse caso o app
manda o mesmo `AA 03 0A 03` com **estilo + 4** (os estilos "do celular") e depois, a cada **~10 ms**:
1. Lê um bloco do microfone (44,1 kHz, 16 bits).
2. Nível = maior valor absoluto do bloco (pico), limitado a 0-32767.
3. Converte linear para 0-100: `nível × 100 / 32767`.
4. Manda **`BB <nível>`** (só 2 bytes, sem checksum).

Aqui o app **não escolhe cor nenhuma**: manda só o volume, e a fita aplica o estilo escolhido (como faz
com o próprio microfone). É o formato mais simples para o notebook alimentar as três fitas da árvore,
se o firmware BSL11 aceitar (musicMode do BSL11 ainda não conferido).
