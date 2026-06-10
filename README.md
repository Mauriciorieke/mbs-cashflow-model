# MBS Cash Flow Model

A Python implementation of a mortgage-backed security cash flow model with prepayment, default, and three-tranche sequential pay waterfall logic. Built to project monthly cash flows on a Fannie Mae single-family loan pool, allocate those cash flows to senior, mezzanine, and equity tranches, and calculate tranche-level valuation metrics.

This repository contains two implementations. v1 is a pure-Python version that builds the logic from first principles, looping over individual loans. v2 is a vectorized rewrite using NumPy and pandas that processes the entire loan pool as matrices, running much faster on full-size pools while producing the same results, with two corrections noted below.

## What it does

- Loads loan data from Fannie Mae's public single-family loan dataset, [Pooltalk](https://fanniemae.mbs-securities.com/fannie)
- Amortizes the loan pool with monthly default (CDR) and prepayment (PSA) assumptions
- Aggregates loan-level cash flows into pool-level totals
- Runs cash flows through a three-tranche sequential pay waterfall
- Allocates interest, losses, and principal across tranches with proper subordination
- Calculates weighted average life (WAL) per tranche
- Exports pool and tranche schedules to CSV
- Runs PSA scenario analysis across multiple prepayment speeds and outputs a WAL table by tranche
- Calculates tranche-level PV, price, yield, modified duration, and convexity

## Implementation

v1 (pure Python) loops over each loan individually, building per-loan amortization schedules and aggregating them. Clear and readable, but slow on large pools.

v2 (NumPy / pandas) loads and filters the data with pandas, then holds the whole pool as NumPy matrices with loans as rows and months as columns. Instead of looping over every loan, it loops only over the months and does the math for all loans at once with array operations. An "alive" mask handles loans that mature partway through. The aggregation is just summing each matrix down the loan axis. The waterfall is still a month-by-month loop since the tranche payments have to go in order, but it runs on the already-aggregated pool vectors so it is fast. On a roughly 6,000-loan pool, v2 runs much faster than v1.

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

## Structure (v2)

- `pmt_loan()` computes the monthly payment, vectorized across all loans
- `psa()` returns the monthly SMM from a PSA speed and month
- `amortization()` runs the full vectorized pool amortization and returns aggregated pool cash flow vectors
- `waterfall()` allocates interest, losses, and principal across the three tranches month by month
- `wal()` calculates weighted average life per tranche
- `pv()` discounts tranche cash flows at a flat annual rate
- `price()` expresses tranche PV as a percentage of starting notional
- `yield_cal()` solves per tranche for the yield matching a target price (scipy brentq)
- `duration()` and `convexity()` use a 10 bps symmetric shock to approximate modified duration and convexity
- `psa_scenario()` runs the full model across a list of PSA speeds and returns WAL by tranche
- `export_pool()` and `export_tranche()` write the pool and tranche schedules to CSV

## Corrections in v2

While rebuilding the model with NumPy, two simplifications in v1 were identified and corrected.

1. Remaining term vs. original term. v1 amortized every loan over its original Loan Term. v2 amortizes over Remaining Months to Maturity, so seasoned loans are scheduled over the time they actually have left. This produces the correct monthly payment for loans that are not brand new.

2. Loss recognition past maturity. Losses and recoveries lag defaults by the recovery lag (12 months). In v1, each loan's schedule ended at its maturity month, which truncated the loss/recovery tail for defaults occurring in a loan's final year. v2 carries this tail through, recognizing those losses and recoveries on the correct lagged timing even after the loan's scheduled payments end, since the default has already occurred and the loss is real.

Effect on tranche cash flows. Because the missed tail contained both recoveries (principal, paid top-down) and losses (write-downs, absorbed bottom-up), the correction is not a wash. Capturing the full tail means senior and mezzanine pay down slightly faster, and equity absorbs slightly more loss. v1's truncation understated both, marginally flattering the structure.

## Future work

- Add Monte Carlo simulation treating CDR and PSA as random variables
- Add CDR scenario analysis alongside PSA stress testing
- Build an interactive visualization layer using Streamlit or Tableau

## About

Built as a learning project to deepen understanding of agency MBS structure, prepay