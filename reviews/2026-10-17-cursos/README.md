# Primeira revisão real de cursos presenciais da PEN

Conferência de 17 de outubro de 2026 sobre o código identificado em
[`capturas.json`](capturas.json), após o merge do PR de departamentos. O índice
atual da PEN apresentou **67 entradas presenciais** em seis seções de câmpus.
Foram capturados o índice e seus 67 detalhes, por requisições HTTPS sequenciais.
As 68 capturas retornaram HTTP 200 nas URLs esperadas, com validação TLS.

O consolidado aceitou os 67 detalhes, sem arquivos ausentes, falhas de leitura,
detalhes inválidos ou capturas fora do índice. A conferência dos campos resultou
em **66 decisões técnicas aprovadas e uma pendente**, para Engenharia Agrícola
no Arenito. As decisões estão disponíveis para revisão humana no PR.

| Câmpus no lote | ID local | Entradas / detalhes aceitos | Aprovados | Pendentes |
| --- | --- | ---: | ---: | ---: |
| Sede / Maringá | `sede` | 44 | 44 | 0 |
| Cianorte | `crc` | 4 | 4 | 0 |
| Arenito / Cidade Gaúcha | `car` | 1 | 0 | 1 |
| Goioerê | `crg` | 4 | 4 | 0 |
| Vale do Ivaí / Ivaiporã | `crv` | 3 | 3 | 0 |
| Umuarama | `cau` | 11 | 11 | 0 |
| **Total** | | **67** | **66** | **1** |

`cobertura_completa: true` no consolidado significa apenas que cada entrada
presencial do índice teve seu detalhe aceito e não sobraram capturas no
manifesto. O relatório de revisão mantém `todos_itens_aprovados: false`: há uma
decisão pendente e a inconsistência de cobertura `cursos da EaD não incluídos`.
Todos os resultados permanecem `publicavel: false`.

## Arquivos e proveniência

- `capturas.json`: commit de base, método, URLs, horários UTC com fuso, status
  HTTP, tipo de conteúdo, tamanho e SHA-256 do índice e dos 67 detalhes.
- `cursos-manifesto.json`: associação explícita de câmpus, URL, arquivo local e
  horário de cada detalhe, no formato do coletor consolidado.
- `cursos-indice.json`: prévia das entradas do índice atual, sem captura anterior.
- `cursos-consolidados.json`: prévias acadêmicas, situação de cada captura e
  contagens por câmpus.
- `cursos-decisoes.json`: decisões com justificativas, evidências e impressões
  dos registros e sua proveniência.
- `cursos-revisao.json`: relatório final produzido pelo comando de revisão.
- [`conferencia.md`](conferencia.md): conferência por curso e particularidades
  dos valores apresentados pelas fontes.

Os HTML originais estão em `capturas/`, ignorado pelo Git. As páginas contêm
nomes e contatos fora do escopo desta API; esses campos não foram transcritos
para os arquivos de revisão. O manifesto identifica os bytes obtidos localmente,
sem representar uma assinatura da UEM ou uma autorização de redistribuição.

Um clone contém os resultados e as referências. A reprodução exata do parsing
exige os originais locais com os hashes registrados. Uma nova consulta às URLs
pode produzir conteúdo diferente e deve formar outro lote, com seus próprios
horários, hashes e decisões.

## Escopo da conferência

Os nomes, links e seções de câmpus foram confrontados por uma leitura separada
dos elementos do índice. Os 67 títulos e breadcrumbs dos detalhes também
corresponderam às entradas esperadas. Os campos acadêmicos foram comparados com
uma leitura separada do conteúdo HTML, conservando seus rótulos, separadores e
ordem; a conferência por curso está em `conferencia.md`.

Uma decisão técnica aprovada indica fidelidade aos campos presentes na captura.
Ela não aprova a situação institucional atual, os IDs estáveis, a unidade de
oferta ou os vínculos com centro e departamento. A chave `campus_id|url_detalhe`
é uma chave de revisão, e `id_candidato` continua sendo uma proposta derivada
do nome. A modalidade presencial é inferida da separação entre as seções de
câmpus e a EaD no índice, conforme a proveniência do coletor.

Este lote não transforma cada habilitação, grau ou alternativa de turno em um
curso ou uma oferta independente. Também não completa campos a partir de outros:

- Ciências Biológicas mantém dois blocos e o grau ausente no bloco integral.
- Física na sede e Letras mantêm `turno: null`, com os turnos que aparecem nas
  habilitações preservados nesses textos.
- Letras mantém quatro habilitações e o grau posterior ao prazo de conclusão.
- Música mantém cinco habilitações e cinco graus, sem inferir correspondência
  entre os itens das duas listas.
- Medicina, Zootecnia e Medicina Veterinária mantêm habilitações vazias onde
  não há valor explícito nessa seção. Tecnologia em Gastronomia mantém graus
  vazios, sem preenchê-los a partir da habilitação.
