# Sprint 5 — Motor Inteligente de Compras

## Objetivo

Calcular reposição, ruptura, Curva ABC, giro e fornecedor recomendado com
base em dados operacionais registrados por produto e empresa.

## Fórmulas

### Consumo médio diário

`consumo do período / dias do período`

O período pode ser 1, 2, 3, 6 ou 12 meses.

### Estoque disponível

`estoque atual - reservado + em pedidos`

### Estoque de segurança

`consumo médio diário × dias de segurança`

### Ponto de reposição

`consumo médio diário × lead time + estoque de segurança`

### Estoque-alvo

`consumo médio diário × dias de cobertura + estoque de segurança`

### Sugestão de compra

A recomendação só é gerada quando o disponível é menor ou igual ao ponto
de reposição:

`máximo(estoque-alvo - disponível, 0)`

### Cobertura e ruptura

`estoque disponível / consumo médio diário`

### Custo médio

O custo médio é ponderado pela quantidade quando há quantidade informada.
Na ausência de quantidades, utiliza a média simples dos registros.

### Curva ABC

Classificação pelo valor anual consumido:

- A: até 80% do valor acumulado;
- B: de 80% a 95%;
- C: restante.

### Giro

`consumo anual / estoque médio`

O estoque médio vem das fotografias diárias. Até existirem fotografias, o
sistema utiliza o estoque atual como aproximação e deixa essa limitação
documentada.

## Cotação inteligente

O custo final unitário considera:

`preço unitário + (frete + impostos - desconto) / quantidade`

O custo final é o critério principal. Lead time, score e preferência são
usados apenas como desempate, evitando esconder uma diferença relevante
de preço.

## Preparação para IA

A Sprint registra eventos estruturados suficientes para uma camada futura:

- consumo;
- estoque;
- custos;
- fornecedores;
- cotações;
- políticas;
- decisões calculadas.

Nenhum modelo de IA é necessário nesta etapa. As recomendações permanecem
explicáveis e auditáveis.
