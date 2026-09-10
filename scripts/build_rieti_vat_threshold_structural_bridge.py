#!/usr/bin/env python3
"""Extract RIETI 21-E-090 local VAT-threshold bunching and structural estimates.

The outputs preserve the study's local/historical/model-contingent scope.  They are
not a calibration of national real-resource cost c_VAT or macro allocative dividend.
"""
from pathlib import Path
import argparse, csv, io, re
from decimal import Decimal, getcontext
from pypdf import PdfReader

getcontext().prec = 40
ROOT = Path(__file__).resolve().parents[1]
CAT = ROOT / 'data/source_catalog.csv'
OUT_BUNCH = ROOT / 'data/derived/rieti_vat_threshold_bunching_response.csv'
OUT_STRUCT = ROOT / 'data/derived/rieti_vat_threshold_structural_estimates.csv'
SOURCE_ID = 'RIETI-2021-SME-VAT-COMPLIANCE'
EXPECTED_SHA = '397ef1b7202d6aec440e422587aa3ab09a1144ce0108db79fbc61166e64fe49b'


def read_csv(path):
    with path.open(encoding='utf-8', newline='') as f:
        return list(csv.DictReader(f))


def render(rows):
    b = io.StringIO()
    w = csv.DictWriter(b, fieldnames=list(rows[0]), lineterminator='\n')
    w.writeheader(); w.writerows(rows)
    return b.getvalue()


def norm(s):
    return re.sub(r'\s+', '', s or '').replace('−', '-').replace('–', '-')


def require(text, tokens, label):
    n = norm(text)
    for tok in tokens:
        if norm(tok) not in n:
            raise RuntimeError(f'{label}: missing token {tok!r}')


def fmt(x):
    s = f'{x:.15f}'.rstrip('0').rstrip('.')
    return s or '0'


