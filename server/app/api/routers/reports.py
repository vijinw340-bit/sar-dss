"""Report generation, listing, download and email delivery."""
import os
import smtplib
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.models import Mission, Report, User
from app.schemas import ReportOut
from app.services import report_pdf

router = APIRouter(prefix="/missions", tags=["Reports"])


@router.post("/{mission_id}/reports", response_model=ReportOut, status_code=status.HTTP_201_CREATED)
def generate_report(
    mission_id: int,
    include_map: bool = Query(default=True),
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    """Generate a professional PDF report for a mission."""
    mission = db.get(Mission, mission_id)
    if not mission:
        raise HTTPException(status_code=404, detail="Mission not found")
    filepath = report_pdf.generate_mission_report(mission, current.full_name)
    report = Report(
        mission_id=mission.id,
        report_type="pdf",
        title=f"{mission.mission_name} - SAR Analysis Report",
        file_path=filepath,
        generated_by=current.id,
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return report


@router.get("/{mission_id}/reports", response_model=list[ReportOut])
def list_reports(
    mission_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """List all reports generated for a mission."""
    mission = db.get(Mission, mission_id)
    if not mission:
        raise HTTPException(status_code=404, detail="Mission not found")
    return (
        db.query(Report)
        .filter(Report.mission_id == mission_id)
        .order_by(Report.created_at.desc())
        .all()
    )


@router.get("/reports/{report_id}/download")
def download_report(
    report_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Download a generated report file."""
    report = db.get(Report, report_id)
    if not report or not os.path.exists(report.file_path):
        raise HTTPException(status_code=404, detail="Report file not found")
    return FileResponse(
        report.file_path,
        media_type="application/pdf",
        filename=os.path.basename(report.file_path),
    )


@router.post("/{mission_id}/reports/{report_id}/email")
def email_report(
    mission_id: int,
    report_id: int,
    to: str = Query(...),
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    """Email a report to a recipient using SMTP env settings (if configured)."""
    report = db.get(Report, report_id)
    if not report or report.mission_id != mission_id:
        raise HTTPException(status_code=404, detail="Report not found")
    if not os.path.exists(report.file_path):
        raise HTTPException(status_code=404, detail="Report file missing")

    smtp_host = os.getenv("SMTP_HOST")
    smtp_user = os.getenv("SMTP_USER")
    smtp_pass = os.getenv("SMTP_PASSWORD")
    mail_from = os.getenv("SMTP_FROM", settings.ADMIN_EMAIL)
    if not smtp_host:
        raise HTTPException(
            status_code=501,
            detail="SMTP not configured on this server",
        )

    msg = MIMEMultipart()
    msg["Subject"] = f"SAR-DSS Report: {report.title}"
    msg["From"] = mail_from
    msg["To"] = to
    msg.attach(MIMEText(f"Please find the SAR analysis report '{report.title}' attached.", "plain"))
    with open(report.file_path, "rb") as fh:
        part = MIMEApplication(fh.read(), _subtype="pdf")
        part.add_header("Content-Disposition", "attachment", filename=os.path.basename(report.file_path))
        msg.attach(part)

    port = int(os.getenv("SMTP_PORT", "587"))
    use_tls = os.getenv("SMTP_TLS", "true").lower() == "true"
    with smtplib.SMTP(smtp_host, port, timeout=20) as server:
        if use_tls:
            server.starttls()
        if smtp_user and smtp_pass:
            server.login(smtp_user, smtp_pass)
        server.sendmail(mail_from, [to], msg.as_string())

    from app.services.mission_engine import log_activity

    log_activity(db, report.mission, current.id, "report_emailed", f"Report emailed to {to}")
    return {"status": "sent", "to": to}
