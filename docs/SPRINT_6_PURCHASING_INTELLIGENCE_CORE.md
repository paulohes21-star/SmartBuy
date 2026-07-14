# Sprint 6 — Purchasing Intelligence Core

## Objetivo

Criar uma camada genérica, segura e auditável entre ERPs externos e o motor
de compras do SmartBuy.

## Arquitetura

1. **Connector:** somente leitura da fonte.
2. **Mapper:** traduz colunas externas para campos canônicos.
3. **Normalizer:** padroniza códigos, números e datas.
4. **Staging:** preserva o registro bruto e o canônico.
5. **Data Quality:** classifica erros e alertas.
6. **Promotion:** atualiza o SmartBuy somente após validação.
7. **Decision API:** expõe recomendações explicáveis.

## Segurança

- Credenciais não são persistidas no SQLite.
- `secret_env_prefix` informa somente o prefixo das variáveis.
- Exemplo:
  - `GW_ERP_USER`
  - `GW_ERP_PASSWORD`
- Consultas de banco devem começar com `SELECT`.
- Os conectores de banco realizam teste de leitura.
- `.env` é ignorado pelo Git.

## Conectores

CSV e Excel funcionam sem dependências adicionais. Os conectores de banco
são opcionais:

- SQL Server: `pyodbc`
- PostgreSQL: `psycopg[binary]`
- MySQL: `mysql-connector-python`
- Firebird: `firebird-driver`
- Oracle: `oracledb`

A instalação do driver só deve ocorrer quando a tecnologia real da GW for
identificada.

## Entidades canônicas

- PRODUCT
- INVENTORY
- CONSUMPTION
- PURCHASE
- SUPPLIER
- OPEN_ORDER

## Idempotência

- Cada registro de staging possui hash SHA-256.
- A mesma fonte, entidade e hash não são inseridos duas vezes.
- Produtos são atualizados por código interno.
- Consumos usam produto, empresa, data, referência e quantidade para evitar
  duplicidade.
- Configurações de estoque usam UPSERT por produto e empresa.

## Limitações desta Sprint

- Não há conexão com o banco real da GW.
- O agendamento automático fica para uma fase posterior.
- O conector REST suporta GET e token Bearer.
- A promoção de PURCHASE registra o histórico, mas o recálculo financeiro
  detalhado continuará no motor de compras.
