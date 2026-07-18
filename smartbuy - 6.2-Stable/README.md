# SmartBuy — Sprint 2 nativa para Windows

Esta versão preserva login, usuários, empresas, permissões e auditoria da Sprint 1 e adiciona gestão profissional de catálogo e estoque.

## Como atualizar

1. Faça uma cópia de segurança da pasta antiga.
2. Extraia esta Sprint 2 em uma nova pasta.
3. Para preservar os dados existentes, copie o arquivo antigo `data/smartbuy.db` para a pasta `data` desta Sprint 2.
4. Execute `INICIAR_SMARTBUY.bat`.
5. O banco será atualizado automaticamente, sem apagar os dados anteriores.

## Login inicial

- E-mail: `admin@smartbuy.local`
- Senha: `SmartBuy@123`

## Módulos adicionados

- categorias;
- marcas;
- fornecedores;
- unidades de medida;
- cadastro mestre de produtos;
- parâmetros de estoque e custo por empresa;
- pesquisa, filtros, paginação e ordenação;
- importação e exportação Excel;
- modelo Excel para preenchimento;
- histórico de alterações;
- auditoria.

## Decisão de arquitetura

O produto é cadastrado uma única vez. Estoque mínimo, máximo, localização, lead time, custos e última compra são mantidos por empresa em `product_company_settings`. Isso evita duplicar o catálogo e prepara o sistema para analisar várias filiais.

## Executar testes

```cmd
.venv\Scripts\python -m pytest
```

## Endereço

`http://127.0.0.1:8000`
