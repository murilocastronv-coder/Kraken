# Kraken Paper Trader para Render

**Modo exclusivamente simulado:** não precisa de API Key, não lê saldo real e não contém comandos de ordens reais. Usa o Kraken CLI apenas para cotação pública (`kraken ticker`).

## Publicação
1. Envie estes arquivos para um repositório GitHub seu.
2. No Render escolha **New → Blueprint**, selecione o repositório e aplique `render.yaml`.
3. O serviço usa Docker e disco persistente de 1 GB; o plano Starter está configurado no blueprint.
4. Abra a URL do serviço no Chrome Android e toque em **Iniciar robô demo**.

## Estratégia didática
Consulta preço a cada 15 segundos e usa médias de 9 e 21 amostras. Compra simulada com 10% do caixa quando a média curta fica acima da longa e vende quando fica abaixo. Primeiro sinal após 21 amostras. Não é recomendação financeira e não garante lucro.

## Segurança e limitações
- Não coloque API keys ou secrets no Render para este app.
- Não há chamadas a `kraken order`; as operações são simuladas internamente.
- Kraken CLI é experimental e pode mudar o formato de saída; confira os logs do Render após publicar.
