# Primeira revisão real de câmpus e centros

Conferência de 16 de outubro de 2026, sobre o código identificado em
[`capturas.json`](capturas.json). Foram geradas prévias das páginas institucionais
atuais, conferidos os campos e registradas decisões técnicas assistidas para os
sete câmpus e os sete centros. As decisões estão disponíveis para revisão no PR;
não representam aprovação humana nem autorização de publicação.

| Dataset | Candidatos | Decisões aprovadas | Pendentes | Inconsistências de cobertura |
| --- | ---: | ---: | ---: | ---: |
| Câmpus | 7 | 7 | 0 | 0 |
| Centros | 7 | 7 | 0 | 0 |

Os dois relatórios permanecem `publicavel: false`. A cobertura conferida corresponde
às sete unidades de cada índice; não certifica a atualidade institucional de todos
os campos, os departamentos ou os cursos. `data/` continua sem snapshot.

## Arquivos e captura

- `capturas.json`: URLs solicitadas e finais, horário UTC com fuso, HTTP status,
  tipo de conteúdo, resultado da validação TLS, tamanho e SHA-256 das sete fontes.
- `campi-previa.json` e `centros-previa.json`: saídas dos coletores existentes.
- `campi-decisoes.json` e `centros-decisoes.json`: decisões por ID e impressão,
  com justificativas e evidências específicas.
- `campi-revisao.json` e `centros-revisao.json`: relatórios finais gerados pelos
  comandos de revisão, sem captura anterior.

Os originais estão em `capturas/`, ignorado pelo Git. Há páginas de apoio que
contêm contatos pessoais fora do escopo desta API; esses conteúdos não foram
transcritos para as prévias, decisões ou relatórios. O manifesto registra a
obtenção via HTTPS e permite conferir os bytes guardados localmente. Ele não é
uma assinatura da UEM e não comprova, por si só, a autenticidade institucional.

Um clone do repositório contém os resultados e as referências, mas não os
originais. A reprodução exata do parsing exige as capturas locais com os hashes
registrados. Uma nova consulta às URLs pode retornar conteúdo diferente e deve
formar outro lote, com novos horários e hashes.

## Conferência dos campos

### Câmpus

