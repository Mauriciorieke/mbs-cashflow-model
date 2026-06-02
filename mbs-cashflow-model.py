"""
MBS Cash Flow Model

Projects monthly cash flows on a Fannie Mae single-family loan pool and
allocates those cash flows across a three-tranche sequential pay waterfall
(senior, mezzanine, equity).

Inputs:
    - Fannie Mae loan-level data file (pipe-delimited)
    - Pool ID to filter on
     - CDR (annual default rate), loss severity, recovery lag
    - PSA speed for prepayment assumption
    - Tranche weights and coupons

Outputs:
    - Loan-level amortization schedules
    - Pool-level aggregated cash flow schedule
    - Tranche-level cash flow schedule with interest, loss, principal, notional
    - WAL by tranche
"""
#Libraries
import csv
from scipy.optimize import brentq


# pmt_loan() function calculates the payment for an amortized loan. Takes inputs of balance, annual rate, frequency, and term month.
def pmt_loan(balance, annual_rate, freq, term_month):
    freq_rate = annual_rate / freq
    pmt = (freq_rate * balance) / (1 - (1 + freq_rate) ** -term_month)
    
    return pmt

# psa() function takes month and PSA speed as inputs, and returns a CPR rate using the PSA prepayment model.
# Standard: PSA 100 gives a 6% terminal CPR rate, ramped up linearly over 30 months. PSA speed changes the terminal rate.
def psa(month, psa_speed):
    speed = psa_speed/100
    adj_cpr = 0.06 * speed
    if month < 30:
        terminal_cpr = adj_cpr * (month / 30)
    else:
        terminal_cpr  = adj_cpr
    return terminal_cpr

# The amort_default() function creates a full amortization schedule for a loan, incorporating default and prepayment.
# Returns a list of nested dictionaries representing the monthly schedule.
# Every month the payment is recalculated to account for defaults and prepayments before solving for the new payment.
# This function is called inside later functions.
def amort_default(balance, annual_rate, freq, term_month, annual_cdr, loss_sev, recovery_lag, psa_speed):
    month_cdr = annual_cdr/freq
    month_rate = annual_rate / freq
    sch = []
    end_balance = balance
    rem_term = term_month
    speed = psa_speed
    
    for month in range(1, term_month + 1):
        beg_balance = end_balance
        default = month_cdr * beg_balance
        smm = 1 - (1 - psa(month, speed))** (1 / freq)
        prepay = (beg_balance - default) * smm
        pmt_current = pmt_loan((beg_balance - default - prepay), annual_rate,freq, rem_term)
        interest = month_rate * (beg_balance - default - prepay)
        principal = pmt_current - interest
        end_balance = beg_balance - principal - default - prepay
        loss = 0
        rec = 0
        if month > recovery_lag:
            lr_def = sch[month - recovery_lag - 1]["default"]
            rec = (1 - loss_sev) * lr_def
            loss = loss_sev * lr_def
        total_cf = interest + principal + rec + prepay          
        sch.append({"month": month,
                    "beg balance": round(beg_balance,2),
                    "pmt": round(pmt_current,2),
                    "interest": round(interest,2),
                    "principal": round(principal,2),
                    "end balance": round(end_balance,2),
                    "default": round(default,2),
                    "loss": round(loss,2),
                    "recovery": round(rec,2),
                    "prepayment": round(prepay,2),
                    "total cashflow": round(total_cf,2),
                    "remain term": rem_term
                    })
        rem_term = rem_term - 1
        
    return sch

# pool_loader() function opens and reads the Fannie Mae loan-level data file.
# Parses the text file delimited by "|" and returns a list of loans matching the pool_id.
def pool_loader(filename, pool_id):
    pool = []
    with open(filename, 'r',newline = "") as file:
        csv_reader = csv.DictReader(file, delimiter = "|")
        #this for loop needs to be in the with open 
        for row in csv_reader:
            if row["Security Identifier"] != pool_id:
                continue
            pool.append({"balance": float(row["Current Investor Loan UPB"]),
                         "rate": (float(row["Current Interest Rate"]))/100,
                         "loan term": int(row["Loan Term"])
                         })
    return pool

