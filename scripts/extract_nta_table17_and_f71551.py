#!/usr/bin/env python3
"""Rebuild historical pseudo-filer external sensitivity inputs from official XLSX.

Outputs
-------
data/derived/nta_salary_class_social_deduction_schedule_2024.csv
data/derived/nta_salary_class_family_deduction_validation_2024.csv
data/derived/income_tax_age_income_source_shares_2024.csv

The NTA schedules are external wage-earner sensitivity mappings. They do not
identify a mapping from F71561 household deciles to NTA salary-survey workers.

The F71551 age-pension quantity is explicitly a proxy. Age-recap household
counts can overlap and the table is aggregate/equivalized; therefore the
computed 65+ share is not a filer-level or person-level identified share.
"""
from pathlib import Path
from zipfile import ZipFile
import argparse
import csv
import hashlib
import io
import re
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
NTA = ROOT / "data/raw/nta/nta_minkan2024_table17.xlsx"
F71551 = ROOT / "data/raw/estat/000040490418.xlsx"

OUT_SOCIAL = ROOT / "data/derived/nta_salary_class_social_deduction_schedule_2024.csv"
OUT_FAMILY = ROOT / "data/derived/nta_salary_class_family_deduction_validation_2024.csv"
OUT_AGE = ROOT / "data/derived/income_tax_age_income_source_shares_2024.csv"
STATUTORY = ROOT / "data/derived/income_tax_2026_statutory_parameters.csv"

M = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
REL = "{http://schemas.openxmlformats.org/package/2006/relationships}"
RID = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
CELL_RE = re.compile(r"^([A-Z]+)([0-9]+)$")
DECILE_RE = re.compile(r"^R(0[1-9]|10)_十分位([1-9]|10)$")

SALARY_UPPER_YEN = [
    1_000_000, 2_000_000, 3_000_000, 4_000_000,
    5_000_000, 6_000_000, 7_000_000, 8_000_000,
    9_000_000, 10_000_000, 15_000_000, 20_000_000,
]


def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def render(fields, rows):
    b = io.StringIO()
    w = csv.DictWriter(b, fieldnames=fields, lineterminator="\n")
    w.writeheader(); w.writerows(rows)
    return b.getvalue()


class Xlsx:
    def __init__(self, path):
        self.path = path
        self.z = ZipFile(path)
        if "xl/sharedStrings.xml" in self.z.namelist():
            root = ET.fromstring(self.z.read("xl/sharedStrings.xml"))
            self.shared = [
                "".join(t.text or "" for t in si.iter(M + "t"))
                for si in root.findall(M + "si")
            ]
        else:
            self.shared = []
        self.sheet_targets = self._sheet_targets()

    def _sheet_targets(self):
        wb = ET.fromstring(self.z.read("xl/workbook.xml"))
        rels = ET.fromstring(self.z.read("xl/_rels/workbook.xml.rels"))
        target_by_rid = {
            r.attrib["Id"]: r.attrib["Target"]
            for r in rels.findall(REL + "Relationship")
        }
        out = {}
        sheets = wb.find(M + "sheets")
        for s in sheets:
            target = target_by_rid[s.attrib[RID]]
            if not target.startswith("/"):
                target = "xl/" + target
            else:
                target = target.lstrip("/")
            out[s.attrib["name"]] = target
        return out

    def cell(self, c):
        typ = c.attrib.get("t")
        if typ == "inlineStr":
            return "".join(t.text or "" for t in c.iter(M + "t"))
        v = c.find(M + "v")
        if v is None:
            return ""
        raw = v.text or ""
        if typ == "s":
            return self.shared[int(raw)]
        return raw

    def row_map(self, sheet_name):
        target = self.sheet_targets[sheet_name]
        result = {}
        root = ET.fromstring(self.z.read(target))
        for row in root.iter(M + "row"):
            rn = int(row.attrib["r"])
            vals = {}
            for c in row.findall(M + "c"):
                ref = c.attrib["r"]
                col = CELL_RE.match(ref).group(1)
                vals[col] = self.cell(c)
            result[rn] = vals
        return result

    def iter_rows(self, sheet_name):
        target = self.sheet_targets[sheet_name]
        with self.z.open(target) as f:
            for _, row in ET.iterparse(f, events=("end",)):
                if row.tag != M + "row":
                    continue
                rn = int(row.attrib["r"])
                vals = {}
                for c in row.findall(M + "c"):
                    ref = c.attrib["r"]
                    col = CELL_RE.match(ref).group(1)
                    vals[col] = self.cell(c)
                yield rn, vals
                row.clear()

    def close(self):
        self.z.close()


