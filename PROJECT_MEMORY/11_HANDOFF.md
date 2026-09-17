# Handoff — continuidade do Otimizer

## Repositório

`heldergaraujo2/Otimizer`, branch `main`.

## Objetivo

Transformar XLSX reais de entregas em rotas confiáveis pela rede viária real, preservando todas as entregas válidas e buscando a localização física mais precisa possível.

Fluxo principal:

`XLSX → Delivery → evidências → localização → PhysicalStop → matriz viária → otimização → sequência → mapa → navegação`

## Regras de negócio obrigatórias

- Nenhuma entrega válida pode ser descartada por ausência de GPS.
- `0,0` e coordenadas inválidas devem ser tratadas como GPS ausente.
- Usar todas as evidências disponíveis: latitude, longitude, endereço, número, quadra, lote, bairro, cidade, CEP e complemento.
- A identidade de `PhysicalStop` não depende somente de latitude/longitude.
- `Sequence` e `Stop` da planilha não determinam a ordem final.
- Conflitos explícitos de endereço/número/quadra/lote devem impedir fusões inseguras.
- Propriedade, acesso viário e ponto aproximado de rua são conceitos diferentes.
- Custos de rota devem vir da malha viária, não de distância em linha reta.
- Todas as paradas válidas devem permanecer representadas no resultado; problemas de localização/roteamento devem ser tratados individualmente.
- Uma parada problemática nunca deve derrubar a otimização das demais.
- Quando a rua correta puder ser determinada com confiança suficiente, um ponto aproximado na rua é preferível a excluir a entrega.

## Estado atual — validado no PC e Android

### Importação e otimização XLSX

O usuário realizou testes reais com **mais de 30 arquivos XLSX reais no PC**.

Resultado informado pelo usuário:

- todos os arquivos foram importados/otimizados corretamente;
- paradas não encontradas não derrubaram as demais paradas;
- as paradas que ficaram pendentes puderam ser adicionadas manualmente;
- após a inclusão manual, a rota foi recalculada/reotimizada sem problemas;
- o fluxo foi considerado **100% funcional conforme esperado**.

### Primeiro teste físico Android — APROVADO

Em 17/09/2026, o usuário validou no celular Android um fluxo operacional real usando o APK do projeto e backend local acessível pela rede LAN.

Fluxo validado com sucesso:

`instalação do APK → login → importação de novo XLSX → otimização → rota manual → reotimização`

Resultado informado pelo usuário:

- login funcionou perfeitamente;
- novo XLSX foi importado corretamente;
- otimização automática funcionou corretamente;
- rotas/paradas manuais também foram otimizadas corretamente;
- a comunicação Android → backend foi confirmada em ambiente físico.

Esse é o primeiro marco oficial de validação móvel do projeto. Ainda não equivale a aprovação para produção: faltam testes de campo mais amplos, estabilidade, segurança, backend remoto e atualização/distribuição do aplicativo.

### Localização cadastral / fallback

Goiânia utiliza fontes municipais oficiais para dados cadastrais e logradouros. O fluxo contém resolução cadastral e fallback de logradouro municipal.

Quando o ponto exato do imóvel não puder ser determinado, a regra é preservar a entrega e usar a melhor evidência disponível, inclusive ponto aproximado na rua correta quando aplicável.

### Rota manual

O autocomplete de rua consulta em tempo real a base municipal de Goiânia, especialmente o layer `10 — Logradouro por Bairro`.

Fluxo validado no PC:

`digitar rua → sugestões reais municipais → selecionar rua → adicionar parada → alfinete automático sobre a rua → ajuste manual opcional → otimização`

O usuário confirmou que:

- ruas reais foram encontradas;
- paradas foram adicionadas;
- o alfinete automático apareceu corretamente;
- o comportamento funcionou perfeitamente.

No Android, o fluxo de rota manual/reotimização também foi validado no primeiro teste físico.

A posição automática é um ponto da geometria da rua, não uma alegação de que o ponto seja a porta do imóvel. O clique manual continua disponível para ajuste fino.

## Implementação relevante recente

Além da implementação municipal, recuperação de pendências e proteção de seleção municipal obsoleta, a auditoria atual adicionou uma proteção específica na seleção cadastral:

- candidatos do Cadastro Imobiliário que contradizem evidência explícita de quadra, lote, número, bairro ou rua não são aceitos;
- quando, para uma entrega sem GPS, existem registros cadastrais para a quadra+lote informados, mas todos contradizem a evidência explícita, a entrega é colocada em quarentena como não resolvida em vez de cair para uma associação cadastral de lote mais fraca;
- a entrega não é removida: permanece disponível para resolução posterior/manual;
- candidatos compatíveis continuam seguindo a hierarquia cadastral existente, incluindo ponto do imóvel e acesso viário.

Commits desta alteração:

- `975e35f460d005af7bf94b350eb1b088c56b56a8` — proteção de conflito cadastral no runtime;
- `d89648771ff00c4c2309d8fd80c2521b89edb8a6` — testes de conflito explícito de número/rua e preservação da resolução compatível.

## Android / conectividade

O Android usa um WebView com shell HTTPS local e pode apontar o frontend para o backend por URL configurável via bridge JavaScript.

Correção aplicada para o primeiro teste físico:

- `a176930a305b18c36390d1571e43ed7ac68805c7` — WebView permite mixed content necessário ao backend HTTP LAN durante o teste;
- `90f89c962bfb2a8adecd4073ce234a707f69b802` — origem `https://appassets.androidplatform.net` adicionada ao CORS padrão do backend;
- `2afae71939b50b4e5bd8ef0c3dd50be892f57d5e` — teste automatizado da origem CORS do Android.

