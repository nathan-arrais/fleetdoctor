# Pitch de 3 minutos

## 1) O que o sistema faz (30s)
- FleetDoctor prioriza ocorrências de frota, gera diagnóstico operacional com IA e oferece chat para perguntas livres sobre a operação.
- O backend combina contexto de eventos/viagens/KPIs e produz respostas acionaveis.

## 2) Decisoes de engenharia de LLM (2min)
- Modelo: local via Ollama (custo zero por chamada e privacidade).
- Framework: LangGraph simples para controlar fluxo e fallback.
- Prompt: system prompt com JSON estrito, guardrails anti-injecao e estilo operacional.
- Parâmetros: temperatura baixa para consistência (`0.2`), `top_p=0.9`, timeout configurável.
- Tools: contexto de evento/viagem, histórico de veículo, snapshot de dashboard e top riscos para o chat.
- Fallback: se modelo falhar ou JSON vier inválido, usa motor determinístico.

## 3) O que funcionou e não funcionou (30s)
- Funcionou: respostas mais contextualizadas mantendo contrato de API.
- Não funcionou: com modelo local pequeno, algumas respostas vieram genéricas.
- Mitigação: validação estrutural + fallback determinístico.
