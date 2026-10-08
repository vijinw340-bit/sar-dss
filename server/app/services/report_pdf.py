"""Professional PDF report generation with ReportLab + Matplotlib.

The report includes mission details, search parameters, weather/wind, coverage,
probability map, search pattern, sector details, officer name and timestamps.
A real OSM static map image is attempted; matplotlib fallback plots guarantee
the report still renders offline.
"""
import io
import json
import math
import os
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Image,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.models import Mission  # noqa: E402
from app.services import gis  # noqa: E402

NAVY = colors.HexColor("#0f2a4a")
BLUE = colors.HexColor("#1d4ed8")
LIGHT = colors.HexColor("#f1f5f9")

OUTPUT_DIR = settings.REPORT_DIR
os.makedirs(OUTPUT_DIR, exist_ok=True)


# ---------------------------------------------------------------- map images
def _fetch_static_map(lat: float, lon: float, radius_nm: float) -> bytes | None:
    """Try to assemble a static map PNG from relayed tiles; None on any failure."""
    try:
        from app.services.static_map import build_static_map

        data = build_static_map(lat, lon, radius_nm, width=840, height=460)
        return data if len(data) > 2000 else None
    except Exception:
        return None


def _make_probability_figure(mission: Mission) -> bytes:
    """Matplotlib figure of the probability zones around the search area."""
    import io as _io

    fig, ax = plt.subplots(figsize=(8.4, 4.6), dpi=110)
    cx, cy = mission.lkp_latitude, mission.lkp_longitude
    radius = mission.search_radius_nm or 5.0
    if mission.search_area and mission.search_area.polygon_geojson:
        poly = gis.parse_geojson(mission.search_area.polygon_geojson)
        ring = poly.get("coordinates", [[[]]])[0]
        ax.plot([p[1] for p in ring], [p[0] for p in ring], color=NAVY, lw=1.6, alpha=0.6)
    colors_map = {"high": "#ef4444", "medium": "#f97316", "low": "#eab308"}
    labels = {"high": "High probability", "medium": "Medium probability", "low": "Low probability"}
    for z in mission.zones or []:
        poly = gis.parse_geojson(z.polygon_geojson)
        ring = poly.get("coordinates", [[[]]])[0]
        xs = [p[1] for p in ring]
        ys = [p[0] for p in ring]
        ax.fill(xs, ys, color=colors_map.get(z.zone_level, "#888"), alpha=0.55, label=labels.get(z.zone_level))
    ax.scatter([cy], [cx], marker="^", s=90, color=NAVY, zorder=5, label="LKP")
    if mission.predicted_longitude is not None and mission.predicted_latitude is not None:
        ax.scatter([mission.predicted_longitude], [mission.predicted_latitude], marker="*", s=140, color="#dc2626", zorder=6, label="Predicted")
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    ax.set_title("Probability Distribution & Search Area", fontweight="bold", color=NAVY)
    ax.grid(True, ls="--", alpha=0.3)
    ax.legend(loc="upper right", fontsize=7, framealpha=0.9)
    ax.set_aspect("auto")
    fig.tight_layout()
    buf = _io.BytesIO()
    fig.savefig(buf, format="png")
    plt.close(fig)
    return buf.getvalue()


