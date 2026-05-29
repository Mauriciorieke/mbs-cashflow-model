# MBS Cash Flow Model

A Python implementation of a mortgage-backed security cash flow model with prepayment, default, and three-tranche sequential pay waterfall logic.
Built to project monthly cash flows on a Fannie Mae single-family loan pool and allocate those cash flows to senior, mezzanine, and equity tranches.

## What it does

- Loads loan data from Fannie Mae's public single-family loan dataset, [Pooltalk](https://fanniemae.mbs-securities.com/fannie) 
- Amortizes each loan individually with monthly default (CDR) and prepayment (PSA) assumptions
- Aggregates loan-level cash flows, amortization schedules, into pool level totals
- Runs cash flows through a three tranche sequential pay waterfall
- Allocates interest, losses, and principal across tranches with proper subordination
- Calculates weighted average life (WAL) per tranche
- Exports pool and tranche schedule to CSV
- Runs PSA scenario analysis across multiple prepayment speeds and outputs a WAL table by tranche

## Key assumptions

- Default rate: annual CDR applied monthly
- Prepayment: PSA convention (ramps to 6% terminal CPR at 100 PSA over 30 months, then flat)
- Recovery: configurable loss severity with a recovery lag in months
- Tranche structure: 80% senior, 15% mezzanine, 5% equity (configurable)
- Senior coupon: 5%, mezzanine coupon: 6%, equity receives residual

## Inputs

- Fannie Mae single-family loan-level data 
- Pool ID to filter on (will create an optional filter option) 
- CDR, loss severity, recovery lag, PSA speed
- Tranche weights and coupons

## Structure

- `psa()` calculates monthly CPR given PSA speed
- `amort_default()` builds the amortization schedule for a single loan
- `amort_each()` runs amortization across the full pool
- `aggregate()` rolls loan level results up to pool level
- `pay_interest()`, `loss_allocate()`, `principal_pay()` handle the per-month waterfall logic
- `waterfall()` ties it all together and produces the tranche schedule
- `wal()` calculates weighted average life for a given tranche
- `flatten_row()` and `export_tranche()` handle CSV export of the tranche schedule
- `export_loan_sch()` handles CSV export of the pool schedule
- `psa_scenario()` runs the full model across a list of PSA speeds and returns WAL by tranche

## Future work

- Add duration and yield calculations per tranche
- Add CDR scenario analysis alongside PSA stress testing
- Build a visualization layer using Streamlit or a similar tool
- Convert to pandas and NumPy for performance and cleaner data handling

## About

Built as a learning project to deepen my understanding of agency MBS structure, prepayment modeling, and securitization waterfalls. Companion piece to a CLO waterfall model I built in Excel.