- Estatística mantém `Não se aplica` como habilitação e `Bacharelado` como grau;
  Nutrição mantém `Nutricionista` na habilitação, nos campos apresentados pela PEN.
- Química preserva os valores associados a `TURNOS`, a pontuação e os campos
  com dois-pontos fora do destaque. Prazos permanecem fora da prévia.
- Arquitetura e Urbanismo em Umuarama preserva `(CAU)` no nome do índice e do
  título. A captura acadêmica termina antes da coordenação.

### Decisão pendente: Engenharia Agrícola

O detalhe do Arenito apresenta `Habilitação: Licenciatura` e
`Grau Acadêmico: Engenheiro Agrícola`. A prévia reproduz essa combinação. A
decisão ficou pendente até esclarecer os valores e sua interpretação em uma
fonte adequada. Não foi escolhido um substituto para a habilitação nem alterada
a saída do coletor para corrigir a página por suposição.

### Cobertura ainda pendente

O índice remete a EaD ao
[NEAD](https://portal.nead.uem.br/site/web/site/cursos#graduacao). O link foi
registrado, mas os cursos desse portal não foram capturados nem incluídos no
lote. A ausência de uma seção do CRN na captura da PEN também não comprova
ausência institucional de cursos nesse câmpus. As contagens acima descrevem o
índice consultado, não um total completo de cursos ou ofertas da UEM.

## Reprodução local

Execute a partir da raiz do repositório, com o ambiente virtual ativado e os
HTML originais disponíveis. O código abaixo confere os 68 hashes e reproduz as
saídas do índice, do consolidado e da revisão. Ele lê os arquivos existentes,
sem acessar a rede ou sobrescrever os resultados registrados.

```bash
python - <<'PY'
import hashlib
import json
import subprocess
import sys
from pathlib import Path

lote = Path("reviews/2026-10-17-cursos")
capturas = json.loads((lote / "capturas.json").read_text())["capturas"]
for captura in capturas:
    if captura["status"] != "capturado":
        raise SystemExit(f"Captura sem sucesso: {captura['arquivo']}")
    arquivo = Path(captura["arquivo"])
    conteudo = arquivo.read_bytes()
    if len(conteudo) != captura["bytes"]:
        raise SystemExit(f"Tamanho divergente: {arquivo}")
    if hashlib.sha256(conteudo).hexdigest() != captura["sha256"]:
        raise SystemExit(f"Hash divergente: {arquivo}")

def conferir(modulo, argumentos, destino):
    resultado = subprocess.check_output(
        [sys.executable, "-m", modulo, *argumentos], text=True
    )
    if resultado != destino.read_text():
        raise SystemExit(f"Resultado divergente: {destino}")
    print(f"OK: {destino}")

indice = next(c for c in capturas if c["tipo"] == "indice")
conferir("app.collectors.cursos", [
    "--html", indice["arquivo"], "--consultado-em", indice["consultado_em"],
], lote / "cursos-indice.json")
conferir("app.collectors.cursos_consolidados", [
    "--indice", indice["arquivo"],
    "--manifesto", str(lote / "cursos-manifesto.json"),
    "--consultado-em-indice", indice["consultado_em"],
], lote / "cursos-consolidados.json")
conferir("app.review.cursos", [
    "--atual", str(lote / "cursos-consolidados.json"),
    "--decisoes", str(lote / "cursos-decisoes.json"),
], lote / "cursos-revisao.json")
PY
```

## Validação executada

- As 68 capturas conferiram em tamanho e SHA-256 com o manifesto.
- A reprodução documentada gerou o índice, o consolidado e a revisão idênticos
  aos JSON registrados, byte a byte.
- As 67 associações entre seção, nome e URL do índice e os 67 breadcrumbs dos
  detalhes conferiram em uma leitura separada do HTML.
- Os manifestos, horários, 67 IDs candidatos únicos e decisões foram conferidos.
  Apenas Engenharia Agrícola está pendente; a EaD permanece fora do lote.
- A verificação dos valores acadêmicos não encontrou e-mails ou marcadores de
  coordenação. Os campos pessoais não integram a prévia.
- Os 74 testes de `test_cursos_collector.py`, `test_curso_detalhes_collector.py`,
  `test_cursos_consolidados.py` e `test_review_cursos.py` passaram.
- `ruff check .`, `ruff format --check .` e `git diff --check` passaram.
- Os HTML originais continuam ignorados pelo Git, e `data/` contém somente
  `.gitkeep`.

## Pendências para publicação

As decisões técnicas deste lote devem passar pela revisão do PR. Continuam
pendentes o esclarecimento de Engenharia Agrícola, a cobertura da EaD, a
completude e atualidade dos dados, a definição de ofertas, os IDs estáveis e os
vínculos institucionais comprovados. As condições de reutilização das fontes
também precisam de revisão antes de aprovar um snapshot completo dos quatro
datasets. `data/` continua sem dados de produção.