def _make_pattern_figure(mission: Mission) -> bytes:
    """Matplotlib figure of the recommended search pattern."""
    import io as _io

    fig, ax = plt.subplots(figsize=(8.4, 4.6), dpi=110)
    for pat in mission.patterns or []:
        wp = gis.parse_geojson(pat.waypoints_geojson)
        coords = wp.get("coordinates", [])
        xs = [c[0] for c in coords]
        ys = [c[1] for c in coords]
        style = dict(color="#1d4ed8", lw=2.0, marker="o", ms=3.0, alpha=0.9)
        if pat.recommended:
            style["color"] = "#dc2626"
        ax.plot(xs, ys, **style, label=pat.pattern_type.replace("_", " ").title() + ("*" if pat.recommended else ""))
    if mission.search_area and mission.search_area.polygon_geojson:
        poly = gis.parse_geojson(mission.search_area.polygon_geojson)
        ring = poly.get("coordinates", [[[]]])[0]
        ax.plot([p[1] for p in ring], [p[0] for p in ring], color=NAVY, lw=1.2, ls="--", alpha=0.5)
    ax.scatter([mission.lkp_longitude], [mission.lkp_latitude], marker="^", s=90, color=NAVY, zorder=5, label="LKP")
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    ax.set_title("Recommended Search Pattern", fontweight="bold", color=NAVY)
    ax.grid(True, ls="--", alpha=0.3)
    ax.legend(loc="upper right", fontsize=7, framealpha=0.9)
    fig.tight_layout()
    buf = _io.BytesIO()
    fig.savefig(buf, format="png")
    plt.close(fig)
    return buf.getvalue()


