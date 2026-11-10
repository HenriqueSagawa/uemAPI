# Decisões complementares sobre DEM e Engenharia Agrícola

Conferência de 22 de outubro de 2026, após o merge da revisão de cursos, sobre
o commit registrado em [`capturas.json`](capturas.json). Foram investigados os
dois valores que ficaram pendentes nos lotes de departamentos e cursos.

As evidências sustentam o nome **Departamento de Engenharia Mecânica** e a
formação de bacharel em Engenharia Agrícola. As novas decisões rejeitam os
valores candidatos incompatíveis com essas evidências, e
[`normalizacoes-propostas.json`](normalizacoes-propostas.json) registra os campos
que poderão ser corrigidos em uma etapa própria de normalização.

| Registro | Valor observado no HTML | Valor proposto | Abrangência da evidência |
| --- | --- | --- | --- |
| DEM / CTC, `nome` | Deparamento de Engenharia Mecânica | Departamento de Engenharia Mecânica | Resolução 106/2018-CI/CTC, Anexo I, art. 1º |
| Engenharia Agrícola / CAR, primeira habilitação | Licenciatura | Bacharel em Engenharia Agrícola | PPC aprovado pela Resolução 042/2022-CI/CCA, para ingressantes a partir de 2023 |

As propostas estão disponíveis para revisão humana, com `aplicadas: false` e
`publicavel: false`. Os coletores continuam registrando fielmente o HTML; seus
resultados não foram editados para aparentar que os valores vieram da página.

## Evidências conferidas

### DEM