# amort_each() function loops through all the loans and calls amort_default() to create an amortization schedule for each loan.
# Inputs are the model assumptions needed by amort_default(), plus the output from pool_loader().
def amort_each(pool, freq, annual_cdr, loss_sev, recovery, psa_speed):
    pool_amort = []
    for loan in pool:
        pool_amort.append(amort_default(loan["balance"],loan["rate"], freq, loan["loan term"], annual_cdr, loss_sev, recovery, psa_speed))
    return pool_amort

# The aggregate() function rolls up all loan-level schedules by month into one pool-level amortization schedule.
# For each month it sums: beginning balance, interest, principal, default, ending balance, loss, recovery, prepayment, and total cash flow.
def aggregate(pool_amort, pool):
    pool_sch = []
    max_term = max(loan["loan term"] for loan in pool)
    for month in range(1, max_term + 1):
        total_balance = sum(loan[month - 1]["beg balance"] for loan in pool_amort if month - 1 <len(loan))
        total_interest = sum(loan[month - 1]["interest"] for loan in pool_amort if month - 1 <len(loan))
        total_principal = sum(loan[month - 1]["principal"] for loan in pool_amort if month - 1 <len(loan))
        total_def = sum(loan[month - 1]["default"] for loan in pool_amort if month - 1 <len(loan))
        total_end = sum(loan[month - 1]["end balance"] for loan in pool_amort if month - 1 <len(loan))
        total_loss = sum(loan[month - 1]["loss"] for loan in pool_amort if month - 1 <len(loan))
        total_rec = sum(loan[month - 1]["recovery"] for loan in pool_amort if month - 1 <len(loan))
        total_prepay = sum(loan[month - 1]["prepayment"] for loan in pool_amort if month - 1 < len(loan))
        total_cfs = sum(loan[month - 1]["total cashflow"] for loan in pool_amort if month - 1 <len(loan))
        pool_sch.append({"month": month,
                             "balance": total_balance,
                             "interest": total_interest,
                             "principal": total_principal,
                             "default": total_def,
                             "end balance": total_end,
                             "loss": total_loss,
                             "recovery": round(total_rec, 2),
                             "prepayment": total_prepay,
                             "total cashflow": total_cfs
                             })
    return pool_sch
    
# wac() function calculates weighted average coupon for the pool, weighted by loan balance.
def wac(pool):
    wac = 0 
    total = sum(loan["balance"] for loan in pool)
    for loan in pool:
        weight = loan["balance"] / total
        wac = wac + (loan["rate"] * weight)
    return wac

# wam() function calculates weighted average maturity for the pool, weighted by loan balance.
def wam(pool):
    wam = 0
    total = sum(loan["balance"] for loan in pool)
    for loan in pool:
        weight = loan["balance"] / total
        wam = wam + (loan["loan term"] * weight)
    return wam


# pay_interest() function takes the tranches, the aggregate schedule, and the month as inputs. Distributes total interest sequentially across tranches (senior -> equity).
# Returns the interest allocated to each tranche.
def pay_interest(tranches, agg_pool, month):
    current_int = agg_pool[month]["interest"]
    senior_owed = tranches[0]["notional"] * (tranches[0]["coupon"]/12)
    mezz_owed = tranches[1]["notional"] * (tranches[1]["coupon"]/12)
    equity_owed = tranches[2]["notional"] * (tranches[2]["coupon"]/12)

    if (current_int - senior_owed) >= 0:
        senior_paid = senior_owed
    else:
        senior_paid = current_int
    current_int = current_int - senior_paid
        
    if (current_int - mezz_owed) >= 0:
        mezz_paid = mezz_owed
    else:
        mezz_paid = current_int
    current_int = current_int - mezz_paid

    equity_paid = current_int

    return {"senior": round(senior_paid,2),
            "mezz": round(mezz_paid,2),
            "equity": round(equity_paid,2)
            }

