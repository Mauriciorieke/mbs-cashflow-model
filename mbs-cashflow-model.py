import csv

def psa(month, psa_speed):
    speed = psa_speed/100
    adj_cpr = 0.06 * speed
    if month < 30:
        terminal_cpr = adj_cpr * (month / 30)
    else:
        terminal_cpr  = adj_cpr
    return terminal_cpr

def pmt_loan(balance, annual_rate, freq, term_month):
    freq_rate = annual_rate / freq
    pmt = (freq_rate * balance) / (1 - (1 + freq_rate) ** -term_month)
    
    return pmt

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

def amort_each(pool, freq, annual_cdr, loss_sev, recovery, psa_speed):
    pool_amort = []
    for loan in pool:
        pool_amort.append(amort_default(loan["balance"],loan["rate"], freq, loan["loan term"], annual_cdr, loss_sev, recovery, psa_speed))
    return pool_amort

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
    
def wac(pool):
    wac = 0 
    total = sum(loan["balance"] for loan in pool)
    for loan in pool:
        weight = loan["balance"] / total
        wac = wac + (loan["rate"] * weight)
    return wac
    
def wam(pool):
    wam = 0
    total = sum(loan["balance"] for loan in pool)
    for loan in pool:
        weight = loan["balance"] / total
        wam = wam + (loan["loan term"] * weight)
    return wam



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

def tranche_build(agg_pool, senior_weight, mezz_weight, equity_weight):
    start_bal = agg_pool[0]["balance"]
    return [
        {"name": "senior", "notional": senior_weight * start_bal, "coupon": 0.05},
        {"name": "mezz", "notional": mezz_weight * start_bal, "coupon": 0.06},
        {"name": "equity", "notional": equity_weight * start_bal, "coupon": 0.0}
    ]

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


tranches = tranche_build(agg_pool,senior_weight, mezz_weight, equity_weight)

tranche_sch = waterfall(tranches, agg_pool)


wal_s = wal(tranche_sch, "senior")
wal_m = wal(tranche_sch, "mezz")
wal_e = wal(tranche_sch, "equity")
print(wal_s)
print(wal_m)
print(wal_e)


#for i in range (88, 95):
 #   print(f"month: {tranche_sch[i]["month"]}")
  #  print(f"senior: {tranche_sch[i]["senior"]["notional"]}")
   # print(f"mezz: {tranche_sch[i]["mezz"]["notional"]}")

