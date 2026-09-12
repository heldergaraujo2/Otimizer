# Estado atual

## Repositório

A integração de escrita com o repositório GitHub `heldergaraujo2/Otimizer` está operacional.

## Fase

Fundação do domínio e importador.

## Concluído

- README inicial.
- Requisitos funcionais.
- Arquitetura inicial.
- Especificação do XLSX.
- Identidade e visão do projeto.
- Importador XLSX com elegibilidade por latitude/longitude.
- Reconstrução inicial de PhysicalStop independente de `Sequence`/`Stop`.
- Modelo explícito de `OptimizedRouteStop` e `Route` com invariantes de cobertura estrutural.
- Resultado estruturado de importação com auditoria de todas as linhas de dados.
- Testes de integridade do resultado da importação.
- Testes de agrupamento e integridade de deliveries.

## Próxima etapa

Criar fixtures anonimizados de regressão baseados nos casos reais e validar quantitativamente o pipeline de importação/agrupamento; em seguida iniciar a primeira camada de roteamento por rede viária.

## Regra de continuidade

Cada avanço relevante deve ser versionado no GitHub para que o estado do projeto permaneça recuperável e auditável.
