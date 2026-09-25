# Inventário inicial de fontes da uemAPI

Revisão: 25 de setembro de 2026. Este inventário avalia as sete URLs já propostas em `sources/registry.yaml`. Todas permanecem **candidatas**. Acesso público à página confirma que ela pode ser lida sem login; não confirma permissão para coleta automatizada ou redistribuição de um dataset.

| Fonte | Dados observados | Uso proposto | Limite encontrado |
| --- | --- | --- | --- |
| [Câmpus da UEM](https://www.uem.br/a-uem/campus) | Sede em Maringá e seis câmpus regionais, com seus municípios. | Nomes e cidades de câmpus. | O texto não traz siglas, identificadores ou endereços de cada unidade. |
| [Organograma](https://www.npd.uem.br/transparencia/organograma/index.html) | Hierarquia de câmpus regionais, centros e departamentos. | Confrontar vínculos institucionais. | É uma página de apresentação; nomes e relações exigem conferência em fontes específicas. |
| [Centros de ensino da PLD](https://pld.uem.br/dvl/regulamentos/centros-de-ensino) | Índice de sete centros com siglas; páginas vinculadas listam departamentos e resoluções. | Fonte inicial para centros e departamentos. | A estrutura das sete páginas vinculadas e a atualidade de cada lista ainda precisam ser conferidas. |
| [Base de Dados da PLD](https://pld.uem.br/lni/base) | Índice HTML de relatórios anuais em PDF. O [relatório 2025](https://pld.uem.br/lni/v05-base-de-dados-2024-2025.pdf) usa ano base 2024 e inclui uma lista de siglas. | Verificação histórica de nomes e siglas. | Não é um PDF único nem uma fonte corrente. O relatório informa direitos reservados; reutilização precisa de revisão específica. |
| [Catálogo de graduação](https://cpr.uem.br/index.php/catalogos/graduacao) | Lista paginada com 57 resultados; páginas de curso apresentam modalidade, grau, centro e câmpus. | Candidata a fonte principal de cursos. | É preciso percorrer todas as páginas, definir o que constitui uma oferta e confirmar se o número na URL de detalhe é estável. |
| [Portal de graduação](https://www.uem.br/estude-na-uem/graduacao) | Resumo que informa 80 cursos e distribuição por local e modalidade. | Conferência de cobertura do catálogo. | A contagem difere dos 57 resultados do catálogo; as unidades contadas podem ser diferentes. |
| [SIGAA público](https://sigs.uem.br/sigaa/public/home.jsf) | Links públicos para consultas de centros, departamentos e cursos. | Fonte adicional de validação. | A página inicial é pública, mas o acesso automatizado aos resultados e seu formato ainda não foram verificados. |

## Decisões antes do primeiro coletor

1. **Identificadores e siglas de câmpus.** A página de câmpus não informa siglas. O relatório Base de Dados 2025 registra siglas regionais, mas não resolve sozinho o código público da sede. Como `/v1/campi/{sigla}` depende dessa regra, ela deve ser aprovada antes de publicar registros.
2. **Unidade de curso.** O catálogo apresenta 57 resultados, enquanto o portal informa 80 cursos. Não tratar essa diferença como erro de uma das páginas sem entender se contam cursos, ofertas, turnos ou modalidades. Um curso com ofertas distintas não deve ser mesclado por nome.
3. **Reutilização e frequência.** Não foi identificada uma licença geral de dados para essas páginas. O relatório anual declara direitos reservados. Antes de automatizar ou redistribuir, revisar as condições aplicáveis a cada fonte e definir frequência prudente de acesso. `review_interval_days` permanece sem valor no registro até essa decisão.
4. **Cobertura dos vínculos.** Conferir os sete centros e suas páginas de departamentos. Vínculos curso–departamento não devem ser inferidos apenas por semelhança de nome ou pelo centro do curso.

Após essas decisões, a primeira implementação sugerida é um coletor de câmpus com amostra local para testes, saída em modo de prévia e revisão do JSON antes da publicação. Nenhum dataset de produção foi criado nesta etapa.
