"""
Parser for ICEGATE Item Wise Ledger HTML (.htm/.html) files.
Produces the same dict_list output format as parse_ledger.py so it can be
fed directly into create_object() without any changes to the upload pipeline.

Ported EXACTLY from legacy/backend/scripts/parse_ledger_htm.py.
No import changes needed — this module has no Django imports.
"""
import datetime
import re
from html.parser import HTMLParser


def _strip_value(text):
    """Remove the leading ': ' / ':\xa0' prefix that ICEGATE puts in value cells."""
    text = text.strip('\xa0 \t\r\n')
    text = re.sub(r'^:[\xa0\s]*', '', text)
    return text.strip('\xa0 \t\r\n')


class _HtmExtractor(HTMLParser):
    """
    SAX-style parser that walks the HTML once and collects:
      - tables: list of tables, each a list of rows, each a list of cell texts
      - body_text: all text nodes outside of tables (for footer date extraction)
    """

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tables = []
        self._cur_table = None
        self._cur_row = None
        self._in_cell = False
        self._cell_buf = []
        self.body_text = []

    def handle_starttag(self, tag, attrs):
        if tag == 'table':
            self._cur_table = []
        elif tag == 'tr' and self._cur_table is not None:
            self._cur_row = []
        elif tag in ('td', 'th') and self._cur_row is not None:
            self._in_cell = True
            self._cell_buf = []

    def handle_endtag(self, tag):
        if tag == 'table' and self._cur_table is not None:
            self.tables.append(self._cur_table)
            self._cur_table = None
            self._cur_row = None
        elif tag == 'tr' and self._cur_row is not None and self._cur_table is not None:
            self._cur_table.append(self._cur_row)
            self._cur_row = None
        elif tag in ('td', 'th') and self._in_cell:
            cell = ''.join(self._cell_buf).strip('\xa0 \t\r\n')
            if self._cur_row is not None:
                self._cur_row.append(cell)
            self._in_cell = False
            self._cell_buf = []

    def handle_data(self, data):
        if self._in_cell:
            self._cell_buf.append(data)
        elif self._cur_table is None:
            # Collect non-table text for footer date extraction
            self.body_text.append(data)


def _parse_date(date_str):
    """Return a datetime.datetime for a DD/MM/YYYY or DD/MM/YY string, or None."""
    if not date_str:
        return None
    for fmt in ('%d/%m/%Y', '%d/%m/%y'):
        try:
            return datetime.datetime.strptime(date_str.strip(), fmt)
        except ValueError:
            continue
    return None


def parse_license_data_htm(content: bytes) -> list:
    """
    Parse an ICEGATE Item Wise Ledger HTML file (one or multiple pages) and
    return a list with a single dict in the same format as parse_ledger.parse_license_data().

    The returned dict has these keys (identical to the CSV parser output):
        ledger_date, registration_no, registration_date, lic_no, lic_date,
        port, iec, scheme_code, notification, foregin_currency,
        cif_inr, cif_fc, total_quantity, row
    """
    # Decode — ICEGATE files are often windows-1252
    for enc in ('windows-1252', 'utf-8-sig', 'utf-8', 'latin-1'):
        try:
            text = content.decode(enc)
            break
        except (UnicodeDecodeError, LookupError):
            continue
    else:
        text = content.decode('latin-1', errors='replace')

    extractor = _HtmExtractor()
    extractor.feed(text)

    if not extractor.tables:
        return []

    # ── Header table (always the first table) ──────────────────────────────
    header_table = extractor.tables[0]
    # Keep only rows that look like 8-cell info rows
    header_rows = [r for r in header_table if len(r) >= 8]

    if not header_rows:
        return []

    # Row 0: Regn.No. | Regn.Date | Lic.No. | Lic.Date
    regn_no   = _strip_value(header_rows[0][1])
    regn_date = _strip_value(header_rows[0][3])
    lic_no    = _strip_value(header_rows[0][5])
    lic_date  = _strip_value(header_rows[0][7])

    # Row 1: RA No. | RA Date | Iss.CH. (port) | Recv.CH
    port = _strip_value(header_rows[1][5])   # Iss.CH. value

    # Row 2: IEC | Schm.Cd. | Notifcn. | Frgn.Curr
    iec              = _strip_value(header_rows[2][1])
    scheme_code      = _strip_value(header_rows[2][3])
    notification     = _strip_value(header_rows[2][5])
    foregin_currency = _strip_value(header_rows[2][7])

    # Row 3: Tot.Duty | CIF-INR. | Tot.Qty. | CIF-FC
    def _flt(s):
        try:
            return float(s) if s else 0.0
        except ValueError:
            return 0.0

    cif_inr        = _flt(_strip_value(header_rows[3][3]))
    total_quantity = _flt(_strip_value(header_rows[3][5]))
    cif_fc         = _flt(_strip_value(header_rows[3][7]))

    # Pad IEC and lic_no to 10 digits if they came in as 9
    if len(iec) == 9:
        iec = '0' + iec
    if len(lic_no) == 9:
        lic_no = '0' + lic_no

    # ── Ledger date — extracted from the "Dated: DD/MM/YYYY" footer ───────
    full_text = ''.join(extractor.body_text)
    ledger_date = datetime.date.today()
    m = re.search(r'Dated[:\s]+(\d{1,2}/\d{2}/\d{4})', full_text)
    if m:
        try:
            ledger_date = datetime.datetime.strptime(m.group(1).strip(), '%d/%m/%Y').date()
        except ValueError:
            pass

    # ── Transaction rows — from ALL tables after the first ─────────────────
    rows = []
    for table in extractor.tables[1:]:
        for row in table:
            if not row:
                continue
            first = row[0].strip()
            if first.lower() not in ('credit-', 'debit-'):
                continue
            if len(row) < 6:
                continue

            is_credit = first.lower() == 'credit-'

            try:
                sr_no = int(row[1].strip())
            except (ValueError, IndexError):
                continue

            cif_inr_row = _flt(row[3].strip() if len(row) > 3 else '')
            cif_fc_row  = _flt(row[4].strip() if len(row) > 4 else '')
            qty_row     = _flt(row[5].strip() if len(row) > 5 else '')

            be_number  = row[7].strip() if len(row) > 7 and row[7].strip() else None
            be_date_str = row[8].strip() if len(row) > 8 and row[8].strip() else None
            be_port    = row[9].strip() if len(row) > 9 and row[9].strip() else None

            be_date = None if is_credit else _parse_date(be_date_str)

            rows.append({
                'type':      'C' if is_credit else 'D',
                'sr_no':     sr_no,
                'cif_inr':   cif_inr_row,
                'cif_fc':    cif_fc_row,
                'qty':       qty_row,
                'be_number': be_number,
                'be_date':   be_date,
                'port':      be_port,
            })

    return [{
        'ledger_date':       ledger_date,
        'registration_no':   regn_no,
        'registration_date': regn_date,
        'lic_no':            lic_no,
        'lic_date':          lic_date,
        'port':              port,
        'iec':               iec,
        'scheme_code':       scheme_code,
        'notification':      notification,
        'foregin_currency':  foregin_currency,
        'cif_inr':           cif_inr,
        'cif_fc':            cif_fc,
        'total_quantity':    total_quantity,
        'row':               rows,
    }]
