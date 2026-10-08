# Revisão local de prévias de câmpus, centros, departamentos e cursos

As prévias produzidas pelos coletores são candidatas. O comando de revisão compara duas prévias do mesmo dataset, destaca mudanças e associa decisões registradas a versões específicas de cada registro. Ele não acessa a rede, não altera as prévias e não cria arquivos em `data/`.

## Preparar as prévias

Salve a saída de uma captura atual. Informe a data e a hora em que o HTML foi obtido, com fuso horário:

```bash
python -m app.collectors.campi \
  --html caminho/para/campi-atual.html \
  --consultado-em 2026-09-26T12:00:00-03:00 \
  > /tmp/campi-atual.json
```

Para centros, use `python -m app.collectors.centros` com os mesmos argumentos. Guarde a prévia anterior se quiser acompanhar o que mudou. Se não houver uma, a revisão tratará todos os registros atuais como candidatos novos.

Ao carregar uma prévia de centros, a revisão exige que cada `id` corresponda à `sigla` em minúsculas, conforme a regra do coletor. Uma divergência interrompe a análise antes de registrar aprovações.

## Comparar e criar um modelo de decisões

```bash
python -m app.review.previews \
  --dataset campi \
  --atual /tmp/campi-atual.json \
  --anterior caminho/para/campi-anterior.json \
  --modelo-decisoes /tmp/decisoes-campi.json \
  > /tmp/revisao-campi.json
```

Retire `--anterior` na primeira revisão. Para centros, troque `--dataset campi` por `--dataset centros` e use as prévias correspondentes. `--modelo-decisoes` cria um arquivo novo e recusa sobrescrever um existente. O relatório contém `comparacao.mudancas`, com inclusões, remoções e diferenças por campo, e `revisao.registros`, com a situação de cada decisão. Mudanças na proveniência da prévia aparecem em `comparacao.proveniencia_alterada`.

## Registrar e conferir decisões

Edite o modelo gerado. Para cada registro atual e cada remoção, preencha:

- `decisao`: `aprovado`, `rejeitado` ou `pendente`;
- `justificativa`: motivo da decisão;
- `evidencias`: lista de URLs ou caminhos de documentos conferidos;
- `data_decisao`: data e hora em ISO 8601 com fuso, para decisões finais.

Decisões finais exigem justificativa, pelo menos uma evidência e data. O Git registra quem alterou o manifesto; evite incluir nomes ou contatos pessoais nele. Depois, confira o relatório novamente:

```bash
python -m app.review.previews \
  --dataset campi \
  --atual /tmp/campi-atual.json \
  --anterior caminho/para/campi-anterior.json \
  --decisoes /tmp/decisoes-campi.json \
  > /tmp/revisao-campi-final.json
```

Cada decisão usa a `impressao` gerada para o registro e sua proveniência. Uma mudança de nome, ID, sigla, cidade, fonte, link de centro, status ou proveniência torna a decisão anterior `decisao_desatualizada`. Uma nova data de captura, sozinha, não a invalida. Registros removidos têm decisões próprias. Decisões que não correspondem a um registro atual ou a uma remoção aparecem em `decisoes_obsoletas`; IDs ausentes ou inesperados aparecem em `inconsistencias_cobertura`.

`todos_itens_aprovados` indica apenas que as decisões do relatório foram registradas e que não há inconsistências de cobertura. O relatório permanece `publicavel: false`: a origem dos arquivos locais não é autenticada, as condições de reutilização das fontes continuam pendentes e a API exige revisão do snapshot completo de quatro datasets antes de publicar dados.

## Departamentos de um centro

A revisão de departamentos recebe a prévia de uma única página de centro produzida por
`app.collectors.departamentos`. Gere a captura atual e, se disponível, uma captura anterior
do **mesmo centro**. Por exemplo:

```bash
python -m app.collectors.departamentos \
  --html caminho/para/departamentos-ctc-atual.html \
  --centro CTC \
  --consultado-em 2026-09-26T12:00:00-03:00 \
  > /tmp/departamentos-ctc-atual.json

python -m app.review.previews \
  --dataset departamentos \
  --atual /tmp/departamentos-ctc-atual.json \
  --anterior caminho/para/departamentos-ctc-anterior.json \
  --modelo-decisoes /tmp/decisoes-departamentos-ctc.json
```

Omita `--anterior` na primeira revisão. O comando recusa prévias de centros diferentes,
IDs incompatíveis com as siglas e a saída do coletor consolidado. Mudanças nos registros,
na auditoria ou nas exclusões exigem nova conferência. O relatório mantém a completude
dos departamentos do centro como não verificada, mesmo se todas as decisões dos registros
listados forem aprovadas. Ele não aprova o conjunto dos sete centros, não resolve siglas
repetidas entre eles e não grava em `data/`.

## Cursos presenciais da PEN

Para cursos, revise a **prévia consolidada** gerada por `app.collectors.cursos_consolidados`.
O comando é separado porque o lote também contém entradas sem captura ou com detalhe
inválido. Uma decisão de registro só é oferecida quando o detalhe foi aceito:

```bash
python -m app.review.cursos \
  --atual caminho/para/cursos-consolidados-atual.json \
  --anterior caminho/para/cursos-consolidados-anterior.json \
  --modelo-decisoes /tmp/decisoes-cursos.json \
  > /tmp/revisao-cursos.json
```

Omita `--anterior` na primeira revisão. Edite o modelo com decisões, justificativas,
evidências e datas como descrito acima. Depois execute novamente, substituindo
`--modelo-decisoes` por `--decisoes /tmp/decisoes-cursos.json`.

O campo `id` do modelo é uma **chave de revisão** formada por `campus_id|url_detalhe`;
ele não é o ID da API. Mudanças de nome sob o mesmo link aparecem como alteração do
registro e tornam a decisão anterior desatualizada. Uma URL nova é outra entrada do
índice: aparece como adição, e a URL removida exige uma decisão de remoção própria.
Uma falha ou ausência da captura do detalhe mantém a entrada no índice e aparece em
`inconsistencias_cobertura`, sem gerar uma remoção falsa. A ordem das entradas, o caminho
do arquivo e a hora da captura não alteram a impressão de uma decisão. Mudanças em
capturas fora do índice aparecem em `comparacao.cobertura_alterada`.

O relatório confere as contagens do lote, as seções de câmpus observadas na PEN,
os IDs candidatos, a correspondência entre cada detalhe aceito e sua entrada no índice,
e a proveniência declarada. Capturas fora do índice e a EaD ainda não incluída também
aparecem como pendências. Mesmo com todas as decisões registradas, o resultado fica
`publicavel: false`: a chave de revisão não resolve os IDs estáveis, os blocos acadêmicos
não foram desdobrados em ofertas, os vínculos e a completude ainda exigem conferência e
as condições de reutilização das fontes seguem pendentes.
