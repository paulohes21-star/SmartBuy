# Sprint 3 — Cadastros Mestres

## Objetivo

Criar a base fiscal e logística reutilizada pelos módulos de produtos,
estoque, compras e integrações com ERP.

## Cadastros entregues

- fabricantes;
- NCM;
- CFOP;
- CST ICMS;
- CST IPI;
- depósitos por empresa;
- localizações por depósito.

Categorias, marcas e unidades já existentes na Sprint 2 permanecem preservadas.

## Decisões de arquitetura

### Separação por empresa

Depósitos pertencem a uma empresa. Isso evita misturar estoques de CNPJs
diferentes e prepara transferências internas entre empresas.

### Localização hierárquica

A localização pertence a um depósito e pode registrar corredor, estante,
nível e posição. O código continua livre para compatibilidade com o ERP.

### Cadastro fiscal centralizado

NCM, CFOP e CST ficam centralizados, evitando textos digitados livremente
em cada produto ou pedido.

### Exclusão lógica

Os registros são ativados e inativados. Não são apagados, preservando
integridade histórica para produtos, notas e pedidos futuros.

### Permissões

- `master_data.read`
- `master_data.write`

ADMIN e MANAGER podem consultar e alterar. VIEWER pode apenas consultar.

## Migração

A migração é incremental e idempotente. `CREATE TABLE IF NOT EXISTS` e
`INSERT OR IGNORE` permitem reiniciar o sistema sem duplicar estruturas.

## Próxima sprint

A Sprint 4 deverá relacionar produtos aos novos cadastros por chaves
estrangeiras e migrar gradualmente os campos fiscais livres.
