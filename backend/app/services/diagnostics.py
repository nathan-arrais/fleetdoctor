from typing import List
from sqlalchemy.orm import Session
from ..models import Event, Trip


def _severity_rank(sev: str) -> int:
    return {"low": 1, "medium": 2, "high": 3, "critical": 4}.get(sev, 1)


def diagnose_event(event: Event) -> dict:
    evidence = []
    probable_causes = []
    recommended_actions = []
    summary = ""

    if event.type == "delay":
        summary = "Atraso acima do esperado no trajeto."
        probable_causes = [
            "Congestionamento na rota",
            "Paradas não planejadas",
            "Desvio de rota",
        ]
        recommended_actions = [
            "Validar rota atual e conferir bloqueios",
            "Revisar tempo de carga/descarga",
            "Ajustar janela de entrega se necessario",
        ]
        if event.value is not None and event.threshold is not None:
            evidence.append(
                f"Atraso de {event.value:.0f} min (limite {event.threshold:.0f} min)."
            )
    elif event.type == "temp_out_of_range":
        summary = "Temperatura fora da faixa operacional."
        probable_causes = [
            "Falha no sistema de refrigeração",
            "Abertura frequente de portas",
            "Calibração incorreta do sensor",
        ]
        recommended_actions = [
            "Verificar unidade de refrigeração",
            "Inspecionar vedação das portas",
            "Recalibrar sensor de temperatura",
        ]
        if event.value is not None and event.threshold is not None:
            evidence.append(
                f"Temperatura registrada {event.value:.1f} C (limite {event.threshold:.1f} C)."
            )
    elif event.type == "excessive_stops":
        summary = "Número de paradas acima do planejado."
        probable_causes = [
            "Rotas com muitos checkpoints",
            "Pausas prolongadas de motorista",
            "Interferências de tráfego",
        ]
        recommended_actions = [
            "Revisar planejamento de paradas",
            "Ajustar janelas de descanso",
            "Treinar para manter ritmo operacional",
        ]
        if event.value is not None and event.threshold is not None:
            evidence.append(
                f"Paradas {event.value:.0f} (limite {event.threshold:.0f})."
            )
    elif event.type == "excessive_idle":
        summary = "Tempo parado elevado durante a viagem."
        probable_causes = [
            "Espera em docas",
            "Pausas não planejadas",
            "Falhas operacionais locais",
        ]
        recommended_actions = [
            "Confirmar SLA de docas",
            "Revisar disciplina de paradas",
            "Criar alertas de idle em tempo real",
        ]
        if event.value is not None and event.threshold is not None:
            evidence.append(
                f"Tempo parado {event.value:.0f} min (limite {event.threshold:.0f} min)."
            )
    else:
        summary = "Evento operacional detectado."
        probable_causes = ["Variação operacional", "Comunicação incompleta"]
        recommended_actions = ["Validar dados da telemetria"]

    if not evidence:
        evidence.append(f"Evento registrado em {event.timestamp.isoformat()}.")

    return {
        "severity": event.severity,
        "summary": summary,
        "probable_causes": probable_causes,
        "recommended_actions": recommended_actions,
        "evidence": evidence,
    }


def diagnose_trip(session: Session, trip: Trip) -> dict:
    events = session.query(Event).filter(Event.trip_id == trip.id).all()
    if not events:
        return {
            "severity": "low",
            "summary": "Viagem sem eventos relevantes.",
            "probable_causes": ["Operação dentro do padrão"],
            "recommended_actions": ["Manter monitoramento"],
            "evidence": ["Nenhum evento associado."],
        }

    top_sev = max(events, key=lambda e: _severity_rank(e.severity)).severity
    types = {e.type for e in events}
    summary = "Múltiplos eventos detectados na viagem." if len(types) > 1 else "Evento recorrente na viagem."

    evidence = [f"Total de eventos: {len(events)}."]
    evidence.extend([f"Tipo detectado: {t}." for t in sorted(types)])

    probable_causes = [
        "Variação de tráfego e janelas de entrega",
        "Condições de rota inconsistentes",
    ]

    recommended_actions = [
        "Revisar plano de rota e buffers",
        "Agendar revisão preventiva",
    ]

    return {
        "severity": top_sev,
        "summary": summary,
        "probable_causes": probable_causes,
        "recommended_actions": recommended_actions,
        "evidence": evidence,
    }
