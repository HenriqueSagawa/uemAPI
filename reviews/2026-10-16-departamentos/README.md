# Primeira revisão real de departamentos

Conferência de 16 de outubro de 2026, baseada no código identificado em
[`capturas.json`](capturas.json), após o merge do PR de câmpus e centros. Foram
capturados novamente o índice da PLD e as sete páginas de centros, geradas as
prévias e registradas decisões técnicas assistidas para revisão no PR.

O consolidado aceitou as sete páginas e reuniu **49 candidatos a departamentos**,
sem siglas repetidas entre centros. Há **48 decisões aprovadas e uma pendente**
(DEM), além de [15 decisões de exclusão](exclusoes.md). A aprovação técnica de um
candidato cobre sua correspondência com a listagem capturada, sem representar
aprovação humana ou autorização de publicação.

| Centro | Candidatos | Excluídos | Aprovados | Pendentes | Relatório |
| --- | ---: | ---: | ---: | ---: | --- |
| CCA | 5 | 3 | 5 | 0 | [revisão](cca/revisao.json) |
| CCB | 5 | 2 | 5 | 0 | [revisão](ccb/revisao.json) |
| CCE | 5 | 2 | 5 | 0 | [revisão](cce/revisao.json) |
| CCH | 11 | 3 | 11 | 0 | [revisão](cch/revisao.json) |
| CCS | 8 | 3 | 8 | 0 | [revisão](ccs/revisao.json) |
| CSA | 5 | 1 | 5 | 0 | [revisão](csa/revisao.json) |
| CTC | 10 | 1 | 9 | 1 | [revisão](ctc/revisao.json) |
| **Total** | **49** | **15** | **48** | **1** | |

`cobertura_fontes_completa: true` significa apenas que as sete páginas foram
processadas. Cada revisão individual mantém a inconsistência de cobertura
`completude dos departamentos do centro não verificada`; por isso,
`todos_itens_aprovados` permanece `false` nos sete relatórios. Todos os resultados
permanecem `publicavel: false`, com `campus_id: null` e `status: desconhecido`.

## Capturas e arquivos

