# Carregador Base Demonstração GW

- Importação de três empresas fictícias.
- Importação de fornecedores, produtos, estoques e movimentações.
- Backup automático do banco.
- Carga idempotente usando prefixo GWTEST-.
- Geração de custos, cotações e snapshots para o motor.
- Validação automática das recomendações.

# SmartBuy 6.4.0 — Enterprise Design System

- Padronização visual da Inteligência de Compras.
- Cabeçalho executivo e status do motor.
- KPIs com contexto operacional.
- Curva ABC calculada com dados reais.
- Tendência de demanda dos últimos sete meses.
- Indicadores de saúde do estoque.
- Tabela Enterprise com busca instantânea e severidade visual.
- Responsividade, acessibilidade e redução de movimento.
- Nenhuma alteração no banco de dados ou nas APIs existentes.


# SmartBuy 6.4.1 — AI Decision Center

- Resumo executivo determinístico baseado nas recomendações reais.
- Top 5 prioridades de compra com justificativa auditável.
- Indicadores de investimento, itens críticos, capital sem consumo e fornecedores pendentes.
- Plano de próximas ações recomendado.
- Nenhuma API externa de IA.
- Nenhuma alteração de banco de dados, API ou regra do motor de compras.


# SmartBuy 6.4.2 — Workspace Operacional

- Devolve protagonismo ao estoque e às recomendações operacionais.
- Move o Workspace Operacional para antes do AI Decision Center.
- Mantém o SmartBuy AI Decision Center integralmente.
- Adiciona filtros rápidos: todos, comprar, críticos e atenção.
- Adiciona busca instantânea por produto e fornecedor.
- Adiciona ordenação nas colunas.
- Adiciona paginação configurável.
- Mantém cabeçalho da tabela fixo durante a rolagem.
- Mantém as colunas ABC e Produto fixas na rolagem horizontal.
- Liga as prioridades da IA às linhas correspondentes no estoque.
- Não altera banco de dados, APIs ou regras do motor de compras.


# SmartBuy 6.4.3 — Workspace Operacional Premium

- Cabeçalho operacional com resumo de produtos, críticos, compras e itens saudáveis.
- Filtros rápidos premium com contadores.
- Busca ampliada por código, produto e fornecedor.
- Produto exibido como mini-card com fornecedor e estado de saúde.
- Sugestão de compra transformada em ação para gerar cotação.
- Hover, foco e hierarquia visual aprimorados.
- Paginação com botões numerados.
- Cabeçalho e colunas fixas preservados.
- Responsividade e acessibilidade revisadas.
- Nenhuma alteração no banco, APIs ou motor de compras.


# SmartBuy 6.4.4 — IA integrada ao Workspace

- Clique em prioridade da IA localiza automaticamente o SKU.
- Filtro rápido é aplicado conforme criticidade.
- Linha do produto recebe destaque temporário.
- Painel lateral Explain Engine mostra a justificativa determinística.
- Métricas operacionais são exibidas no painel lateral.
- Botão de geração de cotação disponível dentro da explicação.
- Botão Explicar adicionado às linhas com compra recomendada.
- Nenhuma alteração no banco, APIs ou motor de compras.


# SmartBuy 6.5.1 — Smart Cart

- Carrinho inteligente integrado ao Workspace Operacional.
- Seleção individual de SKUs recomendados.
- Inclusão automática de todos os itens críticos.
- Agrupamento visual por fornecedor.
- Total estimado da sessão.
- Persistência no navegador durante a sessão.
- Sincronização visual entre carrinho e linhas da tabela.
- Nenhuma alteração no banco de dados, APIs, PDFs ou motor de compras.
- A consolidação definitiva por empresa e fornecedor será entregue no próximo passo.


# SmartBuy 6.5.2 — Cotação Consolidada Automática

