from datetime import datetime
from app.db import query_one, get_conn

REQUIRED_STATIONS = ("progtest", "assembly", "lasermarking1")

def lookup_unit(serial_num: str):
    """Check b2btag_main for the serial and its station statuses."""
    return query_one(
        """
        SELECT serial_num, po_num, progtest, assembly, lasermarking1, vi
        FROM energous.esense_main_copy
        WHERE serial_num = %s
        LIMIT 1
        """,
        (serial_num,)
    )

def lookup_prog_id(prog_id: str):
    """Check that the prog_id exists at all in the progtest table."""
    return query_one(
        """
        SELECT prog_id, serial_num
        FROM energous.esense_progtest
        WHERE prog_id = %s
        LIMIT 1
        """,
        (prog_id,)
    )

def verify_prog_matches_serial(prog_id: str, serial_num: str) -> bool:
    """Confirm this specific prog_id is actually tied to this serial_num."""
    row = query_one(
        """
        SELECT prog_id
        FROM energous.esense_progtest
        WHERE prog_id = %s AND serial_num = %s
        LIMIT 1
        """,
        (prog_id, serial_num)
    )
    return row is not None

def already_packed(serial_num: str) -> bool:
    row = query_one(
        "SELECT serial_num FROM energous.esense_vi_copy WHERE serial_num = %s LIMIT 1",
        (serial_num,)
    )
    return row is not None

def stations_passed(row: dict) -> bool:
    """Return True if all required stations are recorded as 1."""
    return all(row.get(s) == 1 for s in REQUIRED_STATIONS)

def record_packing(serial_num: str, po_num: str, operator_en: str, shift: str, remarks: str = ""):
    """
    Atomically:
      1. Set vi=1 in esense_main_copy
      2. Insert a row into esense_vi_copy (status=1, test_rep=1)
    """
    conn = get_conn()
    try:
        cur = conn.cursor()

        cur.execute(
            """
            UPDATE energous.esense_main_copy
            SET vi = 1
            WHERE serial_num = %s
            """,
            (serial_num,)
        )

        cur.execute(
            """
            INSERT INTO energous.esense_vi_copy
                (serial_num, po_num, operator_en, shift, date_time, test_rep, remarks, status)
            VALUES (%s, %s, %s, %s, %s, 1, %s, 1)
            """,
            (serial_num, po_num, operator_en, shift, datetime.now(), remarks)
        )

        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def process_prog_check(prog_id: str):
    """
    Step 1: just validate the prog_id exists in progtest.
    Returns a result dict:
      status  : "ok" | "not_found"
      message : human-readable string
    """
    prog_id = prog_id.strip()
    prog_row = lookup_prog_id(prog_id)
    if not prog_row:
        return {"status": "not_found", "message": f"Prog ID '{prog_id}' not found in progtest.", "ok": False}

    return {"status": "ok", "message": f"Prog ID '{prog_id}' verified. Now scan the serial number.", "ok": True}


def process_scan(prog_id: str, serial_num: str, operator_en: str, shift: str, remarks: str = ""):
    """
    Full scan pipeline. Requires a prog_id that was already validated in step 1.
    Returns a result dict:
      status  : "ok" | "already_packed" | "fail" | "not_found" | "mismatch"
      message : human-readable string
      unit    : the esense_main_copy row (or None)
    """
    serial_num = serial_num.strip()
    prog_id = prog_id.strip()

    if not prog_id:
        return {"status": "fail", "message": "No prog_id was scanned/verified first.", "unit": None}

    unit = lookup_unit(serial_num)
    if not unit:
        return {"status": "not_found", "message": f"Serial '{serial_num}' not found in database.", "unit": None}

    if already_packed(serial_num):
        return {"status": "already_packed", "message": f"Serial '{serial_num}' was already packed.", "unit": unit}

    if not stations_passed(unit):
        failed = [s for s in REQUIRED_STATIONS if unit.get(s) != 1]
        return {
            "status": "fail",
            "message": f"Serial '{serial_num}' has not passed: {', '.join(failed).upper()}.",
            "unit": unit,
        }

    if not verify_prog_matches_serial(prog_id, serial_num):
        return {
            "status": "mismatch",
            "message": f"Prog ID '{prog_id}' does not match serial '{serial_num}'.",
            "unit": unit,
        }

    record_packing(serial_num, unit["po_num"], operator_en, shift, remarks)
    return {
        "status": "ok",
        "message": f"Serial '{serial_num}' packed successfully.",
        "unit": unit,
    }