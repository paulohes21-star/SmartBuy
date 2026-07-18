PATCH SPRINT 7 — PÁGINA PRODUTOS

1. Faça backup do arquivo templates\products.html atual.
2. Copie templates\products.html deste pacote para a pasta templates do SmartBuy.
3. Copie static\products_sprint7_addon.css para a pasta static do SmartBuy.
4. No templates\base.html, adicione antes de </head>:
   <link rel="stylesheet" href="/static/products_sprint7_addon.css">
5. Reinicie o SmartBuy e atualize o navegador com Ctrl+F5.

O patch preserva as rotas, permissões, filtros, importação Excel e busca inteligente já existentes.
