# Changelog

Todas as mudanças relevantes deste projeto são registradas neste arquivo.

O formato segue [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/) e o
projeto usa [Versionamento Semântico](https://semver.org/lang/pt-BR/).

## [Unreleased]

### Adicionado

- Licença MIT.
- Guia de contribuição, código de conduta, política de segurança e suporte.
- Modelos de issue para bugs, correções de dados e funcionalidades.
- Modelo de pull request e arquivo de mantenedores (CODEOWNERS).
- Este changelog.

## [0.1.0] - 2026-11-20

### Adicionado

- API FastAPI com rotas de lista e detalhe para câmpus, centros, departamentos e
  cursos de graduação em `/v1`.
- Paginação, filtros, schemas Pydantic, respostas de erro padronizadas,
  proveniência por registro e documentação OpenAPI.
- Carregamento e validação do snapshot completo na inicialização, com resposta
  503 quando os dados estão ausentes ou inválidos.
- Pipeline determinístico de geração do snapshot a partir dos lotes revisados.
- Mapeamento persistente de IDs de cursos em `reviews/course-ids.json`.
- Modo `--check` para detectar divergência entre `data/` e a geração revisada.
- Validação de publicação que confere snapshot, fontes aprovadas e registro de
  aprovação.
- Imagem Docker com o snapshot revisado e teste de fumaça no CI.
- Documentação de identificadores de câmpus, identidade de cursos, revisão de
  prévias, geração do snapshot e inventário de fontes.

### Dados

- Primeiro snapshot publicado: 7 câmpus, 7 centros, 49 departamentos e 67 cursos
  presenciais de graduação.
- Captura mais recente: `2026-10-22T17:58:32.788772+00:00`.
- Fontes aprovadas para o escopo publicado: `campi_uem`, `centros_pld` e
  `cursos_graduacao`.
- Aprovação registrada em `reviews/2026-11-20-publicacao/`.

### Limitações conhecidas

- Cursos EaD não incluídos.
- `status` mantido como `desconhecido`.
- Vínculos de centro e departamento não preenchidos.
- Três cursos com `grau` nulo e valores de grau não normalizados.
- Completude e atualidade das listas de departamentos não verificadas.

[Unreleased]: https://github.com/HenriqueSagawa/uemAPI/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/HenriqueSagawa/uemAPI/releases/tag/v0.1.0
