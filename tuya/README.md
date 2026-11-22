# tuya/: descobrir o emissor IR de quem vai usar o projeto

O `ir.py` controla as fitas por infravermelho através de um **emissor IR Tuya** (o "controle universal"
Wi-Fi que o app Smart Life / Tuya usa para ar-condicionado e TV). Para falar com ele direto pela rede de
casa, sem nuvem, o `ir.py` precisa de quatro valores, guardados em `../ir-emissor.json`:

| campo | o que é | de onde vem |
|---|---|---|
| `id` | identificador do aparelho na Tuya (devId / gwId) | nuvem Tuya (login do app) |
| `key` | chave local (local_key, 16 caracteres) que cifra a conversa | nuvem Tuya (login do app) |
| `ip` | endereço do emissor na rede de casa | anúncio do próprio emissor na rede (UDP 6667) |
| `versao` | versão do protocolo local (3.3, 3.4, 3.5) | o mesmo anúncio |
| `control_type` | 1 = emissor antigo (DPs 201/202), 2 = novo (DPs 1-13) | perguntando ao emissor |

## Jeito rápido

```
uv run tuya/chave-emissor.py              # lista os emissores IR da conta e pergunta qual
uv run tuya/chave-emissor.py "IR Sala"    # escolhe pelo nome que aparece no app
uv run tuya/chave-emissor.py --qr         # força novo login por QR
```

Rodar num terminal (o QR aparece na tela), no notebook ligado na mesma rede do emissor:
1. No app Smart Life (ou Tuya Smart): **Eu → engrenagem (Configurações) → Conta e segurança → Código do
   usuário**. Digitar esse código quando o script pedir.
2. Aparece um QR. No app, tocar no leitor (canto superior direito da tela inicial), ler e confirmar.
3. O script acha os emissores IR da conta, procura o escolhido na rede e grava `../ir-emissor.json`.

O login fica em `tuya/segredos.json` e é reaproveitado (e renovado) nas próximas vezes.
Rodar de novo quando o emissor for reconfigurado no app (a **chave muda** a cada novo pareamento) ou
mudar de IP. Testar depois com `uv run ir.py ligar` (as fitas da árvore devem acender).

## Como cada valor foi descoberto (e por que deste jeito)

Caminho levantado em out/2026 e confirmado em 21/11/2026.

### Chave local e id: login por QR do app (sem conta de desenvolvedor)
- A chave nunca passa pela rede local de forma legível: capturar tráfego (roteador, MikroTik) não serve.
  Ela só sai da nuvem Tuya.
- O caminho "oficial" (conta de desenvolvedor em platform.tuya.com + `python -m tinytuya wizard`) depende
  do serviço IoT Core, que é um teste grátis que **vence**. Vencido, o `tinytuya.Cloud().getdevices()`
  devolve só uma lista vazia; o erro real (`28841002 IoT Core service subscription has expired`) só
  aparece chamando a API direto. A renovação mandava para o iot.tuya.com, que parou de responder
  (out/2026).
- O que funciona: biblioteca `tuya-device-sharing-sdk`, a mesma da integração Tuya do Home Assistant,
  com o client_id público dela (`HA_3y9q4ak7g4ephrvke`). Login por QR com o "Código do usuário" do app;
  `Manager.update_device_cache()` devolve todos os aparelhos da conta, cada um com `local_key`.
- Na lista, o emissor IR é a **categoria `wnykq`**. Os "controles virtuais" que a pessoa criou no app
  (ar, TV) aparecem como sub-aparelhos (`infrared_ac`, `infrared_tv`…) e trazem a mesma chave do emissor;
  o script usa o próprio emissor. (Gateways Zigbee vêm sem chave; seus filhos trazem a do gateway.)

### Uma chave por aparelho (com exceções)
- Cada aparelho **Wi-Fi independente** (emissor IR, tomada, lâmpada Wi-Fi) tem a **sua** local_key.
- Aparelhos **pendurados num gateway** (Zigbee, Bluetooth mesh) usam a chave do gateway, porque quem fala
  na rede é ele; na lista o gateway costuma vir com a chave vazia e os filhos com a dele (já visto:
  11 sub-aparelhos Zigbee de um mesmo gateway com a mesma chave).
- Os **controles virtuais** do emissor IR (ar, TV criados no app) trazem a chave do emissor.
- A chave **muda quando o aparelho é pareado de novo** (removido e adicionado no app, ou Wi-Fi trocado
  pelo app); a antiga deixa de funcionar. Por isso o script avisa quando a chave mudou.
- Para este projeto só interessa a chave do emissor IR.

### IP e versão: anúncio do emissor na rede
- Todo aparelho Tuya Wi-Fi anuncia a cada poucos segundos, por broadcast UDP nas portas **6666**
  (protocolo 3.1, em claro) e **6667** (3.3+, cifrado com md5("yGAdlopoPVldABfn")). O anúncio traz
  `gwId` (= id), `ip` e `version`.
- O script usa `tinytuya.deviceScan()` (escuta ~20 s) e pega o anúncio cujo gwId é o id do emissor.
- Na nuvem o aparelho tem outro campo `ip`, mas é o IP **público** da casa: não serve.
- Ping pode não responder (o IR Sala nunca respondeu a ping): não usar ping para saber se está vivo.

### control_type: perguntando ao emissor
- O tinytuya (`Contrib.IRRemoteControlDevice`) detecta sozinho, mas isso é uma conversa a mais com o
  emissor e falha se ele demorar; o `ir.py` usa o valor gravado. O "IR Sala" é tipo 1.
- Se a detecção funcionar, a chave também está certa (chave errada dá erro 904 no tinytuya).

## O que já se sabe desses emissores
- Não têm estado: `status()` devolve `None`. Só transmitem.
- Os códigos dos controles virtuais do app ficam na nuvem; para uso local é preciso **aprender** do
  controle físico (`uv run ir.py aprender …`) ou **gerar** o código (as fitas da árvore usam NEC
  endereço 00; ver PROGRESSO.md e `../ir-fitas.json`).
- O "IR Sala" responde de forma **intermitente** na rede local: às vezes some por minutos (o app pela
  nuvem continua funcionando). Não é problema de chave. O `ir.py` tenta de novo a cada uso.
- O emissor precisa "ver" a árvore; o IR também pega por reflexo em parede e teto.

## Arquivos com segredo (chmod 600, não compartilhar)
- `tuya/segredos.json`: login do app (código do usuário e token), gravado pelo script.
  Modelo sem dados reais: `tuya/segredos.json.example` (só para mostrar o formato; não precisa copiar).
- `../ir-emissor.json`: chave local do emissor. Modelo sem dados reais: `../ir-emissor.json.example`.
Os dois ficam fora do git (`.gitignore`).
