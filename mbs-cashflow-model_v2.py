"""
Created on Wed Jun  3 21:57:05 2026

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
terms = df["Remaining Months to Maturity"].to_numpy()


# Payment function
def pmt_loan(balance, annual_rate, term_month):
    freq_rate = annual_rate / 12
    pmt = (freq_rate * balance) / (1 - (1 + freq_rate) ** -term_month)
    return pmt


n_loans = len(balance)
n_month = terms.max()
annual_cdr = 0.005
month_cdr = np.full((n_loans,), (annual_cdr / 12))
psa = 1 - (1 - 0.06)** (1 / 12)
smm = np.full((n_loans,), psa)
lag = 12
loss_sev = 0.3

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
    
    

