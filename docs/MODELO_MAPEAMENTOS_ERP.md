# Modelos de mapeamento

## Produtos

```json
{
  "internal_code": "COD_PRODUTO",
  "description": "DESCRICAO",
  "unit_code": "UNIDADE",
  "ncm": "NCM",
  "erp_code": "COD_ERP"
}
```

## Estoque

```json
{
  "product_code": "COD_PRODUTO",
  "company_code": "COD_EMPRESA",
  "current_stock": "ESTOQUE_ATUAL",
  "reserved_stock": "ESTOQUE_RESERVADO",
  "on_order_stock": "EM_PEDIDOS"
}
```

## Consumo

```json
{
  "product_code": "COD_PRODUTO",
  "company_code": "COD_EMPRESA",
  "quantity": "QUANTIDADE",
  "movement_date": "DATA",
  "reference_number": "DOCUMENTO"
}
```

## Compras

```json
{
  "product_code": "COD_PRODUTO",
  "company_code": "COD_EMPRESA",
  "unit_cost": "CUSTO_UNITARIO",
  "quantity": "QUANTIDADE",
  "purchase_date": "DATA_COMPRA",
  "reference_number": "NOTA_FISCAL"
}
```
