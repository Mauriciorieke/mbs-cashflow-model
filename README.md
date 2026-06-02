# MBS Cash Flow Model

A Python implementation of a mortgage-backed security cash flow model with prepayment,
default, and three-tranche sequential pay waterfall logic.
Built to project monthly cash flows on a Fannie Mae single-family loan pool,
allocate those cash flows to senior, mezzanine, and equity tranches,
and calculate tranche-level valuation metrics.

## What it does

- Loads loan data from Fannie Mae's public single-family loan dataset, [Pooltalk](https://fanniemae.mbs-securities.com/fannie)
- Amortizes each loan individually with monthly default (CDR) and prepayment (PSA) assumptions
- Aggregates loan-level cash flows into pool level totals
- Runs cash flows through a three tranche sequential pay waterfall
- Allocates interest, losses, and principal across tranches with proper subordination
- Calculates weighted average life (WAL) per tranche
- Exports pool and tranche schedules to CSV
- Runs PSA scenario analysis across multiple prepayment speeds and outputs a WAL table by tranche
- Calculates tranche-level PV, price, yield, modified duration, and convexity

## Key assumptions

- Default rate: annual CDR applied monthly
- Prepayment: PSA convention (ramps to 6% terminal CPR at 100 PSA over 30 months, then flat)
- Recovery: configurable loss severity with a recovery lag in months
- Tranche structure: 80% senior, 15% mezzanine, 5% equity (configurable)
- Senior coupon: 5%, mezzanine coupon: 6%, equity receives residual

## Inputs

- Fannie Mae single-family loan-level data
- Pool ID to filter on
- CDR, loss severity, recovery lag, PSA speed
- Tranche weights and coupons
- Discount rate for valuation

## Structure

- `psa()` calculates monthly CPR given PSA speed
- `amort_default()` builds the amortization schedule for a single loan
- `amort_each()` runs amortization across the full pool
- `aggregate()` rolls loan level results up to pool level
- `wac()` and `wam()` calculate pool level weighted average coupon and maturity
- `pay_interest()`, `loss_allocate()`, `principal_pay()` handle the per-month waterfall logic
- `waterfall()` ties it all together and produces the tranche schedule
- `wal()` calculates weighted average life for a given tranche
- `flatten_row()` and `export_tranche()` handle CSV export of the tranche schedule
- `export_loan_sch()` handles CSV export of the pool schedule
- `psa_scenario()` runs the full model across a list of PSA speeds and returns WAL by tranche
- `pv_tranche()` discounts tranche cash flows at a flat annual rate
- `price()` expresses tranche PV as a percentage of starting notional
- `yield_cal()` solves for the yield that equates calculated price to a given market price
- `duration()` calculates approximate modified duration using a 10 bps symmetric shock
- `convex()` calculates approximate convexity using a 10 bps symmetric shock

## Sample Output
PSA SPEED   SENIOR WAL    MEZZ WAL    EQUITY WAL
50.00       4.13          8.82        9.82
100.00      3.77          8.51        9.75
150.00      3.46          8.16        9.66
200.00      3.20          7.78        9.54
250.00      2.98          7.39        9.39
300.00      2.78          6.99        9.20

            SENIOR        MEZZ        EQUITY
DCFs        6149599.99    1232779.37  562581.10
Price       100.00        106.91      146.37
Yield       5.00%         6.00%       12.73%
Duration    3.34          6.73        5.47
Convexity   15.67         53.05       44.36

## Future work

- Convert to pandas and NumPy for performance on larger pools
- Add Monte Carlo simulation treating CDR and PSA as random variables
- Add CDR scenario analysis alongside PSA stress testing
- Build a visualization layer using Streamlit or Tableau

## About

Built as a learning project to deepen understanding of agency MBS structure,
prepayment modeling, securitization waterfalls, and fixed income valuation.
Companion piece to a CLO waterfall model built in Excel.