O problema que inicialmente produzia `OPTIONS /auth/login 400` foi eliminado, e o usuário confirmou login funcionando no APK.

O workflow de APK também foi validado anteriormente com sucesso e gera `app-debug.apk` como artefato do GitHub Actions.

## Sistema de atualização por patch

Requisito oficial registrado em `PROJECT_MEMORY/12_UPDATE_SYSTEM.md`.

Status: **PLANEJADO — NÃO IMPLEMENTAR AINDA**.

Objetivo futuro: permitir que alterações compatíveis de frontend/conteúdo sejam distribuídas como patch sem exigir novo APK; mudanças nativas Android continuam exigindo novo APK. O futuro Update Manager deverá considerar versão, compatibilidade, checksum, rollback e fallback seguro.

## Auditoria automatizada atual

No commit `2afae71939b50b4e5bd8ef0c3dd50be892f57d5e`, Backend e Frontend foram executados pelo GitHub Actions e concluíram com sucesso:

- Backend: **success**;
- Frontend: **success**;
- o teste específico da origem CORS Android foi incluído e passou no workflow de frontend/backend correspondente.

A árvore `main` contém atualmente quatro workflows ativos: Android APK, Backend tests, Frontend tests e Importer tests. Não foram encontrados workflows temporários de patch na listagem atual de `.github/workflows`.

A auditoria histórica anterior registrou **132 testes do Importer** e **71 do Backend**, com warnings de depreciação conhecidos no Backend. Esses números devem ser tratados como último resultado quantitativo explicitamente registrado, não como contagem inferida para qualquer execução posterior.

## Cobertura automatizada relevante

### XLSX e preservação

- linhas vazias;
- preservação das entregas;
- importação real já validada com mais de 30 arquivos;
- cenários de localização incompleta.

### Localização

- GPS;
- ausência de GPS;
- cadastro;
- quadra/lote;
- ponto cadastral;
- acesso viário;
- fallback de rua;
- proveniência/confiança;
- ponto municipal aproximado;
- conflito explícito de número/rua sem associação insegura.

### Stops

- diferenciação entre `Delivery` e `PhysicalStop`;
- proteção contra fusões incompatíveis;
- preservação de pendentes;
- entrega problemática permanece representada.

### Routing

- matriz OSRM;
- pares inacessíveis;
- pernas individuais sem rota;
- preservação de todas as paradas.

### Optimization

- origem;
- destino;
- retorno;
- determinismo;
- rotas grandes;
- parada inacessível;
- preservação de 100/100 entregas no cenário isolado;
- reotimização manual.

### Frontend / Android

- autocomplete municipal;
- alfinete municipal;
- invalidação de seleção municipal obsoleta;
- ajuste manual;
- navegação;
- pendências;
- login Android;
- importação XLSX Android;
- otimização Android;
- rota manual/reotimização Android.

## Ambiente local conhecido

Windows:

`D:\Otimizer\Otimizer-main`

Python:

`3.14.7`

Backend para teste físico Android:

```powershell
cd D:\Otimizer\Otimizer-main
.\.venv\Scripts\Activate.ps1
python -m uvicorn otimizer_api.main:app --host 0.0.0.0 --port 8000
```

O telefone utilizado no teste acessou o backend pela rede LAN do PC. A URL deve ser configurada conforme o IPv4 LAN atual do computador; não gravar IP de rede local como configuração de produção.

Frontend PC:

```powershell
cd D:\Otimizer\Otimizer-main
python -m http.server 8080 --directory frontend
```

URL:

`http://localhost:8080`

## Próxima fase

A validação funcional básica no PC e o primeiro fluxo operacional físico Android já foram concluídos. O projeto entra agora em **auditoria de robustez, estabilização e preparação para testes de campo**, sem recomeçar o projeto.

Prioridades restantes:

1. auditar completamente a árvore Git e consistência entre código, documentação e artefatos;
2. confirmar/registrar execução verde de todos os quatro workflows ativos no estado atual;
3. auditar regressões em importer, backend, routing, optimization, frontend e Android;
4. ampliar testes de conflitos cadastrais e casos de empate;
5. ampliar testes de múltiplas pernas não roteáveis;
6. ampliar testes de repetibilidade/determinismo;
7. testar performance com XLSX maiores;
8. revisar falhas, timeout e indisponibilidade de serviços externos;
9. revisar segurança, autenticação, sessões e licenciamento;
10. separar claramente configuração de desenvolvimento LAN da configuração de produção;
11. preparar backend remoto/deploy e configuração segura do aplicativo;
12. planejar distribuição do APK e assinatura de release;
13. manter o sistema de atualização por patch planejado, sem implementá-lo prematuramente;
14. manter README, documentação e `PROJECT_MEMORY` coerentes;
15. produzir relatório final de aceitação antes de declarar produção.

## Próximo ajuste técnico

O próximo trabalho deve privilegiar evidência e testes, não novas funcionalidades cosméticas.

A validação Android já comprovou o caminho operacional principal, mas ainda não valida cenários de campo como perda de conexão, backend remoto, grandes cargas, permissões do aparelho, retomada do aplicativo, múltiplos dispositivos e segurança de produção.

Depois de cada alteração significativa:

`verificar estado → uma alteração → testes → análise → diff → commit → push → confirmação no GitHub → próxima etapa`

## Regra de continuidade

Não recomeçar o projeto.

Nunca inventar execução, resultado, commit ou CI.

Nunca declarar o projeto pronto somente porque os testes automatizados passaram.

O objetivo agora é transformar a validação funcional já comprovada no PC e Android em uma base robusta, segura e auditada para evolução do produto.