A nova captura da [página do CTC](https://pld.uem.br/dvl/regulamentos/centros-de-ensino/centro-de-tecnologia-ctc)
conserva a grafia `Deparamento`. O link aponta para uma página de arquivo da
PLD; o download termina em `.crdownload`, mas seus bytes identificam um PDF.
Essa cópia e a [cópia no domínio do DEM](https://dem.uem.br/arquivos/resolucoes-dem/resolucao-106-2018-ctc.pdf)
têm tamanho e SHA-256 idênticos.

Na página PDF 2, o Anexo I e seu art. 1º identificam o Departamento de Engenharia
Mecânica, sua sigla DEM e seu vínculo com o CTC. A página foi extraída e conferida
visualmente. O documento é de 2018: a decisão usa a nomenclatura e não afirma
que o regulamento esgote a situação institucional atual da unidade.

A proposta altera somente `nome`. Sigla, ID candidato, câmpus e situação atual
não recebem valores novos. O candidato com a grafia incorreta ficou `rejeitado`
na nova revisão; isso não indica extinção ou retirada da unidade do inventário.

### Engenharia Agrícola

O [detalhe atual da PEN](https://www.pen.uem.br/site/public/curso/7e57e246c1bb9a6a19bde73c135003e110ad48e3)
foi conferido com uma nova captura do índice. O HTML ainda apresenta
`Licenciatura`, e sua extração também permanece assim.

O próprio detalhe vincula o
[PPC no arquivo 20230524_140812-engenhariaagricola.pdf](https://www.pen.uem.br/site/public/assets/files/19944F3D475A0C509C267FE117F4A9F8/20230524_140812-engenhariaagricola.pdf).
A página PDF 1 delimita a aplicação aos ingressantes a partir de 2023. Na página
PDF 2, o item 1.1 registra a habilitação indicada na proposta, o item 1.2 vincula
o curso ao Arenito e o item 1.6 assinala Bacharel. As duas páginas foram conferidas
visualmente. A redação proposta conserva o texto específico do item 1.1.

Como corroboração, a página PDF/impressa 16 do
[Edital 072/2025-DAA, segunda republicação, para ingresso em 2026](https://daa.uem.br/editais-e-portarias/editais-e-portarias-2025-1/edital-072-2025-daa-processos-especiais-de-ingresso-2026-2a-republicacao.pdf)
relaciona Engenharia Agrícola no CAR, turno Integral e categoria Bacharelado.
O edital foi conferido visualmente e não foi usado para atualizar vagas ou
outras informações do curso.

Também foi capturado um material anterior da PEN, no arquivo
`20210310_114004-engenhariaagricola.pdf`, encontrado na pesquisa. Ele usa
`Bacharelado` para habilitação, mas não é o PPC atualmente vinculado. Sua primeira
página foi conferida apenas como comparação histórica; ela não define o valor
da proposta nem substitui o documento vinculado atual.

Os termos dos documentos têm escopos diferentes: o edital usa uma categoria
de formação, o PPC apresenta a habilitação específica e o HTML exibe o grau
profissional. A proposta muda somente a habilitação e preserva o grau profissional
observado. Não é uma regra geral de converter graus ou habilitações. A aplicação
futura deve respeitar a abrangência do PPC; o modelo atual ainda não diferencia
turmas de ingresso.

## Novas decisões e preservação do histórico

- `ctc-previa.json`: nova extração da captura do CTC de 22/10. Seus registros,
  auditoria e exclusões coincidem com os da prévia de 16/10.
- `ctc-decisoes.json`: reaproveita as nove decisões inalteradas e troca a decisão
  do DEM de `pendente` para `rejeitado`, com as novas evidências.
- `ctc-revisao.json`: comparação com a prévia de 16/10, com nove aprovações,
  uma rejeição e nenhuma decisão pendente ou desatualizada. A completude segue
  não verificada e `todos_itens_aprovados` permanece `false`.
- `cursos-indice-previa.json` e `engenharia-agricola-previa.json`: novas extrações
  do índice e do único detalhe consultado em 22/10. Não constituem uma nova
  captura dos 67 detalhes.
- `cursos-decisoes.json`: preserva as 66 aprovações históricas e altera somente
  Engenharia Agrícola de `pendente` para `rejeitado`, com a justificativa da
  divergência de habilitação.
- `cursos-revisao.json`: nova revisão **do consolidado de 17/10**, com 66
  aprovações, uma rejeição e nenhuma decisão pendente ou desatualizada. As datas
  do lote e as demais decisões continuam históricas; a EaD segue fora da cobertura.
- `normalizacoes-propostas.json`: duas propostas declarativas, com valor
  observado, valor proposto, campo, impressão da base, evidências, hashes e
  localizadores. Esse arquivo ainda não é consumido pelos coletores ou pela API.

Os lotes de 16 e 17/10 permanecem intactos. As rejeições resolvem a avaliação dos
valores originais para uso canônico; a adoção das propostas depende da revisão
e da futura etapa que as aplique com conferência da base e da abrangência.
Uma mudança no registro ou na proveniência exige nova decisão.

## Capturas e catálogo de fontes

O manifesto registra dez arquivos obtidos por HTTPS: páginas atuais, páginas de
arquivo e PDFs de apoio. Todos têm horário UTC com fuso, URL solicitada e final,
HTTP status, tipo de conteúdo, tamanho e SHA-256. Os originais estão em
`capturas/`, ignorado pelo Git. Há assinaturas e contatos nos documentos; esses
dados não foram transcritos para os JSON ou para a documentação versionada.

Um clone contém os resultados e as referências, mas a reprodução exata exige
os originais locais com os hashes registrados. Metadados e hashes não são uma
assinatura institucional nem autorizam reutilização ou publicação.

O catálogo mantém as fontes como `candidate` e as condições de reutilização
como `not_verified`. As datas foram atualizadas somente no escopo conferido:

- Câmpus: captura de 16/10 e referências ao lote correspondente.
- Índice de centros e sete páginas: conferência de 16/10; a nova conferência do
  CTC em 22/10 é descrita como parcial, sem revalidar o índice inteiro.
- Índice da PEN: nova captura de 22/10. Os 67 detalhes continuam com a referência
  de 17/10; somente Engenharia Agrícola foi recapturado agora.
- O índice da Base de Dados, organograma, portal de graduação e SIGAA mantêm
  as datas anteriores, pois não foram reconferidos nesta etapa.
- Foram incluídas as fontes de validação do regulamento do DEM, do PPC e do
  edital da DAA, com seus limites documentados.

## Reprodução local

Na raiz do repositório, com o ambiente virtual ativado e as dez capturas locais
disponíveis, execute:

```bash
python - <<'PY'
import hashlib
import json
import subprocess
import sys
from pathlib import Path

lote = Path("reviews/2026-10-22-pendencias")
capturas = json.loads((lote / "capturas.json").read_text())["capturas"]
por_nome = {Path(c["arquivo"]).name: c for c in capturas}
for captura in capturas:
    if captura["status"] != "capturado":
        raise SystemExit(f"Captura sem sucesso: {captura['arquivo']}")
    arquivo = Path(captura["arquivo"])
    conteudo = arquivo.read_bytes()
    if len(conteudo) != captura["bytes"]:
        raise SystemExit(f"Tamanho divergente: {arquivo}")
    if hashlib.sha256(conteudo).hexdigest() != captura["sha256"]:
        raise SystemExit(f"Hash divergente: {arquivo}")
    if arquivo.suffix == ".pdf" and not conteudo.startswith(b"%PDF-"):
        raise SystemExit(f"Formato inesperado: {arquivo}")
if por_nome["dem-regulamento.pdf"]["sha256"] != por_nome["dem-regulamento-pld.pdf"]["sha256"]:
    raise SystemExit("Cópias do regulamento do DEM divergem")

def conferir(modulo, argumentos, destino):
    resultado = subprocess.check_output(
        [sys.executable, "-m", modulo, *argumentos], text=True
    )
    if resultado != destino.read_text():
        raise SystemExit(f"Resultado divergente: {destino}")
    print(f"OK: {destino}")

ctc = por_nome["ctc.html"]
indice = por_nome["cursos-indice.html"]
curso = por_nome["engenharia-agricola.html"]
conferir("app.collectors.departamentos", [
    "--html", ctc["arquivo"], "--centro", "CTC", "--consultado-em", ctc["consultado_em"],
], lote / "ctc-previa.json")
conferir("app.collectors.cursos", [
    "--html", indice["arquivo"], "--consultado-em", indice["consultado_em"],
], lote / "cursos-indice-previa.json")
conferir("app.collectors.curso_detalhes", [
    "--indice", indice["arquivo"], "--html", curso["arquivo"], "--campus", "car",
    "--url", curso["url_final"], "--consultado-em", curso["consultado_em"],
], lote / "engenharia-agricola-previa.json")
conferir("app.review.previews", [
    "--dataset", "departamentos", "--atual", str(lote / "ctc-previa.json"),
    "--anterior", "reviews/2026-10-16-departamentos/ctc/previa.json",
    "--decisoes", str(lote / "ctc-decisoes.json"),
], lote / "ctc-revisao.json")
conferir("app.review.cursos", [
    "--atual", "reviews/2026-10-17-cursos/cursos-consolidados.json",
    "--decisoes", str(lote / "cursos-decisoes.json"),
], lote / "cursos-revisao.json")
PY
```

Os comandos reproduzem as extrações e os relatórios; não aplicam as normalizações
nem transformam a documentação em uma nova aprovação humana.

## Validação executada

- Dez capturas conferidas em tamanho e SHA-256; os cinco arquivos PDF também
  conferiram pela assinatura de formato `%PDF-`.
- As duas cópias do regulamento do DEM têm SHA-256 idênticos.
- As três prévias e os dois relatórios foram reproduzidos byte a byte pelo
  procedimento documentado.
- Cada manifesto de decisões mudou somente o registro que estava pendente;
  as demais decisões e as impressões originais foram preservadas.
- As duas propostas conferiram com suas impressões de base, valores observados,
  referências de captura e hashes, mantendo `aplicadas: false`.
- O catálogo YAML foi validado com PyYAML disponível no Python do sistema:
  dez fontes candidatas, três novas fontes de validação e datas coerentes com
  o escopo de cada captura; reutilização continua não verificada.
- Os 51 testes de `test_review_previews.py` e `test_review_cursos.py` passaram.
- `ruff check .`, `ruff format --check .` e `git diff --check` passaram.
- Os lotes anteriores não têm alterações, os originais continuam ignorados
  pelo Git e `data/` contém somente `.gitkeep`.