# ------------------------------------------------------------------- the pdf
def generate_mission_report(mission: Mission, officer_name: str) -> str:
    """Generate a full PDF report for a mission and return its file path."""
    filename = f"mission_{mission.id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.pdf"
    filepath = os.path.join(OUTPUT_DIR, filename)
    doc = SimpleDocTemplate(
        filepath,
        pagesize=A4,
        rightMargin=1.4 * cm,
        leftMargin=1.4 * cm,
        topMargin=1.4 * cm,
        bottomMargin=1.4 * cm,
    )
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="TitleBlue", parent=styles["Title"], textColor=NAVY, alignment=TA_CENTER, fontSize=17))
    styles.add(ParagraphStyle(name="Small", parent=styles["BodyText"], fontSize=9, leading=12))
    styles.add(ParagraphStyle(name="H2", parent=styles["Heading2"], textColor=NAVY, fontSize=12))

    story = []

    # Header
    story.append(Paragraph("Airports Authority of India", styles["TitleBlue"]))
    story.append(Paragraph("SEARCH AND RESCUE DECISION SUPPORT SYSTEM", styles["H2"]))
    story.append(Paragraph(f"Search Area Analysis Report &nbsp;|&nbsp; Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')} &nbsp;|&nbsp; Officer: {officer_name}", styles["Small"]))
    story.append(Spacer(1, 0.35 * cm))

    # Mission details
    story.append(Paragraph("Mission Details", styles["H2"]))
    mission_rows = [
        ["Mission Name", mission.mission_name, "Flight No.", mission.flight_number or "-"],
        ["Aircraft", mission.aircraft_name or "-", "Registration", mission.registration_number or "-"],
        ["Aircraft Type", mission.aircraft_type or "-", "Pilot", mission.pilot_name or "-"],
        ["Departure", mission.departure_airport or "-", "Destination", mission.destination_airport or "-"],
        ["Status", mission.status.upper(), "LKP Accuracy", mission.lkp_accuracy.upper()],
        ["Last Contact", mission.last_contact_time.strftime("%Y-%m-%d %H:%M UTC"), "Elapsed", f"{mission.elapsed_hours:.1f} h"],
        ["LKP Position", f"{mission.lkp_latitude:.5f}, {mission.lkp_longitude:.5f}", "Altitude", f"{mission.altitude_ft:,.0f} ft"],
    ]
    t = Table(mission_rows, colWidths=[3.2 * cm, 4.6 * cm, 3.2 * cm, 4.6 * cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), LIGHT),
        ("TEXTCOLOR", (0, 0), (0, -1), NAVY),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, LIGHT]),
    ]))
    story.append(t)
    story.append(Spacer(1, 0.3 * cm))

    # Search parameters
    story.append(Paragraph("Calculated Search Parameters", styles["H2"]))
    params = [
        ["Search Radius", f"{mission.search_radius_nm:.2f} nm", "Search Area", f"{mission.search_area_sqnm:,.2f} nm²"],
        ["Distance (Speed × Time)", f"{mission.distance_nm:.1f} nm", "Uncertainty", f"{mission.uncertainty_nm:.1f} nm"],
        ["Desired Coverage", f"{mission.desired_coverage_pct:.1f} %", "Weather Impact", f"{mission.weather_impact:.2f}"],
        ["Predicted Position", _fmt_pos(mission.predicted_latitude, mission.predicted_longitude), "Risk Score", f"{mission.risk_score:.1f} / 100"],
        ["Wind", f"{mission.wind_speed_kts:.0f} kt @ {mission.wind_direction_deg:.0f}°", "Visibility", f"{mission.visibility_nm:.1f} nm"],
        ["Weather", mission.weather_conditions or "-", "Fuel Remaining", f"{mission.fuel_remaining_hours:.1f} h"],
    ]
    t2 = Table(params, colWidths=[4.0 * cm, 4.2 * cm, 4.0 * cm, 4.2 * cm])
    t2.setStyle(TableStyle([
        ("TEXTCOLOR", (0, 0), (0, -1), NAVY),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, LIGHT]),
    ]))
    story.append(t2)
    story.append(Spacer(1, 0.3 * cm))

    # Recommended pattern text
    rec = next((p for p in mission.patterns or [] if p.recommended), None)
    if rec:
        story.append(Paragraph(f"Recommended Pattern: <b>{rec.pattern_type.replace('_', ' ').title()}</b>", styles["BodyText"]))
        story.append(Paragraph(f"<i>{rec.reason or ''}</i>", styles["Small"]))
        story.append(Spacer(1, 0.2 * cm))

    # Map image (fallback to probability figure)
    map_bytes = _fetch_static_map(mission.lkp_latitude, mission.lkp_longitude, mission.search_radius_nm or 5.0)
    try:
        if map_bytes:
            img = Image(io.BytesIO(map_bytes), width=16.8 * cm, height=9.2 * cm)
        else:
            img = Image(io.BytesIO(_make_probability_figure(mission)), width=16.8 * cm, height=9.2 * cm)
        story.append(img)
    except Exception:
        pass
    story.append(Spacer(1, 0.3 * cm))

    # Probability figure
    try:
        img2 = Image(io.BytesIO(_make_probability_figure(mission)), width=16.8 * cm, height=9.2 * cm)
        story.append(img2)
    except Exception:
        pass
    story.append(Spacer(1, 0.3 * cm))

    # Pattern figure
    try:
        img3 = Image(io.BytesIO(_make_pattern_figure(mission)), width=16.8 * cm, height=9.2 * cm)
        story.append(img3)
    except Exception:
        pass

    # Sectors
    if mission.sectors:
        story.append(Spacer(1, 0.3 * cm))
        story.append(Paragraph("Sector Allocation", styles["H2"]))
        sector_rows = [["Sector", "Angle", "Area (nm²)", "Assigned Aircraft"]]
        for s in mission.sectors:
            sector_rows.append([
                s.name,
                f"{s.start_angle_deg:.0f}° - {s.end_angle_deg:.0f}°",
                f"{s.area_sqnm:.1f}",
                s.assigned_aircraft or "Unassigned",
            ])
        ts = Table(sector_rows, colWidths=[3.5 * cm, 4.5 * cm, 4.0 * cm, 4.6 * cm])
        ts.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), NAVY),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
        ]))
        story.append(ts)

    # Remarks
    if mission.remarks:
        story.append(Spacer(1, 0.3 * cm))
        story.append(Paragraph("Remarks", styles["H2"]))
        story.append(Paragraph(mission.remarks.replace("\n", "<br/>"), styles["Small"]))

    story.append(Spacer(1, 0.6 * cm))
    story.append(Paragraph("Generated by SAR-DSS (Airports Authority of India) - For official use only.", styles["Small"]))

    doc.build(story)
    return filepath


def _fmt_pos(lat: float | None, lon: float | None) -> str:
    if lat is None or lon is None:
        return "-"
    return f"{lat:.5f}, {lon:.5f}"
