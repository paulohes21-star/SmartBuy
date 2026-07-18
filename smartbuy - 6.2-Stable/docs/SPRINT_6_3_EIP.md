# Sprint 6.3 — Enterprise Integration Platform

## Objetivo

Evoluir a integração existente sem conectar diretamente o Motor de Compras
a qualquer banco de ERP.

## Arquitetura

ERP / arquivo / API
→ Connector Registry
→ Connector Manager
→ Preview / Health / Sync
→ Staging Data Lake
→ Data Quality
→ Promoção para o modelo canônico
→ Purchasing Intelligence Core

## Componentes entregues

- contratos tipados de conectores;
- catálogo de capacidades;
- validação SemVer;
- registro runtime de conectores;
- Connector Manager;
- health snapshots persistentes;
- cache com TTL;
- eventos de integração;
- consulta ao staging;
- API interna versionável;
- migração idempotente.

## Limite desta sprint

A Sprint 6.3 não inclui credenciais nem consultas ao banco da GW.
O próximo passo será o levantamento técnico do ERP e a criação de um
conector GW somente leitura.