A [página principal](https://www.uem.br/a-uem/campus) confirma a sede em Maringá
e o conjunto de seis municípios regionais. Os nomes, siglas e vínculos com cada
município também foram confrontados com as fontes abaixo. A grafia `Câmpus` e os
IDs são escolhas locais da [regra da uemAPI](../../docs/campus-identifiers.md).

| ID | Conferência e decisão |
| --- | --- |
| `sede` | Maringá consta no parágrafo institucional. A estrutura multicampi da página 17 do relatório apresenta a sede sem sigla. Mantidos `sede` como ID interno e `sigla: null`, sem concluir que inexiste outra sigla institucional. |
| `crc` | Nome e sigla conferidos nas páginas 8 e 17 do relatório e no glossário. Cianorte consta na lista de municípios e no nome da unidade. |
| `crg` | Nome e sigla conferidos nas páginas 8 e 17 do relatório e no glossário. Goioerê consta na lista de municípios e no nome da unidade. |
| `car` | O relatório usa a forma canônica regional e o glossário a associa a Cidade Gaúcha. A página principal e a PLD usam uma variante sem “Regional”. Mantida a escolha já documentada, com a diferença explícita. |
| `crn` | Nome e sigla conferidos no relatório e no glossário. A Carta de Serviços situa a unidade em Diamante do Norte. A página principal escreve “Diamante de Norte”; mantida a normalização documentada. |
| `cau` | Nome e sigla conferidos nas páginas 8 e 17 do relatório e no glossário. Umuarama consta na lista de municípios e no nome da unidade. |
| `crv` | Nome e sigla conferidos nas páginas 8 e 17 do relatório. A página de contato do CRV situa a unidade em Ivaiporã. Apenas a localização foi usada como evidência. |

Fontes de apoio efetivamente consultadas e identificadas por hash no manifesto:

- [Base de Dados 2025](https://pld.uem.br/lni/v05-base-de-dados-2024-2025.pdf),
  **ano base 2024**, páginas PDF/impressas 8 (siglas e nomenclaturas) e 17
  (estrutura multicampi). As duas páginas foram extraídas e conferidas visualmente.
- [Glossário da UEM](https://cpr.uem.br/glossario/), primeira página, com entradas
  de CRC, CRG, CAU, CAR e CRN; ela não foi usada como comprovação de CRV.
- [Carta de Serviços do CRN](https://cpr.uem.br/index.php/pesquisar-carta/3547-gre-crn).
- [Contato do CRV](https://crv.uem.br/contato).
- [Índice de câmpus regionais da PLD](https://pld.uem.br/dvl/regulamentos/campus-regionais),
  usado para confrontar a variante do Arenito; essa página lista somente três
  entradas e não foi tratada como inventário completo dos seis regionais.

Para todos os câmpus, `endereco` permanece `null` e `status` permanece
`desconhecido`. A conferência não usa o relatório histórico para afirmar que uma
unidade está ativa hoje. A diferença entre `Campus` nas fontes e `Câmpus` na
prévia segue a convenção local, sem alteração da identidade da unidade.

### Centros

No [índice atual da PLD](https://pld.uem.br/dvl/regulamentos/centros-de-ensino),
foram conferidos os sete rótulos e seus respectivos `href`: CCA, CCB, CCE, CCH,
CCS, CSA e CTC. Cada nome da prévia corresponde ao texto do link, retirando
somente a sigla inicial e o sufixo de departamentos e órgãos. Os IDs correspondem
às siglas em minúsculas; os links completos constam na prévia.

A aprovação cobre a correspondência entre os registros e o índice capturado.
O conteúdo das páginas vinculadas, os departamentos, os câmpus e a situação
atual dos centros exigem suas próprias conferências; `status` permanece
`desconhecido`.

## Reproduzir localmente

Execute a partir da raiz do repositório, com o ambiente virtual ativado e os
originais disponíveis em `capturas/`. Confira os hashes antes de executar os
coletores:

```bash
python - <<'PY'
import hashlib
import json
from pathlib import Path

manifesto = Path("reviews/2026-10-16-campi-centros/capturas.json")
for captura in json.loads(manifesto.read_text())["capturas"]:
    arquivo = Path(captura["arquivo"])
    conteudo = arquivo.read_bytes()
    if len(conteudo) != captura["bytes"]:
        raise SystemExit(f"Tamanho divergente: {arquivo}")
    if hashlib.sha256(conteudo).hexdigest() != captura["sha256"]:
        raise SystemExit(f"Hash divergente: {arquivo}")
    print(f"OK: {arquivo.name}")
PY

python -m app.collectors.campi \
  --html reviews/2026-10-16-campi-centros/capturas/campi.html \
  --consultado-em 2026-10-16T15:28:56.372959+00:00 \
  > /tmp/uem-campi-previa.json

python -m app.collectors.centros \
  --html reviews/2026-10-16-campi-centros/capturas/centros.html \
  --consultado-em 2026-10-16T15:29:31.827522+00:00 \
  > /tmp/uem-centros-previa.json

diff -u reviews/2026-10-16-campi-centros/campi-previa.json /tmp/uem-campi-previa.json
diff -u reviews/2026-10-16-campi-centros/centros-previa.json /tmp/uem-centros-previa.json

python -m app.review.previews --dataset campi \
  --atual reviews/2026-10-16-campi-centros/campi-previa.json \
  --decisoes reviews/2026-10-16-campi-centros/campi-decisoes.json \
  > /tmp/uem-campi-revisao.json

python -m app.review.previews --dataset centros \
  --atual reviews/2026-10-16-campi-centros/centros-previa.json \
  --decisoes reviews/2026-10-16-campi-centros/centros-decisoes.json \
  > /tmp/uem-centros-revisao.json

diff -u reviews/2026-10-16-campi-centros/campi-revisao.json /tmp/uem-campi-revisao.json
diff -u reviews/2026-10-16-campi-centros/centros-revisao.json /tmp/uem-centros-revisao.json
```

## Validação executada

- Os sete arquivos originais conferiram em tamanho e SHA-256 com o manifesto.
- A reexecução dos dois coletores e das duas revisões reproduziu os JSON
  registrados byte a byte.
- Cada relatório apresentou sete aprovações válidas, nenhuma decisão obsoleta e
  nenhuma inconsistência de cobertura, mantendo `publicavel: false`.
- Os 39 testes de `test_campi_collector.py`, `test_centros_collector.py` e
  `test_review_previews.py` passaram.
- `ruff check .`, `ruff format --check .` e `git diff --check` passaram.
- `data/` contém somente `.gitkeep`.

## Pendências para publicação

As decisões deste lote devem passar pela revisão do PR. Também continuam
pendentes a revisão das condições de reutilização de cada fonte, a revisão de
departamentos e cursos, a cobertura da EaD, os vínculos comprovados e o mapeamento
persistente dos IDs de cursos. As fontes permanecem candidatas no registro.
Somente o snapshot completo dos quatro datasets poderá ser proposto para
publicação após essas etapas.