O [índice de centros da PLD](https://pld.uem.br/dvl/regulamentos/centros-de-ensino)
foi obtido antes das páginas de departamentos. Seus sete links foram confrontados
com o mapeamento de fontes já existente no coletor. As oito requisições
retornaram HTTP 200, na URL HTTPS esperada, com validação TLS.

- `capturas.json`: commit de base, URLs, horários UTC com fuso, resultado HTTP,
  tipo de conteúdo, tamanho e SHA-256 das oito capturas.
- `departamentos-manifesto.json`: as sete associações entre centro, arquivo e
  horário, no formato de entrada do coletor consolidado.
- `departamentos-consolidados.json`: cobertura das páginas, contagens e
  duplicidades entre centros.
- `cca/` a `ctc/`: `previa.json`, `decisoes.json` e `revisao.json` para cada centro.
- `exclusoes.md`: decisão e fundamento para cada entrada excluída.

Os originais estão em `capturas/`, ignorado pelo Git. Um clone contém os
resultados e as referências, mas a reprodução exata do parsing exige os arquivos
locais com os hashes registrados. Uma nova consulta pode trazer conteúdo
diferente e deve formar outro lote. Os metadados de obtenção não são uma
assinatura institucional e não autorizam a redistribuição dos documentos.

## Alcance da conferência

Foram conferidos os sete títulos, as siglas, os nomes exibidos e os links das
64 entradas: 49 candidatas e 15 excluídas. Uma extração separada de todos os links
textuais sob a URL de cada centro coincidiu com a união de `auditoria` e
`excluidos`, sem omissões nessa comparação. Essa conferência cobre os rótulos
das páginas obtidas; não comprova que a PLD liste todos os departamentos atuais.

O nome candidato retira a sigla inicial e o sufixo da resolução. Os IDs em
minúsculas são candidatos internos, e o centro corresponde à página identificada
pelo título e pelo regulamento do próprio centro. Não foram inferidos câmpus,
situação atual ou relações com cursos. Os documentos vinculados não foram lidos;
seus links foram conferidos apenas como valores presentes no HTML.

Foram registradas estas particularidades:

- **DEM / CTC:** a fonte escreve `Deparamento de Engenharia Mecânica`. A prévia
  mantém essa grafia e sua observação de auditoria. A decisão ficou **pendente**
  até definir e comprovar o nome canônico; os JSON do coletor não foram editados
  para corrigir o texto.
- **DAU / CTC:** o sufixo de resolução termina sem fechar parênteses. O coletor
  já admite esse formato e preserva o nome que o antecede.
- **DDM / CTC:** `Resolucao` aparece sem acento no sufixo removido.
- **DAM / CTC:** preservada a grafia `Meio-Ambiente` com hífen.
- **DMO / CCS:** preservados a sigla DMO e o nome Ciências do Movimento Humano
  exibidos na mesma entrada, sem recalcular a sigla a partir do nome.
- Alguns nomes de arquivos vinculados mencionam resoluções diferentes dos
  rótulos atuais, como em DFL e DMA. Ambos os valores foram preservados; o nome
  do arquivo não foi usado para afirmar o conteúdo ou a vigência do documento.
- NUPÉLIA aparece como instituto no CCB. Sua exclusão considera esse rótulo,
  mantendo pendente a classificação institucional baseada no regulamento.

## Reprodução local

Execute a partir da raiz do repositório, com o ambiente virtual ativado e os
originais disponíveis em `capturas/`. O código abaixo confere os oito hashes e
reexecuta os coletores e as revisões, comparando os resultados byte a byte. Ele
não acessa a rede nem sobrescreve os JSON registrados.

```bash
python - <<'PY'
import hashlib
import json
import subprocess
import sys
from pathlib import Path

lote = Path("reviews/2026-10-16-departamentos")
capturas = json.loads((lote / "capturas.json").read_text())["capturas"]
for captura in capturas:
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

manifesto = lote / "departamentos-manifesto.json"
conferir("app.collectors.departamentos_consolidados",
         ["--manifesto", str(manifesto)],
         lote / "departamentos-consolidados.json")
for captura in json.loads(manifesto.read_text())["centros"]:
    centro = captura["centro_sigla"]
    pasta = lote / centro.lower()
    conferir("app.collectors.departamentos", [
        "--html", str(lote / captura["arquivo"]),
        "--centro", centro, "--consultado-em", captura["consultado_em"],
    ], pasta / "previa.json")
    conferir("app.review.previews", [
        "--dataset", "departamentos", "--atual", str(pasta / "previa.json"),
        "--decisoes", str(pasta / "decisoes.json"),
    ], pasta / "revisao.json")
PY
```

## Validação executada

- Os oito arquivos originais conferiram em tamanho e SHA-256 com o manifesto.
- A reprodução documentada gerou o consolidado, as sete prévias e as sete
  revisões idênticos aos JSON registrados, byte a byte.
- Os candidatos e as exclusões das prévias individuais coincidiram com os
  resultados do consolidado. Os relatórios mantiveram 48 aprovações, uma decisão
  pendente para o DEM e a completude não verificada em todos os centros.
- Os 90 testes de `test_departamentos_collector.py`,
  `test_departamentos_consolidados.py` e `test_review_previews.py` passaram.
- `ruff check .`, `ruff format --check .` e `git diff --check` passaram.
- Os HTML originais continuam ignorados pelo Git, e `data/` contém somente
  `.gitkeep`.

## Pendências

As decisões técnicas e de exclusão estão disponíveis para revisão humana no PR.
O nome canônico do DEM, a completude e a atualidade institucional das listas, a
classificação dos demais órgãos, os documentos vinculados e as condições de
reutilização continuam pendentes. A cobertura das sete fontes e a ausência de
siglas duplicadas neste lote não resolvem essas questões.

A etapa seguinte é revisar as capturas reais de cursos, incluindo a cobertura da
EaD e os IDs estáveis. As fontes continuam candidatas e `data/` continua sem
snapshot de produção.
