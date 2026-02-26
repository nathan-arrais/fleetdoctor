# Pitch de 3 minutos

## 1) O que o sistema faz (30s)
- FleetDoctor prioriza ocorrencias de frota e gera diagnostico operacional com IA.
- O backend combina contexto de eventos/viagens e produz recomendacoes acionaveis.

## 2) Decisoes de engenharia de LLM (2min)
- Modelo: local via Ollama (custo zero por chamada e privacidade).
- Framework: LangGraph simples para controlar fluxo e fallback.
- Prompt: system prompt com JSON estrito, guardrails anti-injecao e estilo operacional.
- Parametros: temperatura baixa para consistencia (`0.2`), `top_p=0.9`, timeout configuravel.
- Tools: contexto de evento/viagem, similares e historico de veiculo.
- Fallback: se modelo falhar ou JSON vier invalido, usa motor deterministico.

## 3) O que funcionou e nao funcionou (30s)
- Funcionou: respostas mais contextualizadas mantendo contrato de API.
- Nao funcionou: com modelo local pequeno, algumas respostas vieram genéricas.
- Mitigacao: validacao estrutural + fallback deterministico.
