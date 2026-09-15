# Handoff — continuidade do Otimizer

## Repositório

`heldergaraujo2/Otimizer`, branch `main`.

## Objetivo

Transformar XLSX reais de entregas em uma rota confiável por rede viária real, preservando todas as entregas válidas e buscando a localização física mais precisa possível.

Fluxo:

`XLSX → Delivery → evidências → localização da propriedade → ponto de acesso → PhysicalStop → matriz viária → otimização → sequência → mapa → navegação`

## Regras de negócio obrigatórias

- Nenhuma entrega válida deve ser descartada por ausência de GPS.
- `0,0` ou coordenada inválida deve ser tratada como GPS ausente.
- Usar todas as evidências disponíveis: latitude, longitude, endereço, número, quadra, lote, bairro, cidade, CEP e complemento.
- A identidade de PhysicalStop não depende somente de latitude/longitude.
- `Sequence` e `Stop` da planilha não determinam a ordem final nem a identidade física.
- Conflitos explícitos de endereço/número/quadra/lote devem impedir fusões inseguras.
- Propriedade e ponto de acesso viário são conceitos diferentes.
- Custos de rota vêm da malha viária, não de distância em linha reta.
- Todos os PhysicalStops válidos devem permanecer na rota e receber sequência contínua iniciando em 1.

## Estado atual da implementação

### Importer

- Importação XLSX real.
- Parser brasileiro de endereço.
- Evidências de número/quadra/lote.
- `Delivery` preservada mesmo sem GPS.
- Agrupamento conservador de PhysicalStops.
- Validação de cobertura.
- `GoianiaLocationProvider` integrado ao fluxo.
- Goiânia usa dados cadastrais oficiais de lotes/quadras/número predial/segmentos de logradouro.
- Quando `bairro + quadra + lote` estão disponíveis, o lote cadastral é priorizado para identificar a propriedade, inclusive quando existe GPS na planilha.
- O ponto cadastral da propriedade é usado para procurar candidato de acesso viário.
- Quando a resolução não é confiável, a entrega permanece pendente em vez de ser perdida.

### Routing

- OSRM.
- Matriz de TravelMetric.
- Tempo e distância.
- Origem/destino.
- Retorno ao início.
- Tratamento de trechos inacessíveis.
- Métricas derivadas da mesma matriz usada na otimização.

### Optimization

A implementação atual contém:

- objetivo por tempo ou distância;
- solução exata para rotas pequenas;
- heurísticas para rotas maiores;
- multi-start quando há origem livre;
- regret insertion;
- greedy fallback;
- 2-opt;
- desempate determinístico;
- suporte a origem, destino e retorno ao início;
- validação de rota completa.

A fase de auditoria da otimização foi encerrada sem necessidade de alteração estrutural adicional neste momento.

### Backend

FastAPI, autenticação, sessões, Argon2id, licenciamento, SQLite e endpoint de otimização estão integrados na base atual.

### Frontend

- upload XLSX;
- objetivos tempo/distância;
- origem/destino e retorno ao início;
- mapa Leaflet;
- marcadores numerados;
- lista/detalhes das paradas;
- navegação;
- botão `SEGUIR PARA A PRÓXIMA`;
- parada visitada visualmente em cinza;
- estado de visita reiniciado quando uma nova rota é carregada.

## Caso real importante

Existe um caso real sem GPS válido contendo endereço com `Rua SR 2`, `quadra 30`, `lote 24` e indicação de sobrado da esquina. Esse caso orientou a implementação de resolução cadastral por parcela e deve continuar sendo usado na validação manual.

Não usar dados pessoais reais de clientes em nova documentação ou testes além do que já estiver anonimizado/necessário no repositório.

## Testes

A suíte do importer chegou a `100 passed in 1.77s` no ambiente de desenvolvimento antes da última atualização de documentação.

O commit `ef6aee0897125a944578b7e91eae181480f7448c` disparou CI e revelou uma regressão de teste, não de lógica: `test_provider_can_resolve_missing_gps_from_neighborhood_block_and_lot` ainda esperava a origem antiga `goiania-cadastral-lot`, enquanto a implementação passou a retornar `goiania-cadastral-parcel` para resolução por parcela cadastral.

Essa expectativa foi corrigida no commit:

`92f402e11586b1459f54aaef1bcff7a571249b5c` — `test: align cadastral parcel source expectation`

O CI do commit `ef6aee...` foi confirmado como:

- importer: falhou com 105 passed / 1 failed devido somente à expectativa antiga;
- backend: sucesso;
- frontend: sucesso.

Após a correção, é obrigatório aguardar/consultar o novo CI antes de declarar a suíte verde.

## Roadmap

O roadmap oficial foi criado em:

`PROJECT_MEMORY/10_ROADMAP.md`

A próxima fase principal é **validação real no PC**, incluindo os três XLSX e o caso sem GPS. Depois vêm estabilização de produção, refinamento da precisão cadastral/acesso viário e, em seguida, a intervenção manual do motorista.

### Intervenção manual do motorista — planejada, não implementar agora

- selecionar uma parada;
- escolher/reinserir a posição na sequência;
- transformar a decisão em restrição real;
- recalcular a rota;
- reotimizar as demais paradas;
- atualizar mapa, métricas e navegação;
- permitir intervenções adicionais segundo regras definidas antes da implementação.

## Próximo passo após CI verde

1. Confirmar CI verde do commit de correção.
2. Fechar a validação automática da fase cadastral.
3. Fazer o primeiro teste real completo no PC.
4. Validar os três XLSX sem alterar os arquivos.
5. Validar especificamente entregas sem GPS.
6. Registrar resultados de deliveries, PhysicalStops, pontos roteados, pendências, distância, duração, localização, mapa e navegação.
7. Corrigir somente falhas reais encontradas.
8. Produzir relatório final de aceitação.

## O que ainda falta para o projeto ser considerado finalizado

### Obrigatório antes de uso real

- CI verde após a última correção.
- Teste manual completo no PC.
- Validação dos três XLSX reais.
- Validação do caso sem GPS válido.
- Repetibilidade da rota.
- Verificação de mapa e navegação em uso real.
- Medição de precisão da localização cadastral e do ponto de acesso.
- Tratamento de falhas de serviços externos em cenário real.

### Evolução técnica importante

- Melhorar a escolha da face/acesso do lote quando os dados cadastrais oficiais permitirem.
- Cache/index local de geometrias quando necessário para performance.
- Testes adicionais de evidências conflitantes/incompletas.
- Teste de carga com arquivos maiores.
- Revisão de dependências e warnings conhecidos.

### Produto/comercial

- Intervenção manual do motorista.
- Auditoria e limites de uso.
- Pagamentos Pix em produção.
- Segurança/observabilidade/deploy de produção.
- Refinamento comercial e UX.

## Regra de continuidade

Não recomeçar o projeto. Ler este arquivo e `PROJECT_MEMORY/10_ROADMAP.md` antes de alterar qualquer coisa.

Para cada alteração: verificar estado → uma alteração → testes → análise → diff → commit → push → confirmação no GitHub → próxima etapa.

Nunca inventar execução, resultado, commit ou CI. Nunca declarar o projeto pronto somente porque os testes automatizados passaram.