def build():
    cat = {r['source_id']: r for r in read_csv(CAT)}
    if SOURCE_ID not in cat:
        raise RuntimeError(f'missing source {SOURCE_ID}')
    src = cat[SOURCE_ID]
    if src['sha256'] != EXPECTED_SHA:
        raise RuntimeError(f'{SOURCE_ID}: unexpected sha256 {src["sha256"]}')
    p = ROOT / src['raw_file']
    r = PdfReader(p)
    if len(r.pages) != 32:
        raise RuntimeError(f'{SOURCE_ID}: unexpected page count {len(r.pages)}')

    # Model scope and definition: physical PDF pp.12-14.
    p12 = r.pages[11].extract_text() or ''
    p13 = r.pages[12].extract_text() or ''
    p14 = r.pages[13].extract_text() or ''
    require(p12, [
        '4 or more employees',
        'cannot pass on any tax at all to their selling price',
        'simplified tax system',
    ], 'RIETI 21-E-090 p12')
    require(p13, [
        'value added can be described as v = (1 − α)y',
        'Θ(y; α) = θ(1 − α)y',
        'θ ∈ [0, 1]',
    ], 'RIETI 21-E-090 p13')
    require(p14, ['1 − tB − θ', 'marginal bunchers'], 'RIETI 21-E-090 p14')

    # Bunching table and numerical-estimation inputs: physical PDF pp.21-22.
    p21 = r.pages[20].extract_text() or ''
    p22 = r.pages[21].extract_text() or ''
    require(p21, [
        'Table 3. Size of Excess Bunching',
        '1989-1991 1.397 0.227 27.5 16.498 3.793',
        '1992-1994 1.243 0.237 27.5 16.277 4.594',
        '1997-1999 1.212 0.208 27.5 16.261 4.211',
    ], 'RIETI 21-E-090 Table 3')
    require(p22, [
        '∆y∗/y∗ = 55 .0%',
        '∆y∗ 1992/y∗ = 54 .3%',
        '∆y∗ 1997/y∗ = 54 .2%',
    ], 'RIETI 21-E-090 p22 numerical inputs')

    # Structural estimates and paper's own 30m example: physical PDF pp.23-24.
    p23 = r.pages[22].extract_text() or ''
    p24 = r.pages[23].extract_text() or ''
    require(p23, [
        'e and θ fall around 0.03 and 0.13',
        '30 × (1 − 0.65) × 0.13 = 1 .365 million JPY',
        'relatively excessive',
    ], 'RIETI 21-E-090 p23')
    require(p24, [
        'Table 5. Tax Elasticity and Compliance Costs',
        '0.028 0.130 0.073 0.140',
        '0.391 0.091 0.263 0.111',
        '0.054 0.116 0.047 0.130',
        'input-cost share α is set at 0.65',
    ], 'RIETI 21-E-090 Table 5')

    threshold = Decimal('30')  # million JPY in structural-estimation periods
    bunch_raw = [
        ('1989_1991', '1989-1991', '1.397', '0.227', '27.5', '16.498', '3.793', '0.550'),
        ('1992_1994', '1992-1994', '1.243', '0.237', '27.5', '16.277', '4.594', '0.543'),
        ('1997_1999', '1997-1999', '1.212', '0.208', '27.5', '16.261', '4.211', '0.542'),
    ]
    bunch = []
    for sid, years, b, bse, lower, dy, dyse, published_ratio in bunch_raw:
        exact_ratio = Decimal(dy) / threshold
        bunch.append({
            'sample_id': sid,
            'sample_years': years,
            'threshold_million_yen': fmt(threshold),
            'excess_bunching_estimate': b,
            'excess_bunching_se': bse,
            'excluded_window_lower_million_yen': lower,
            'marginal_buncher_sales_response_upper_million_yen': dy,
            'marginal_buncher_sales_response_upper_se_million_yen': dyse,
            'published_delta_y_over_threshold': published_ratio,
            'recomputed_delta_y_over_threshold': fmt(exact_ratio),
            'source_id': SOURCE_ID,
            'source_locator': 'PDF p.21 Table 3; PDF p.22 numerical-estimation inputs',
            'identification_status': 'LOCAL_HISTORICAL_MARGINAL_BUNCHER_RESPONSE_UPPER_BOUND',
            'population_scope': 'Japanese Census of Manufacture establishments in historical VAT regimes; manufacturing; survey uses shipment value as taxable-sales proxy',
            'model_use': 'THRESHOLD_DISTORTION_EVIDENCE_NOT_MACRO_A_ALLOC',
            'note': 'The convergence-method upper bound is a local sales-response measure for the marginal buncher around the historical 30m-JPY threshold. It is not an aggregate sales/GDP loss and not a current 10m-JPY/invoice-era estimate.'
        })

    # reform, group, e, e_se, theta, theta_se
    struct_raw = [
        ('1992', 'all', '0.028', '0.67',  '0.130', '0.027'),
        ('1997', 'all', '0.073', '0.082', '0.140', '0.040'),
        ('1992', 'firms', '0.391', '0.264', '0.091', '0.036'),
        ('1997', 'firms', '0.263', '0.229', '0.111', '0.055'),
        ('1992', 'sole_proprietors', '0.054', '0.164', '0.116', '0.018'),
        ('1997', 'sole_proprietors', '0.047', '0.096', '0.130', '0.037'),
    ]
    struct = []
    alpha = Decimal('0.65')
    for reform, group, e, ese, theta, thetase in struct_raw:
        va = threshold * (Decimal('1') - alpha)
        implied = va * Decimal(theta)
        struct.append({
            'reform_id': reform,
            'population_group': group,
            'input_cost_share_alpha': fmt(alpha),
            'tax_elasticity_e': e,
            'tax_elasticity_se': ese,
            'compliance_cost_theta': theta,
            'compliance_cost_theta_se': thetase,
            'theta_definition': 'Theta(y;alpha)=theta*(1-alpha)*y; theta is model compliance cost relative to value added',
            'mechanical_value_added_at_30m_sales_million_yen': fmt(va),
            'mechanical_compliance_cost_at_30m_sales_million_yen': fmt(implied),
            'source_id': SOURCE_ID,
            'source_locator': 'PDF pp.13-14 model; PDF pp.22-24 numerical estimation and Table 5',
            'identification_status': 'MODEL_CONTINGENT_LOCAL_STRUCTURAL_COMPLIANCE_COST_PARAMETER',
            'population_scope': 'historical Japanese manufacturing establishments around 30m-JPY VAT threshold; 1989-1999 regimes used for structural estimates',
            'real_resource_cost_interpretation': 'NO',
            'model_use': 'LOCAL_THRESHOLD_STRUCTURAL_EVIDENCE_NOT_C_VAT_OR_MACRO_A_ALLOC',
            'note': 'Paper defines compliance costs broadly to include monetary, time, operational and psychological expenses. Model assumes no VAT pass-through and omits the simplified tax system near the threshold. The 30m-JPY implied cost is a mechanical model example, not observed expenditure.'
        })
    return bunch, struct


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--check', action='store_true'); args = ap.parse_args()
    bunch, struct = build()
    outs = [(OUT_BUNCH, render(bunch)), (OUT_STRUCT, render(struct))]
    if args.check:
        stale = [str(p.relative_to(ROOT)) for p, text in outs if not p.exists() or p.read_text(encoding='utf-8') != text]
        if stale:
            raise SystemExit('stale generated artifacts: ' + ', '.join(stale))
        print('RIETI VAT-threshold structural bridge: current (3 bunching-response rows; 6 structural rows; no macro a_alloc calibration)')
    else:
        for p, text in outs:
            p.parent.mkdir(parents=True, exist_ok=True); p.write_text(text, encoding='utf-8')
        print(f'wrote {OUT_BUNCH.relative_to(ROOT)}: {len(bunch)} rows')
        print(f'wrote {OUT_STRUCT.relative_to(ROOT)}: {len(struct)} rows')

if __name__ == '__main__':
    main()
