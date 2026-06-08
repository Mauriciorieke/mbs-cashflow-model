"""
Created on Wed Jun  3 21:57:05 2026

MBS Cash Flow Model v2 - Vectorized rewrite using NumPy and pandas (in progress)
Vectorized amortization engine complete. Aggregation, waterfall, and valuation to follow.

@author: Mauricio Rieke
"""
import numpy as np
import pandas as pd
from scipy.optimize import brentq

# Read Fannie File, pipe delimited
df = pd.read_csv("fannie.txt", sep = "|", low_memory=False)

# Filter by pool ID
pool_id = "MA6099"
df = df[df["Security Identifier"] == pool_id]

# Pull the three columns and convert to numpy array
balance = df["Current Investor Loan UPB"].to_numpy()
rate = df["Current Interest Rate"].to_numpy() / 100
terms = df["Remaining Months to Maturity"].to_numpy()

'''
I decied to use Remaining Months to Maturity, not original Loan Term. So that seasoned
loans amortize over the months they actually have left rather than a
full original term. (v1 used original Loan Term, which slightly
misstated the payment on already-seasoned loans.)
terms = df["Loan Term"].to_numpy()
'''


# Payment function
def pmt_loan(balance, annual_rate, term_month):
    freq_rate = annual_rate / 12
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
    
    terminal_cpr = 1 - (1 - terminal_cpr)** (1 / 12)
    
    return terminal_cpr

n_loans = len(balance)
n_month = terms.max()
annual_cdr = 0.005
lag = 12
loss_sev = 0.3
psa_speed = 100



month_cdr = np.full((n_loans,), (annual_cdr / 12))
beg_bal = np.zeros([n_loans,n_month])
interest_matrix = np.zeros([n_loans, n_month])
principal_matrix = np.zeros([n_loans, n_month])
default_matrix = np.zeros([n_loans, n_month])
prepay_matrix = np.zeros([n_loans, n_month])
loss_matrix = np.zeros([n_loans, n_month])
recovery_matrix = np.zeros([n_loans, n_month])
end_bal = np.zeros([n_loans, n_month])
running_balance = balance.copy()

for month in range(n_month):
    alive = (terms - month) > 0
    smm = np.full((n_loans,),psa(month + 1, psa_speed)) #The creation of the full array of the same SMM was for future work of differing CPR per loan
    beg_balance = running_balance.copy()
    beg_bal[:,month] = beg_balance.copy()
    default_matrix[:,month] = beg_balance * month_cdr * alive 
    prepay_matrix[:,month] = smm * (beg_balance - default_matrix[:,month]) * alive
    interest_matrix[:,month] = (beg_balance - default_matrix[:,month] - prepay_matrix[:,month]) * (rate / 12) * alive
    principal_matrix[:,month] = (pmt_loan((beg_balance - default_matrix[:,month] - prepay_matrix[:,month]), rate, np.maximum(1,(terms - month))) - interest_matrix[:,month]) * alive 
    if month >= lag:
        loss_matrix[:,month] = default_matrix[:,(month - lag)] * loss_sev
        recovery_matrix[:,month] = default_matrix[:,(month - lag)] * (1 - loss_sev)
    end_bal[:,month] = beg_balance - default_matrix[:,month] - prepay_matrix[:,month] - principal_matrix[:,month]
    running_balance = end_bal[:,month].copy() * alive # Using the alive here is more of a safegaurd    
''' (For the loss and recoveries) 
Losses and recoveries lag defaults by the recovery lag (12 months).
A loan's final-year defaults therefore realize losses/recoveries AFTER 
its scheduled maturity. I intentionally let this tail run past maturity
rather than masking it with `alive`, since the default already occurred
and the loss/recovery is real regardless of the loan's payment end date.'''
   
pool_begbal = np.sum(beg_bal, axis=0)
pool_int = np.sum(interest_matrix, axis=0)
pool_principal = np.sum(principal_matrix, axis=0)
pool_default = np.sum(default_matrix, axis=0)
pool_prepay = np.sum(prepay_matrix, axis=0)
pool_loss = np.sum(loss_matrix, axis=0)
pool_recovery = np.sum(recovery_matrix, axis=0)
pool_endbal = np.sum(end_bal, axis=0)

agg_pool = np.vstack((pool_begbal, pool_default,
                     pool_prepay, pool_int,
                     pool_principal, pool_loss,
                     pool_recovery, pool_endbal)
                     ).T
'''Creates a Matrix for the aggregated pool amortization
Uses vstack then ".T" to transpose the matrix to have months as rows
This is mainly to create a matrix to export to CSV'''



# iteration for waterfall tranching - run through month 

#Key for Tranche matrix Indexing
sr_int, sr_loss, sr_prin, sr_not = 0, 1, 2, 3
mz_int, mz_loss, mz_prin, mz_not = 4, 5, 6, 7
eq_int, eq_loss, eq_prin, eq_not = 8, 9, 10, 11

#Weights for notionals
senior_weight = 0.8
mezz_weight = 0.15
equity_weight = 0.05
weights = np.array([senior_weight, mezz_weight, equity_weight])
#Coupons for tranches
sr_coup = 0.05
mz_coup = 0.06
eq_coup = 0
tranche_rate = np.array([sr_coup, mz_coup, eq_coup])

