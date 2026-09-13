# Estado atual

## Repositório

A integração de escrita com o repositório GitHub `heldergaraujo2/Otimizer` está operacional.

## Fase

Fundação do domínio, importação XLSX, roteamento rodoviário, otimização configurável e resultado de rota.

## Concluído

- README inicial, requisitos, arquitetura e especificação do XLSX.
- Importador XLSX com elegibilidade por latitude/longitude e auditoria das linhas não resolvidas.
- Reconstrução inicial de PhysicalStop independente de `Sequence`/`Stop`.
- Modelos explícitos de Delivery, PhysicalStop, OptimizedRouteStop e Route com invariantes de cobertura.
- Fixtures anonimizados e testes de regressão baseados nos casos reais, sem armazenar dados pessoais das planilhas.
- Integração com OSRM Table para matriz de distância/tempo por rede viária, preservando pares inalcançáveis.
- Otimizador determinístico por vizinho mais próximo e interface configurável de problema.
- Objetivos de otimização por tempo ou distância.
- Suporte a origem/depot, destino opcional, rota aberta e retorno à origem quando não há origem externa.
- Matriz de roteamento consciente dos endpoints e validação de rotas completas.
- Serviço de aplicação que executa XLSX -> PhysicalStops -> matriz rodoviária -> otimização.
- Resultado de serviço com contagem de entregas, paradas físicas, paradas roteadas, pendências e indicador de cobertura completa.
- Resultado de métricas com pernas individuais, distância total e duração total.
- Pernas opcionais de origem -> primeira parada, última parada -> destino e retorno à origem.
- Métricas calculadas exclusivamente a partir da mesma matriz rodoviária usada na otimização.
- Testes automatizados para importação, agrupamento, roteamento, otimização, endpoints, métricas e cobertura ponta a ponta.
- GitHub Actions configurado para executar a suíte do importer.

## Estado de testes

O último pipeline confirmado antes da evolução do resultado foi bem-sucedido. As alterações de resultado/métricas foram versionadas em commits separados; o próximo passo é confirmar o novo pipeline e corrigir qualquer regressão encontrada por ele.

## Próxima etapa

Após CI verde, construir uma API HTTP fina sobre o serviço, mantendo o domínio independente do framework. A API deverá aceitar o XLSX e parâmetros de rota e devolver um contrato estável, pronto para o frontend, contendo resumo, paradas numeradas, entregas por parada, pernas e métricas.

Depois disso, iniciar o frontend/mapa e a navegação, e posteriormente avaliar um solver mais forte (como OR-Tools) sobre a mesma matriz rodoviária.

## Regra de continuidade

Cada avanço relevante deve ser versionado no GitHub para que o estado do projeto permaneça recuperável e auditável.