def fnum(x):
    if x in ("", "-", None):
        return 0.0
    return float(x)


def dependent_amounts():
    with STATUTORY.open(encoding="utf-8", newline="") as f:
        rows = [
            r for r in csv.DictReader(f)
            if r["parameter_group"] == "dependent_deduction"
        ]
    by = {r["rule_id"]: r for r in rows}
    required = {
        "D_GENERAL", "D_SPECIFIED",
        "D_ELDERLY_CORESIDENT", "D_ELDERLY_OTHER",
    }
    if set(by) != required:
        raise RuntimeError(f"dependent statutory rules mismatch: {sorted(by)}")
    amounts = {
        "general": int(float(by["D_GENERAL"]["constant_yen"])),
        "specified": int(float(by["D_SPECIFIED"]["constant_yen"])),
        "elderly_co_resident": int(float(by["D_ELDERLY_CORESIDENT"]["constant_yen"])),
        "elderly_other": int(float(by["D_ELDERLY_OTHER"]["constant_yen"])),
    }
    shas = {r["source_sha256"] for r in rows}
    if len(shas) != 1:
        raise RuntimeError("dependent-deduction rules do not share one source SHA")
    return amounts, next(iter(shas))


def nta_table17_outputs():
    x = Xlsx(NTA)
    try:
        summary = x.row_map("その１の１(合計)")
        deps = x.row_map("その１の２(合計)")
        social = x.row_map("その２の１(合計)")
    finally:
        x.close()

    raw_sha = sha256(NTA)
    dependent_amounts_2026, dependent_source_sha = dependent_amounts()
    social_rows = []
    family_rows = []

    # Salary-class rows are 36:47 in total summary/dependents, 7:18 and 21:32
    # in the social-insurance sheet.
    for i, upper in enumerate(SALARY_UPPER_YEN):
        sr = 36 + i
        dr = 36 + i
        people_r = 7 + i
        amount_r = 21 + i

        employee_count = fnum(summary[sr].get("D"))
        social_recipient_count = fnum(social[people_r].get("N"))
        social_amount_million = fnum(social[amount_r].get("N"))
        social_total_yen = social_amount_million * 1_000_000.0
        avg_per_employee = (
            social_total_yen / employee_count if employee_count else 0.0
        )
        avg_per_recipient = (
            social_total_yen / social_recipient_count
            if social_recipient_count else 0.0
        )

        label = summary[sr].get("C", social[people_r].get("D", ""))
        social_rows.append({
            "salary_class_label": label,
            "upper_salary_yen_inclusive": upper,
            "full_year_employee_count": f"{employee_count:.12g}",
            "full_year_employee_count_source_cell": f"D{sr}",
            "social_insurance_deduction_recipient_count":
                f"{social_recipient_count:.12g}",
            "social_insurance_deduction_recipient_count_source_cell":
                f"N{people_r}",
            "social_insurance_deduction_amount_million_yen":
                f"{social_amount_million:.12g}",
            "social_insurance_deduction_amount_source_cell": f"N{amount_r}",
            "average_social_insurance_deduction_per_employee_yen":
                f"{avg_per_employee:.12g}",
            "average_social_insurance_deduction_per_recipient_yen":
                f"{avg_per_recipient:.12g}",
            "preferred_mapping_value":
                "average_social_insurance_deduction_per_employee_yen",
            "population_scope":
                "NTA Table17 year-end-adjusted full-year salary earners; external sensitivity only",
            "source_id": "NTA-MINKAN-2024-T17",
            "source_file": "data/raw/nta/nta_minkan2024_table17.xlsx",
            "source_sha256": raw_sha,
            "model_status": "EXTERNAL_SENSITIVITY_ONLY",
        })

        general = fnum(deps[dr].get("E"))
        specified = fnum(deps[dr].get("F"))
        elderly_co = fnum(deps[dr].get("G"))
        elderly_other = fnum(deps[dr].get("H"))
        observed_total = fnum(deps[dr].get("D"))
        component_total = general + specified + elderly_co + elderly_other
        total_deduction = (
            general * dependent_amounts_2026["general"]
            + specified * dependent_amounts_2026["specified"]
            + elderly_co * dependent_amounts_2026["elderly_co_resident"]
            + elderly_other * dependent_amounts_2026["elderly_other"]
        )
        per_employee = total_deduction / employee_count if employee_count else 0.0
        family_rows.append({
            "salary_class_label": label,
            "upper_salary_yen_inclusive": upper,
            "full_year_employee_count": f"{employee_count:.12g}",
            "full_year_employee_count_source_cell": f"D{sr}",
            "observed_dependent_count_total": f"{observed_total:.12g}",
            "observed_dependent_count_total_source_cell": f"D{dr}",
            "general_dependent_count": f"{general:.12g}",
            "general_dependent_count_source_cell": f"E{dr}",
            "specified_dependent_count": f"{specified:.12g}",
            "specified_dependent_count_source_cell": f"F{dr}",
            "elderly_co_resident_dependent_count": f"{elderly_co:.12g}",
            "elderly_co_resident_dependent_count_source_cell": f"G{dr}",
            "elderly_other_dependent_count": f"{elderly_other:.12g}",
            "elderly_other_dependent_count_source_cell": f"H{dr}",
            "component_count_sum": f"{component_total:.12g}",
            "component_count_minus_reported_total":
                f"{component_total-observed_total:.12g}",
            "general_deduction_2026_yen": dependent_amounts_2026["general"],
            "specified_deduction_2026_yen": dependent_amounts_2026["specified"],
            "elderly_co_resident_deduction_2026_yen":
                dependent_amounts_2026["elderly_co_resident"],
            "elderly_other_deduction_2026_yen":
                dependent_amounts_2026["elderly_other"],
            "dependent_deduction_2026_amounts_on_2024_composition_total_yen":
                f"{total_deduction:.12g}",
            "dependent_deduction_2026_amounts_on_2024_composition_per_employee_yen":
                f"{per_employee:.12g}",
            "composition_year": 2024,
            "statutory_amount_year": 2026,
            "eligibility_warning":
                "does not forecast persons newly eligible under 2026 income thresholds",
            "source_id_composition": "NTA-MINKAN-2024-T17",
            "source_id_statutory_amounts": "NTA-2026-DEPENDENT-DEDUCTION",
            "source_sha256_statutory_amounts": dependent_source_sha,
            "source_file_composition":
                "data/raw/nta/nta_minkan2024_table17.xlsx",
            "source_sha256_composition": raw_sha,
            "model_status": "EXTERNAL_SENSITIVITY_ONLY",
        })

    return social_rows, family_rows


