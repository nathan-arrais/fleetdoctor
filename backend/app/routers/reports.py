import os
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from sqlalchemy.orm import Session
from ..deps import get_db
from ..models import Report
from ..schemas import ReportOut, ReportGenerateRequest
from ..services.reports import generate_report_html

router = APIRouter()

REPORTS_DIR = os.path.join(os.path.dirname(__file__), "..", "reports_store")
REPORTS_DIR = os.path.abspath(REPORTS_DIR)


def _ensure_reports_dir():
    os.makedirs(REPORTS_DIR, exist_ok=True)


def _report_urls(report_id: int):
    return {
        "preview_url": f"/api/reports/{report_id}/preview",
        "download_url": f"/api/reports/{report_id}/download",
    }


@router.post("/reports/generate", response_model=ReportOut)
def generate_report(payload: ReportGenerateRequest, db: Session = Depends(get_db)):
    _ensure_reports_dir()
    html = generate_report_html(
        db,
        payload.start,
        payload.end,
        payload.region,
        payload.status,
        payload.event_type,
        payload.severity,
        payload.q,
    )
    created_at = datetime.utcnow()
    file_name = f"fleetdoctor_report_{created_at.strftime('%Y%m%d_%H%M%S')}.html"
    file_path = os.path.join(REPORTS_DIR, file_name)

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(html)

    report = Report(
        created_at=created_at,
        report_type=payload.type,
        start=payload.start,
        end=payload.end,
        region=payload.region,
        status_filter=payload.status,
        type_filter=payload.event_type,
        severity_filter=payload.severity,
        query_filter=payload.q,
        html_content=html,
        file_name=file_name,
        file_path=file_path,
    )
    db.add(report)
    db.commit()
    db.refresh(report)

    urls = _report_urls(report.id)
    out = ReportOut.model_validate(report)
    out.report_id = report.id
    out.preview_url = urls["preview_url"]
    out.download_url = urls["download_url"]
    return out


@router.get("/reports", response_model=list[ReportOut])
def list_reports(db: Session = Depends(get_db)):
    reports = db.query(Report).order_by(Report.created_at.desc()).all()
    output = []
    for r in reports:
        urls = _report_urls(r.id)
        out = ReportOut.model_validate(r)
        out.report_id = r.id
        out.preview_url = urls["preview_url"]
        out.download_url = urls["download_url"]
        output.append(out)
    return output


@router.get("/reports/{report_id}/download")
def download_report(report_id: int, db: Session = Depends(get_db)):
    report = db.query(Report).filter(Report.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    if not report.file_path or not os.path.exists(report.file_path):
        raise HTTPException(status_code=404, detail="Report file missing")

    return FileResponse(report.file_path, filename=report.file_name, media_type="text/html")


@router.get("/reports/{report_id}/preview")
def preview_report(report_id: int, db: Session = Depends(get_db)):
    report = db.query(Report).filter(Report.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    if report.file_path and os.path.exists(report.file_path):
        with open(report.file_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(content=report.html_content)
