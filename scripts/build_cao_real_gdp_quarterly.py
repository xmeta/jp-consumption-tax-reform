"""Build normalized quarterly real GDP growth data from Cabinet Office CSV."""

import csv
from pathlib import Path


def parse_quarter(value):
    year, month = value.strip('.').split('/')
    year = int(year)
    month = month.strip()
    quarter = {'1- 3':1, '4- 6':2, '7- 9':3, '10-12':4}[month]
    return f"{year}-Q{quarter}"


src = Path('data/macro/raw/cao_real_gdp_qoq_2026_q2.csv')
out = Path('data/macro/real_gdp_quarterly.csv')

rows = []
current_year = None
with src.open(encoding='cp932', newline='') as f:
    for row in csv.reader(f):
        if not row or not row[0].strip():
            continue
        if '/' in row[0]:
            current_year = int(row[0].split('/')[0])
            label = row[0]
        else:
            label = f"{current_year}/{row[0]}"
        if not row[1].strip() or row[1].strip() == '***':
            continue
        qoq = float(row[1].strip()) / 100
        rows.append({
            'quarter': parse_quarter(label),
            'real_gdp_growth_qoq': qoq,
            'annualized_growth': (1 + qoq) ** 4 - 1,
            'status': 'observed',
            'source_id': 'CAO_QE_2026_Q2_REAL_GDP_QOQ',
            'revision_date': '2026-08-17',
        })

with out.open('w', newline='', encoding='utf-8') as f:
    writer = csv.DictWriter(f, fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows(rows)

print(f'wrote {len(rows)} rows')
