"""
Created on Wed Jun  3 21:57:05 2026

MBS Cash Flow Model v2 - Vectorized rewrite using NumPy and pandas (in progress)
Vectorized amortization engine complete. Aggregation, waterfall, and valuation to follow.

@author: Mauricio Rieke
"""
import numpy as np
import pandas as pd

# Read Fannie File, pipe delimited
df = pd.read_csv("fannie.txt", sep = "|", low_memory=False)

# Filter by pool ID
pool_id = "MA6053"
df = df[df["Security Identifier"] == pool_id]

# Pull the three columns and convert to numpy array
balance = df["Current Investor Loan UPB"].to_numpy()
rate = df["Current Interest Rate"].to_numpy() / 100
terms = df["Remaining Months to Maturity"].to_numpy() # In original used Loan term and in this I will be using remaining Months to Maturity


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
month_cdr = np.full((n_loans,), (annual_cdr / 12))
lag = 12
loss_sev = 0.3
psa_speed = 100

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
    smm = np.full((n_loans,),psa(month + 1, psa_speed))
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
    
pool_begbal = np.sum(beg_bal[:,:], axis=0)
pool_int = np.sum(interest_matrix[:,:], axis=0)
pool_principal = np.sum(principal_matrix[:,:], axis=0)
pool_default = np.sum(default_matrix[:,:], axis=0)
pool_prepay = np.sum(prepay_matrix[:,:], axis=0)
pool_loss = np.sum(loss_matrix[:,:], axis=0)
pool_recovery = np.sum(recovery_matrix[:,:], axis=0)
pool_endbal = np.sum(end_bal[:,:], axis=0)

'''
for i in range(12):
    print(np.round(pool_int[i], 2))
    print(np.round(pool_default[i], 2))
    print(np.round(pool_principal[i], 2))
    print(np.round(pool_prepay[i], 2)) 
'''

# iteration for waterfall tranching - run through month 


  
    