def f71551_output():
    x = Xlsx(F71551)
    try:
        picked = {d: {} for d in range(1, 11)}
        for rn, vals in x.iter_rows("F71551"):
            if rn < 8:
                continue
            if vals.get("D") != "0_平均":
                continue
            m = DECILE_RE.match(vals.get("F", ""))
            if not m or vals.get("H") != "00_平均":
                continue
            d = int(m.group(2))
            if vals.get("I") == "集計世帯数（概数）" and vals.get("K") == "0_総数":
                picked[d]["count"] = (rn, vals)
            if (
                vals.get("I") == "等価年間収入額"
                and vals.get("K", "").startswith("214_")
            ):
                picked[d]["pension"] = (rn, vals)
    finally:
        x.close()

    raw_sha = sha256(F71551)
    rows = []
    for d in range(1, 11):
        if set(picked[d]) != {"count", "pension"}:
            raise RuntimeError(f"missing F71551 rows for decile {d}")
        cr, c = picked[d]["count"]
        pr, p = picked[d]["pension"]

        # AC = R11 18-64 recap; AD = R12 65+ recap.
        n_u65 = fnum(c.get("AC"))
        n_65p = fnum(c.get("AD"))
        pension_u65_kY = fnum(p.get("AC"))
        pension_65p_kY = fnum(p.get("AD"))
        proxy_u65 = n_u65 * pension_u65_kY
        proxy_65p = n_65p * pension_65p_kY
        denom = proxy_u65 + proxy_65p
        share = proxy_65p / denom if denom else 0.0

        rows.append({
            "decile": d,
            "decile_label": p.get("F", ""),
            "all_age_household_count_approx": c.get("M", ""),
            "all_age_household_count_source_cell": f"M{cr}",
            "age18_64_recap_household_count_approx": f"{n_u65:.12g}",
            "age18_64_recap_household_count_source_cell": f"AC{cr}",
            "age65p_recap_household_count_approx": f"{n_65p:.12g}",
            "age65p_recap_household_count_source_cell": f"AD{cr}",
            "recap_count_overlap_ratio_to_all_age":
                f"{((n_u65+n_65p)/fnum(c.get('M')) if fnum(c.get('M')) else 0):.12g}",
            "all_age_public_pension_kY": p.get("M", ""),
            "all_age_public_pension_source_cell": f"M{pr}",
            "age18_64_public_pension_kY": f"{pension_u65_kY:.12g}",
            "age18_64_public_pension_source_cell": f"AC{pr}",
            "age65p_public_pension_kY": f"{pension_65p_kY:.12g}",
            "age65p_public_pension_source_cell": f"AD{pr}",
            "age18_64_public_pension_amount_proxy_kY_households":
                f"{proxy_u65:.12g}",
            "age65p_public_pension_amount_proxy_kY_households":
                f"{proxy_65p:.12g}",
            "age65p_share_of_public_pension_amount_proxy": f"{share:.12g}",
            "proxy_definition":
                "(R12 age65+ recap approximate households * R12 public-pension mean) / same plus R11 age18-64 term",
            "identification_warning":
                "age recap household counts can overlap; aggregate equivalized cells do not identify filer/person pension-age allocation",
            "source_id": "ESTAT-7155-1-2024",
            "source_file": "data/raw/estat/000040490418.xlsx",
            "source_sha256": raw_sha,
            "model_status": "SENSITIVITY_PROXY_NOT_IDENTIFIED",
        })
    return rows


def specs():
    social, family = nta_table17_outputs()
    age = f71551_output()
    return [
        (OUT_SOCIAL, list(social[0]), social),
        (OUT_FAMILY, list(family[0]), family),
        (OUT_AGE, list(age[0]), age),
    ]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    out = specs()
    if args.check:
        stale = []
        for path, fields, rows in out:
            expected = render(fields, rows)
            actual = path.read_text(encoding="utf-8") if path.exists() else ""
            if expected != actual:
                stale.append(str(path.relative_to(ROOT)))
        if stale:
            print("ERROR: stale NTA/F71551 sensitivity files: " + ", ".join(stale))
            sys.exit(1)
        print("NTA Table17 / F71551 sensitivity extracts: current (34 rows)")
        return
    for path, fields, rows in out:
        path.write_text(render(fields, rows), encoding="utf-8")
        print(f"wrote {path.relative_to(ROOT)}: {len(rows)} rows")


if __name__ == "__main__":
    main()
