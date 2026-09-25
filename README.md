# uemAPI

API comunitária, independente e **não oficial** para informações públicas da Universidade Estadual de Maringá. Este repositório contém a base da v0.1 Fundação. Ainda não há fontes revisadas nem dados de produção aprovados.

## O que já existe

- Aplicação FastAPI com rotas de lista e detalhe para câmpus, centros, departamentos e cursos de graduação em `/v1`.
- Paginação fixa: `page` começa em 1; `page_size` usa 50 por padrão e aceita até 100.
- Filtros de departamentos por `centro` e `campus`, e de cursos por `campus`, `centro`, `grau` e `modalidade`.
- Schemas, formato de erro, proveniência por registro e documentação OpenAPI em `/docs`.
- Carregamento de um snapshot JSON completo na inicialização, com validação de modelos, unicidade e referências. Se um arquivo estiver ausente ou inválido, `/v1/health` e as consultas respondem 503.

Os exemplos nos testes são fictícios e não devem ser copiados para `data/`. O contrato de dados poderá ser refinado depois da conferência das fontes reais.

## Desenvolvimento local

Requer Python 3.13 ou superior.

```bash
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
python -m uvicorn app.main:app --reload
```

A documentação interativa estará em <http://127.0.0.1:8000/docs>. Até que os quatro arquivos aprovados existam em `data/`, as consultas retornam 503. Para usar outro diretório de dados, defina `UEM_API_DATA_DIR` (consulte `.env.example`).

Também é possível construir uma imagem com `docker build -t uem-api .` e iniciar com `docker run --rm -p 8000:8000 uem-api`. A imagem atual inclui apenas o diretório `data/` vazio e, portanto, informa indisponibilidade até receber dados revisados.

## Qualidade

```bash
python -m ruff check .
python -m ruff format --check .
python -m pytest
```

## Formato do snapshot

O diretório configurado deve conter `campi.json`, `centros.json`, `departamentos.json` e `cursos.json`. Cada arquivo contém uma lista JSON não vazia de registros do schema correspondente. Cada registro inclui `id`, `nome` e `fonte` com `source_id`, `url` e `consultado_em` com fuso horário. Os schemas em `app/schemas/` definem os demais campos. Todos os quatro arquivos são validados juntos; nenhum subconjunto é publicado isoladamente.

## Próximas etapas

1. Verificar fontes institucionais públicas para cada dataset, condições de uso e identificadores disponíveis.
2. Implementar o Source Registry e os coletores, com fixtures sem dados pessoais.
3. Definir o processo de revisão dos diffs e publicar os primeiros JSON reais aprovados.

O projeto não coleta dados pessoais, conteúdos restritos ou informações que exijam autenticação.