# Creating Tranche Matrix and setting original values to starting notionals. 
tranche_output = np.zeros((12,n_month))
running_val = weights * pool_begbal[0]


for month in range(n_month):
    
    #Interest owed
    cur_int = pool_int[month].copy()
    int_owed = running_val * (tranche_rate / 12)
    sr_paid = min(cur_int, int_owed[0])
    cur_int -= sr_paid
    mz_paid = min(cur_int, int_owed[1])
    cur_int -= mz_paid
    eq_paid = max(cur_int, 0)
    tranche_output[[sr_int,mz_int,eq_int], month] = sr_paid, mz_paid, eq_paid
    
    #Loss allocated
    cur_loss = pool_loss[month].copy()
    eq_lost = min(cur_loss, running_val[2])
    cur_loss -= eq_lost
    mz_lost = min(cur_loss, running_val[1])
    cur_loss -= mz_lost
    sr_lost = min(cur_loss, running_val[0])
    cur_loss -= sr_lost
    tranche_output[[sr_loss, mz_loss, eq_loss], month] = sr_lost, mz_lost, eq_lost
    running_val -= np.array([sr_lost, mz_lost, eq_lost])
    
    #Prinicpal and recovery repayment
    cur_pmt = pool_principal[month] + pool_recovery[month] + pool_prepay[month]
    sr_repay = min(cur_pmt, running_val[0])
    cur_pmt -= sr_repay
    mz_repay = min(cur_pmt, running_val[1])
    cur_pmt -= mz_repay
    eq_repay = min(cur_pmt, running_val[2])
    tranche_output[[sr_prin, mz_prin, eq_prin], month] = sr_repay, mz_repay, eq_repay
    running_val -= np.array([sr_repay, mz_repay, eq_repay])
    
    tranche_output[[sr_not, mz_not, eq_not], month] = running_val
    


def export_pool(agg_pool): # Exports the Pool amortization schedule
    df = pd.DataFrame(agg_pool, columns=["Beginning Balance", "Default",
                                  "Prepayment", "Interest",
                                  "Principal", "loss",
                                  "Recovery", "End Balance"
                                  ])
    df.to_csv('pool_output.csv')

def export_tranche(tranche): #
    t = tranche.T
    df_1 = pd.DataFrame(t, columns=["sr_int", "sr_loss",
                                  "sr_prin", "sr_not",
                                  "mz_int", "mz_loss",
                                  "mz_prin", "mz_not",
                                  "eq_int", "eq_loss",
                                  "eq_prin", "eq_not"
                                  ])
    df_1.to_csv('output.csv')


#Valuation (pv to price to yield to dur to convex)
disc_rate = 0.05
market_price = np.full((3,), 100)    

def wal(tranche_output):
    weight = np.zeros((3,))
    sr = sum(tranche_output[sr_prin,:])
    mz = sum(tranche_output[mz_prin,:])
    eq = sum(tranche_output[eq_prin,:])
    totals = np.array((sr, mz, eq))
    for m in range(n_month):
        pi = np.array((tranche_output[sr_prin, m], tranche_output[mz_prin, m], tranche_output[eq_prin, m])) 
        weight += (m + 1) * pi
    wal = (weight / totals) / 12
    return wal

def pv(tranche_output, disc_rate):
    disc = np.zeros((3,)) 
    for month in range(n_month):
        sr_cf = tranche_output[sr_int, month] + tranche_output[sr_prin, month] - tranche_output[sr_loss, month]
        mz_cf = tranche_output[mz_int, month] + tranche_output[mz_prin, month] - tranche_output[mz_loss, month]
        eq_cf = tranche_output[eq_int, month] + tranche_output[eq_prin, month] - tranche_output[eq_loss, month]        
        cfs = np.array((sr_cf, mz_cf, eq_cf))
        disf = (1+(disc_rate / 12)) ** -(month + 1)
        disc += (disf * cfs)
    return disc

def price(tranche_output, disc_rate):
    value = pv(tranche_output, disc_rate)
    notionals =  np.array((tranche_output[sr_not,0], tranche_output[mz_not,0], tranche_output[eq_not,0]))
    price = (value / notionals) * 100 
    return price 

def yield_cal(tranche_output, market_p):
    yields = np.zeros((3,))
    for i in range(3):
        diff = lambda rate, i=i: price(tranche_output, rate)[i] - market_p[i] #Not fully understanding the Late binding i=i
        yields[i] = brentq(diff, 0.0001, 0.99)
    return yields

def duration(tranche_output, disc_rate):
    delta_y = 0.001
    num = price(tranche_output, disc_rate - delta_y) - price(tranche_output, disc_rate + delta_y)
    dem = 2 * delta_y * price(tranche_output, disc_rate)
    duration = num / dem
    return duration

def convexity(tranche_output, disc_rate):
    delta_y = 0.001
    num = (price(tranche_output, disc_rate - delta_y) + price(tranche_output, disc_rate + delta_y)) - (2 * price(tranche_output, disc_rate))
    dem = delta_y ** 2 * price(tranche_output, disc_rate)
    convex = num / dem
    return convex


# End of Valuation Metrics functions
pres = pv(tranche_output, disc_rate)
pric = price(tranche_output, disc_rate)
yld = yield_cal(tranche_output, market_price)
dur = duration(tranche_output, disc_rate)
conve = convexity(tranche_output, disc_rate)
wals = wal(tranche_output)