# loss_allocate() function takes the tranches, the aggregate schedule, and the month as inputs. Distributes total loss sequentially across tranches (equity -> senior).
# Returns the loss allocated to each tranche.
def loss_allocate(tranches, agg_pool, month):
    current_loss = agg_pool[month]["loss"]
    if (tranches[2]["notional"] - current_loss) >= 0:
        equity_loss = current_loss
    else:
        equity_loss = tranches[2]["notional"]
    current_loss = current_loss - equity_loss
    
    if (tranches[1]["notional"] - current_loss) >= 0:
        mezz_loss = current_loss
    else:
        mezz_loss = tranches[1]["notional"]
    current_loss = current_loss - mezz_loss

    senior_loss = max(0, current_loss)

    return {"senior": senior_loss,
            "mezz": mezz_loss,
            "equity": equity_loss
            }
# principal_pay() function takes the tranches, the aggregate schedule, and the month as inputs. Distributes total principal, recovery, and prepayment sequentially across tranches (senior -> equity).
# Returns the principal paid to each tranche.
def principal_pay(tranches, agg_pool, month):
    current_pay = (agg_pool[month]["principal"] + agg_pool[month]["recovery"] + agg_pool[month]["prepayment"])
    if (tranches[0]["notional"]-current_pay) >= 0:
        senior_pay = current_pay
    else:
        senior_pay = tranches[0]["notional"]
    current_pay = current_pay - senior_pay

    if (tranches[1]["notional"] - current_pay) >= 0:
        mezz_pay = current_pay
    else:
        mezz_pay = tranches[1]["notional"]
    current_pay = current_pay - mezz_pay

    equity_pay = max(0, current_pay)

    return {"senior": senior_pay,
            "mezz": mezz_pay,
            "equity": equity_pay
            }


# waterfall() function creates the cash flow allocations for interest, loss, and principal repayment by calling pay_interest(), loss_allocate(), and principal_pay().
# Returns a list of monthly entries. Each entry contains the month and nested dictionaries for senior, mezz, and equity, each holding {interest, loss, principal, notional}.
def waterfall(tranches, agg_pool):
    tranche_sch = []
    for i in range(len(agg_pool)):
        int_result = pay_interest(tranches, agg_pool, i)
        
        loss_result = loss_allocate(tranches, agg_pool, i)
        tranches[0]["notional"] = tranches[0]["notional"] - loss_result["senior"]
        tranches[1]["notional"] = tranches[1]["notional"] - loss_result["mezz"]
        tranches[2]["notional"] = tranches[2]["notional"] - loss_result["equity"]
        
        pay_result = principal_pay(tranches, agg_pool, i)
        tranches[0]["notional"] = tranches[0]["notional"] - pay_result["senior"]
        tranches[1]["notional"] = tranches[1]["notional"] - pay_result["mezz"]
        tranches[2]["notional"] = tranches[2]["notional"] - pay_result["equity"]
        
        tranche_sch.append({"month": i + 1,
                            "senior": {"interest": int_result["senior"], "loss": round(loss_result["senior"], 2), "principal": round(pay_result["senior"],2), "notional": round(tranches[0]["notional"],2)},
                            "mezz": {"interest": int_result["mezz"], "loss": round(loss_result["mezz"], 2), "principal": round(pay_result["mezz"],2), "notional": round(tranches[1]["notional"],2)},
                            "equity": {"interest": int_result["equity"], "loss": round(loss_result["equity"], 2), "principal": round(pay_result["equity"],2), "notional": round(tranches[2]["notional"],2)}
                            })
    return tranche_sch

# tranche_build() creates a fresh tranche structure with starting notionals and coupons. Used to reset tranches before each waterfall run since waterfall() mutates the notional values.
def tranche_build(agg_pool, senior_weight, mezz_weight, equity_weight):
    start_bal = agg_pool[0]["balance"]
    return [
        {"name": "senior", "notional": senior_weight * start_bal, "coupon": 0.05},
        {"name": "mezz", "notional": mezz_weight * start_bal, "coupon": 0.06},
        {"name": "equity", "notional": equity_weight * start_bal, "coupon": 0.0}
    ]

