# Aprovação de publicação da v0.1.0

Em 20 de novembro de 2026, a manutenção do projeto aprovou a publicação do
primeiro snapshot revisado da uemAPI. A decisão autoriza a API a servir os quatro
arquivos de `data/` descritos abaixo. Ela não altera os lotes de revisão
anteriores, não recaptura as fontes e não transforma dados não verificados em
dados oficiais.

O registro estruturado dessa decisão está em
[`aprovacao.json`](aprovacao.json). Ele é conferido por
`scripts/validate_publication.py` junto com o snapshot, o manifesto e o catálogo
de fontes.

## Escopo aprovado

| Dataset | Registros |
| --- | ---: |
| Câmpus | 7 |
| Centros | 7 |
| Departamentos | 49 |
| Cursos presenciais de graduação | 67 |

A captura mais recente usada no snapshot é
`2026-10-22T17:58:32.788772+00:00`. As entradas são exatamente as declaradas em
[`reviews/snapshot-inputs.json`](../snapshot-inputs.json), incluindo as
normalizações verificadas e o mapeamento persistente de IDs de cursos.

## IDs de cursos

O snapshot usa [`reviews/course-ids.json`](../course-ids.json), com 67 entradas
indexadas por `campus_id` e `url_detalhe`. O ID publicado não muda quando o nome
do curso muda. Uma URL nova exige uma nova entrada e uma nova decisão de revisão;
o pipeline recusa curso aceito sem ID e IDs repetidos, e informa mapeamentos não
utilizados no relatório de geração.

## Fontes aprovadas para este escopo

- `campi_uem`, para os campos publicados de câmpus;
- `centros_pld`, para os campos publicados de centros e departamentos;
- `cursos_graduacao`, para os campos publicados de cursos presenciais.

As três entradas passaram a `status: approved`, `reuse_conditions: verified` e
intervalo de revisão de 180 dias em `sources/registry.yaml`. As demais fontes do
catálogo continuam candidatas e não são usadas pelo snapshot publicado.

Esta aprovação é uma decisão de manutenção sobre a publicação deste snapshot pela
uemAPI. Ela não constitui licença geral, parecer jurídico nem autorização para
terceiros redistribuírem as páginas institucionais. As condições de reutilização
registradas valem para o escopo documentado nesta pasta.

## Limitações conhecidas

- Cursos de graduação a distância (EaD) não estão incluídos.
- Todos os registros publicados mantêm `status: desconhecido`; a situação atual
  não foi verificada.
- Os 67 cursos não têm `centro_sigla` nem `departamento_sigla`, e os 49
  departamentos não têm `campus_id`. Os filtros correspondentes ficam vazios com
  este snapshot.
- `grau` preserva o valor observado ou `null` quando o coletor não conseguiu
  inferir um único grau. Três cursos ficaram com `grau: null`
  (`cau-tecnologia-em-gastronomia`, `sede-ciencias-biologicas` e `sede-musica`).
- Os 55 valores distintos de `grau` misturam categorias como “Bacharelado” e
  títulos profissionais como “Engenheiro Agrícola” e “Médico”. O campo não deve
  ser lido como uma classificação normalizada.
- A grafia de Engenharia Agrícola na fonte continua divergente do PPC vinculado.
  A normalização proposta foi registrada, mas permanece fora do modelo canônico
  publicado; o valor observado não foi alterado.
- A completude e a atualidade das listas de departamentos não foram verificadas.
  Os vínculos institucionais entre cursos, centros e departamentos não foram
  comprovados e por isso não foram preenchidos.
- Os nomes dos sete centros aparecem em maiúsculas como na fonte; a forma
  `Arquitetura e Urbanismo (CAU)` foi preservada.
- A cobertura de ofertas, turnos e habilitações não foi desdobrada em registros
  independentes.

## O que não foi aprovado

- Publicar capturas novas sem passar pelo fluxo de revisão.
- Preencher centro, departamento, câmpus de departamento, situação ou ofertas
  por inferência.
- Alterar IDs de cursos quando o nome mudar.
- Reutilizar as fontes fora do escopo descrito nesta aprovação.
- Tratar a API como fonte oficial da UEM.

## Verificação

```bash
python scripts/validate_sources.py
python scripts/validate_data.py --require
python scripts/update_data.py --check
python scripts/validate_publication.py
```

O último comando compara o snapshot publicado com a geração determinística dos
lotes revisados, confere as fontes efetivamente usadas e exige que a aprovação
registre as mesmas contagens, fontes e data de captura. Qualquer divergência faz
o CI falhar.
