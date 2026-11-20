# Suporte

A uemAPI é mantida de forma voluntária e **não oficial**. Não há SLA, suporte
comercial ou garantia de disponibilidade. O projeto não substitui os canais
oficiais da Universidade Estadual de Maringá.

## Antes de pedir ajuda

1. Leia o [README](README.md).
2. Consulte a documentação em [`docs/`](docs/).
3. Verifique o estado da API em `/v1/health`.
4. Procure issues existentes com o mesmo problema.

## Onde abrir cada tipo de solicitação

| Assunto | Canal |
| --- | --- |
| Erro na aplicação, rota ou documentação | [Relatar bug](.github/ISSUE_TEMPLATE/bug_report.yml) |
| Correção de nome, vínculo, grau ou outro dado | [Correção de dados](.github/ISSUE_TEMPLATE/data_correction.yml) |
| Nova funcionalidade ou melhoria | [Sugerir funcionalidade](.github/ISSUE_TEMPLATE/feature_request.yml) |
| Vulnerabilidade de segurança | [Canal privado](SECURITY.md) |
| Dúvida sobre contribuição | [CONTRIBUTING.md](CONTRIBUTING.md) |

## O que incluir

Para problemas técnicos, informe:

- o que você tentou fazer;
- o que esperava e o que aconteceu;
- a URL, rota ou arquivo envolvido;
- a versão, commit ou ambiente;
- logs relevantes, sem tokens, dados pessoais ou conteúdo restrito.

Para correções de dados, informe o ID do registro, o campo, o valor atual, o valor
observado na fonte e a URL pública que sustenta a correção. Correções sem
evidência não podem ser aceitas.

## Limitações conhecidas

O snapshot publicado tem limitações documentadas na
[aprovação de publicação](reviews/2026-11-20-publicacao/README.md), incluindo
ausência de cursos EaD, `status` desconhecido e vínculos de centro/departamento
não preenchidos. Verifique esse documento antes de relatar uma ausência como bug.
