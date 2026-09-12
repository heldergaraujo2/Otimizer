# Estado atual

## Repositório

A integração de escrita com o repositório GitHub `heldergaraujo2/Otimizer` está operacional.

## Fase

Fundação do domínio, importador e primeira camada de roteamento/otimização.

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
- Fixtures anonimizados de regressão baseados nos casos reais.
- Camada de integração com OSRM Table para matriz de distância/tempo por rede viária, preservando pares inalcançáveis.
- Primeiro otimizador determinístico por vizinho mais próximo, usando tempo de viagem rodoviária como custo primário e cobrindo todos os PhysicalStops.
- Agregação de métricas de rota (distância e duração), incluindo opcionalmente a perna de retorno.
- Exportação pública das APIs de importação, roteamento, otimização e métricas.

## Estado de testes

Os testes automatizados foram adicionados para importação, agrupamento, roteamento, otimização e métricas. A execução local não foi possível neste ambiente porque o clone por rede do GitHub não conseguiu resolver `github.com`; portanto, não há afirmação de que a suíte foi executada localmente.

## Próxima etapa

Evoluir o otimizador para uma interface de problema configurável, separando origem/depot, destino opcional, rota aberta/fechada e objetivo (tempo ou distância). Depois disso, avaliar um solver de otimização mais forte (por exemplo, OR-Tools) sobre a mesma matriz rodoviária, mantendo o algoritmo guloso como baseline determinístico.

## Regra de continuidade

Cada avanço relevante deve ser versionado no GitHub para que o estado do projeto permaneça recuperável e auditável.