# wal() function calculates weighted average life for a given tranche. Measures the average time required to repay principal.
# WAL = sum(month * principal[i]) / sum(principal), divided by 12 to convert from months to years.
def wal(tranche_sch, tranche_name):
    total = 0 
    weight = 0
    for entry in tranche_sch:
        month = entry["month"]
        principal_t = entry[tranche_name]["principal"]
        total = total + principal_t
        weight = weight + (month * principal_t)
    wal = (weight / total)/12
    return wal

# Exporting aggregated amort schedule into a CSV file
def export_loan_sch(agg_pool):
    with open('aggregate_pool.csv','w', newline = '') as csvfile:
        fieldnames = list(agg_pool[0].keys())
        w = csv.DictWriter(csvfile, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(agg_pool)
        
# Since the tranche schedule was a nested dict, this function flattens the row, one at a time.
def flatten_row(row):
    flat = {}
    flat["month"] = row["month"]
    for tranche, fields in row.items():
        if tranche == "month":
            continue
        for field, value in fields.items():
            flat[tranche + "_" + field] = value
    return flat


# When exporting the tranche schedule to CSV the function calls flatten_row() to create a flat dictionary for every row, before exporting.
def export_tranche(tranche_sch):
    flat_tranche = []
    for row in tranche_sch:
        flat_tranche.append(flatten_row(row))
    with open("tranche_output.csv", 'w', newline = '') as csvfile:
        fieldnames = list(flat_tranche[0].keys())
        w = csv.DictWriter(csvfile, fieldnames = fieldnames)
        w.writeheader()
        w.writerows(flat_tranche)
                       

# Scenario analysis function to show the WAL fro each tranceh based on a range of PSA speeds.
# The only new input would be psa_speed. 
def psa_scenario(pool, psa_speed, freq, annual_cdr, loss_sev, recovery, senior_weight, mezz_weight, equity_weight):
    output = []
    
    for speed in psa_speed:
        loan_schedule = amort_each(pool, freq, annual_cdr, loss_sev, recovery, speed)
        pool_schedule = aggregate(loan_schedule, pool)
        new_tranche = tranche_build(pool_schedule, senior_weight, mezz_weight, equity_weight)
        pool_waterfall = waterfall(new_tranche, pool_schedule)
        output.append({"psa speed": speed, 
                        "senior_wal": wal(pool_waterfall, "senior"),
                        "mezz_wal": wal(pool_waterfall, "mezz"), 
                        "equity_wal": wal(pool_waterfall, "equity")
                        })
    return output

'''
Valuation Functions: PV, price, yield, duration, and convexity per tranche.
pv_tranche() discounts monthly cash flows (interest + principal - loss) at a flat annual rate.
price() calls pv_tranche() and expresses the result as a percentage of starting notional.
yield_cal() uses scipy brentq to solve for the rate that matches a given market price.
duration() and convex() use a 10 bps symmetric shock to approximate modified duration and convexity.
'''
def pv_tranche(tranche_sch, name, dr):
    disc_cfs = 0
    freq = 12
    for entry in tranche_sch:
        month = entry["month"]
        cf = entry[name]["interest"] + entry[name]["principal"] - entry[name]["loss"]
        disc_cfs = disc_cfs + (cf/(1 + (dr/freq)) ** month)
    return disc_cfs

def price(tranche_sch, name, dr):
    pv = pv_tranche(tranche_sch, name, dr)
    notional = tranche_sch[0][name]["notional"] + tranche_sch[0][name]["principal"] + tranche_sch[0][name]["loss"]
    price = (pv / notional) * 100
    return price

def yield_cal(tranche_sch, name, mark_price):
    def diff(rate):
        price_diff = price(tranche_sch, name, rate)
        return price_diff - mark_price
    return brentq(diff, 0.0001, 0.99)    

def duration(tranche_sch, name, dr):
    delta_y = 0.001
    p0 = price(tranche_sch, name, dr)
    p_up = price(tranche_sch, name, dr - delta_y)
    p_down = price(tranche_sch, name, dr + delta_y)
    dur = (p_up - p_down)/(2 * delta_y * p0)
    return dur

def convex(tranche_sch, name, dr):
    delta_y = 0.001
    p0 = price(tranche_sch, name, dr)
    p_up = price(tranche_sch, name, dr - delta_y)
    p_down = price(tranche_sch, name, dr + delta_y)
    con = ((p_up + p_down) - (2 * p0))/(p0 * delta_y ** 2)
    return con

#inputs needed for the different functions
filename = "fannie.txt" 
pool_id = "MA6099"
freq = 12
annual_cdr = 0.005
loss_sev = 0.3
recovery = 12
psa_speed = 100
load_pool = pool_loader(filename, pool_id)
amort_pool = amort_each(load_pool, freq, annual_cdr, loss_sev, recovery, psa_speed)
agg_pool = aggregate(amort_pool, load_pool)
wac_pool = wac(load_pool)
wam_pool = wam(load_pool)
senior_weight = 0.8
mezz_weight = 0.15
equity_weight = 0.05
psa_speeds = [50, 100, 150, 200, 250, 300]
dr = 0.05

#Structure to run the model
tranches = tranche_build(agg_pool,senior_weight, mezz_weight, equity_weight)
tranche_sch = waterfall(tranches, agg_pool)

export_loan_sch(agg_pool)
export_tranche(tranche_sch)

# Calling the PSA Scenarios function and Printing out to console as a table.
scenario_analysis = psa_scenario(load_pool, psa_speeds, freq, annual_cdr, loss_sev, recovery, senior_weight, mezz_weight, equity_weight)
print(f"{'PSA SPEED':<12}{'SENIOR WAL':<14}{'MEZZ WAL':<12}{'EQUITY WAL'}")
for row in scenario_analysis:
    print(f"{row['psa speed']:<12.2f}{row['senior_wal']:<14.2f}{row['mezz_wal']:<12.2f}{row['equity_wal']:.2f}")
    

# Calling all the valuation functions to print.
senior_dcf = pv_tranche(tranche_sch, "senior", dr)
mezz_dcf = pv_tranche(tranche_sch, "mezz", dr)
equity_dcf = pv_tranche(tranche_sch, "equity", dr)

senior_price = price(tranche_sch, "senior", dr)
mezz_price = price(tranche_sch, "mezz", dr)
equity_price = price(tranche_sch, "equity", dr)

senior_yld = yield_cal(tranche_sch, "senior", 100)
mezz_yld = yield_cal(tranche_sch, "mezz", 100)
equity_yld = yield_cal(tranche_sch, "equity", 100)

senior_dur = duration(tranche_sch, "senior", dr)
mezz_dur = duration(tranche_sch, "mezz", dr)
equity_dur = duration(tranche_sch, "equity", dr) 

senior_con = convex(tranche_sch, "senior", dr)
mezz_con = convex(tranche_sch, "mezz", dr)
equity_con = convex(tranche_sch, "equity", dr) 
 
# Prints all the valuation metrics into a table based on tranche cleanly into the console.
print()
print(f"{'':<12}{'SENIOR':<14}{'MEZZ':<12}{'EQUITY'}")
print(f"{'DCFs':<12}{senior_dcf:<14.2f}{mezz_dcf:<12.2f}{equity_dcf:.2f}")
print(f"{'Price':<12}{senior_price:<14.2f}{mezz_price:<12.2f}{equity_price:.2f}")
print(f"{'Yield':<12}{senior_yld:<14.2%}{mezz_yld:<12.2%}{equity_yld:.2%}")
print(f"{'Duration':<12}{senior_dur:<14.2f}{mezz_dur:<12.2f}{equity_dur:.2f}")
print(f"{'Convexity':<12}{senior_con:<14.2f}{mezz_con:<12.2f}{equity_con:.2f}")

