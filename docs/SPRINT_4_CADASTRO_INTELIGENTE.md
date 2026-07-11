# Sprint 4 — Cadastro Inteligente de Produtos

## Objetivo

Evoluir o catálogo existente sem duplicar o módulo de produtos.

## Recursos

- pesquisa por código interno, ERP, barras, descrição, referência de fabricante
  e códigos externos;
- verificação de duplicidades;
- códigos externos por ERP e empresa;
- importação Excel em validação e confirmação;
- atualização de produtos existentes pelo código interno;
- transação única na confirmação;
- auditoria;
- permissões específicas;
- migração idempotente.

## Modelo de integração ERP

`product_external_codes` desacopla o produto interno do código usado em cada
sistema. A chave de integração é composta por:

- sistema de origem;
- empresa, quando aplicável;
- código externo.

Um produto pode ter vários códigos, sem alterar seu código interno.

## Importação

1. Upload do XLSX.
2. Validação de cabeçalho e cadastros auxiliares.
3. Classificação de cada linha como CREATE ou UPDATE.
4. Registro do lote e das linhas.
5. Exibição dos erros.
6. Confirmação somente quando todas as linhas estiverem válidas.
7. Gravação transacional.
8. Auditoria e histórico.

## Segurança

O token aleatório do lote impede confirmação acidental por URL. A confirmação
também verifica status e quantidade de erros.

## Limitação consciente

A Sprint 4 prepara a integração, mas não abre conexão direta com o ERP. Essa
conexão exigirá levantamento do banco, credenciais somente leitura, mapeamento
de tabelas e política de sincronização.
