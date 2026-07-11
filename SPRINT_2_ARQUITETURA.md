# Arquitetura da Sprint 2

## Catálogo mestre

`products` contém dados compartilhados: código interno, descrição, categoria, marca, unidade, NCM, impostos, códigos ERP e de barras, fornecedor padrão e status.

## Estoque por empresa

`product_company_settings` contém dados específicos de cada CNPJ: mínimo, máximo, lead time, localização, custo médio, último custo, última compra e saldo atual.

## Histórico

Toda criação e alteração de produto gera um snapshot em `product_history`. A auditoria geral continua registrando o ator e a ação.

## Excel

A importação utiliza cabeçalhos estáveis e faz atualização por código interno. As linhas são validadas individualmente; erros são apresentados sem apagar registros válidos. A exportação respeita os filtros atuais.

## Escalabilidade

As consultas são paginadas no servidor e os campos usados em busca possuem índices. A estrutura poderá migrar de SQLite para PostgreSQL sem alterar a regra de negócio.