- Remove integralmente o Smart Cart da Inteligência de Compras.
- O SmartBuy volta a selecionar automaticamente todos os itens recomendados.
- Consolidação automática por empresa e fornecedor.
- Uma única solicitação reúne todos os SKUs do mesmo grupo.
- Tela de revisão permite retirar um SKU sem excluir o produto do sistema.
- Totais, mensagens, WhatsApp, e-mail e PDF respeitam os SKUs retirados.
- Opção de restaurar todos os SKUs retirados.
- Nenhuma alteração no banco de dados ou no motor de compras.


# SmartBuy 6.5.3 — Smart Quotation Engine

- Remove definitivamente o conceito de carrinho.
- Consolida automaticamente todos os SKUs em um único pacote por fornecedor.
- Permite combinar SKUs de empresas diferentes no mesmo envio ao fornecedor.
- Identifica a empresa solicitante em cada linha.
- Cria uma única mensagem, um único e-mail e um único PDF por fornecedor.
- Permite retirar individualmente um SKU durante a revisão.
- Recalcula valores, quantidades e documentos após cada retirada.
- PDF consolidado passou a apresentar empresas e SKUs no mesmo documento.
- Nenhuma alteração no banco de dados ou no motor de recomendação.


# SmartBuy 6.5.4 — RFQ Enterprise Consolidation

- Consolidação de fornecedores por CNPJ.
- Fallback por razão social/nome normalizado quando o CNPJ não existir.
- Unificação automática de cadastros duplicados.
- Um único pacote, PDF, e-mail e WhatsApp por fornecedor real.
- Consolidação do mesmo SKU entre empresas.
- Quantidade total por SKU e distribuição por empresa.
- Painel executivo de negociação por fornecedor.
- Retirada seletiva por empresa/SKU com recálculo automático.
- PDF consolidado redesenhado.
- Nenhuma alteração no banco de dados ou motor de compras.


# SmartBuy 6.5.5 — Central de Cotações Enterprise

- Interface totalmente reorganizada no padrão da Inteligência de Compras.
- Um único pacote visual por fornecedor.
- Todos os SKUs consolidados exibidos em tabela compacta.
- Empresas, quantidade, cobertura, preço e valor estimado visíveis.
- Retirada de SKU preservada.
- PDF, e-mail, WhatsApp e cópia preservados.
- Busca instantânea por fornecedor ou SKU.
- Layout responsivo e acessível.
- Nenhuma alteração no banco, APIs, motor, PDF ou regras de negócio.


# SmartBuy 6.5.6 — Central de Cotações Visual Oficial

- Página reconstruída conforme a referência visual oficial aprovada.
- Compatibilidade corrigida com os dados reais `rfq.items` do backend atual.
- Linhas de SKU, empresas, quantidades, cobertura e valores restauradas.
- Um pacote visual por grupo de fornecedor recebido do backend.
- PDF, e-mail, WhatsApp, copiar e retirar SKU preservados.
- Busca instantânea por fornecedor, SKU ou produto.
- Pacotes recolhíveis e detalhes das empresas sob demanda.
- Nenhuma alteração no banco, APIs, SQL, motor ou regras de negócio.


# SmartBuy 6.5.7 — Premium Visual Polish

- Refinamento exclusivamente visual da Central de Cotações.
- Nova hierarquia tipográfica e melhor contraste.
- Indicadores principais com leitura mais rápida.
- Tabelas mais densas, legíveis e profissionais.
- Cabeçalhos e rodapés de fornecedores mais equilibrados.
- Espaçamentos e alinhamentos padronizados.
- Botões e estados visuais refinados.
- Responsividade aprimorada.
- Nenhuma funcionalidade, rota, regra, API, banco ou lógica foi alterada.


# SmartBuy 6.5.8 — Premium Scale & Density

- Página ampliada para aproveitar toda a área útil do desktop.
- Título, fornecedores, valores e totais ganharam maior presença visual.
- KPIs do topo ampliados e com melhor hierarquia.
- Tabela transformada no elemento dominante da negociação.
- Tipografia e espaçamentos aumentados para monitores grandes.
- Rodapé financeiro reorganizado visualmente, sem mover funcionalidades.
- Botões preservados e visualmente reforçados.
- Responsividade aprimorada.
- Nenhuma funcionalidade, rota, banco, API, regra ou lógica foi alterada.

