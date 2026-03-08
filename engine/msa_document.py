"""Generate a pre-filled Medical Service Agreement (DOCX) from the NOH Cash template."""

import hashlib
import math
from datetime import date, datetime, timedelta
from io import BytesIO
from pathlib import Path

from docx import Document

TEMPLATE_PATH = Path(__file__).resolve().parent.parent / "data" / "msa_template.docx"


def _generate_reference(patient_name: str, id_number: str) -> str:
    """Short deterministic reference from patient details + date."""
    raw = f"{patient_name}|{id_number}|{datetime.utcnow().date()}"
    return "NOH-MSA-" + hashlib.sha256(raw.encode()).hexdigest()[:8].upper()


def _estimate_edd(gestational_age_weeks: float) -> date:
    """Estimate EDD from current GA (40 weeks total)."""
    remaining_weeks = 40.0 - gestational_age_weeks
    return date.today() + timedelta(weeks=remaining_weeks)


def generate_msa_docx(
    *,
    patient_name: str,
    id_number: str,
    gestational_age_weeks: float,
    global_fee: float,
    months_to_34_weeks: int,
    monthly_payment: float,
) -> BytesIO:
    """
    Fill in the MSA template and return an in-memory DOCX buffer.

    Parameters
    ----------
    patient_name : str
        Full name with title, e.g. "Mrs J Doe".
    id_number : str
        ID or passport number (and surname if different).
    gestational_age_weeks : float
        Current gestational age at booking.
    global_fee : float
        Total global maternity fee (from pricing engine).
    months_to_34_weeks : int
        Number of monthly instalments.
    monthly_payment : float
        Amount per month.

    Returns
    -------
    BytesIO
        In-memory DOCX ready for download.
    """
    doc = Document(str(TEMPLATE_PATH))

    # Table 0 is the letterhead — skip
    # Table 1 is Client Details
    details_table = doc.tables[1]

    field_map = {
        0: _generate_reference(patient_name, id_number),          # Reference Number
        1: patient_name,                                           # Title and Name
        2: id_number,                                              # ID/Passport Number and Surname
        3: date.today().strftime("%d %B %Y"),                      # Date of Agreement
        4: _estimate_edd(gestational_age_weeks).strftime("%d %B %Y"),  # EDD
        5: f"{gestational_age_weeks:.1f}",                         # Current Gestation
        6: f"R {global_fee:,.2f}",                                 # Global Maternity Fee
        7: str(months_to_34_weeks),                                # Settlement Time
        8: f"R {monthly_payment:,.2f}",                            # Monthly Installment
    }

    for row_idx, value in field_map.items():
        cell = details_table.rows[row_idx].cells[1]
        cell.text = value
        # Preserve the existing font by copying style from the label cell
        for paragraph in cell.paragraphs:
            for run in paragraph.runs:
                run.font.size = details_table.rows[row_idx].cells[0].paragraphs[0].runs[0].font.size if details_table.rows[row_idx].cells[0].paragraphs[0].runs else None

    # Table 3 — Practice signature block: pre-fill name
    practice_table = doc.tables[3]
    practice_table.rows[0].cells[1].text = "Dr H P Manyonga"

    # Write to in-memory buffer
    buf = BytesIO()
    doc.save(buf)
    buf.seek(0)
    return buf
