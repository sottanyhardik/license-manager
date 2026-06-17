# Commission Accounting - Correct Entry Guide

## Issue Fixed
Commission entries were being entered incorrectly, showing in Credit column instead of Debit column.

## ✅ CORRECT Accounting Treatment for Commissions

### For PURCHASE Transactions (Commission Paid)

**When you pay commission to an agent:**

| Account | Debit (₹) | Credit (₹) |
|---------|-----------|------------|
| Commission Paid (5303) | ₹X,XXX | - |
| Bank Account / Cash | - | ₹X,XXX |

**Explanation:**
- Commission Paid is an **EXPENSE** account
- Expenses increase with **DEBITS**
- Cash/Bank decreases with **CREDITS**

**Journal Entry:**
```
Dr. Commission Paid           ₹10,000
    Cr. Bank Account                      ₹10,000
(Being commission paid to agent)
```

---

### For SALE Transactions (Commission Received)

**When you receive commission:**

| Account | Debit (₹) | Credit (₹) |
|---------|-----------|------------|
| Bank Account / Cash | ₹X,XXX | - |
| Commission Received (4103) | - | ₹X,XXX |

**Explanation:**
- Commission Received is a **REVENUE** account
- Revenue increases with **CREDITS**
- Cash/Bank increases with **DEBITS**

**Journal Entry:**
```
Dr. Bank Account              ₹10,000
    Cr. Commission Received             ₹10,000
(Being commission received)
```

---

## 🎯 Quick Reference

### Commission PAID (Expense)
- ✅ **DEBIT** Commission Paid account
- ✅ **CREDIT** Bank/Cash account
- ❌ **DO NOT** credit Commission Paid

### Commission RECEIVED (Income)
- ✅ **CREDIT** Commission Received account
- ✅ **DEBIT** Bank/Cash account
- ❌ **DO NOT** debit Commission Received

---

## 📊 Account Codes

| Account Name | Code | Type | Normal Balance |
|--------------|------|------|----------------|
| Commission Paid | 5303 | EXPENSE | Debit |
| Commission Received | 4103 | REVENUE | Credit |

---

## 🔍 How to Enter in the System

### For Commission Paid (Most Common)

1. Go to **Journal Entries**
2. Click **Create New Entry**
3. Set Entry Type: **Manual Entry** or **Commission**
4. Add Lines:
   - **Line 1:**
     - Account: **Commission Paid (5303)**
     - **Debit Amount:** Enter the commission amount
     - Credit Amount: Leave as 0
     - Description: "Commission paid to [Agent Name]"

   - **Line 2:**
     - Account: **Bank Account** (select appropriate bank)
     - Debit Amount: Leave as 0
     - **Credit Amount:** Enter the commission amount
     - Description: "Payment of commission"

5. Verify that **Total Debit = Total Credit**
6. Save and Post

### For Commission Received

1. Go to **Journal Entries**
2. Click **Create New Entry**
3. Set Entry Type: **Manual Entry** or **Commission**
4. Add Lines:
   - **Line 1:**
     - Account: **Bank Account** (select appropriate bank)
     - **Debit Amount:** Enter the commission amount
     - Credit Amount: Leave as 0
     - Description: "Commission received from [Client Name]"

   - **Line 2:**
     - Account: **Commission Received (4103)**
     - Debit Amount: Leave as 0
     - **Credit Amount:** Enter the commission amount
     - Description: "Commission income"

5. Verify that **Total Debit = Total Credit**
6. Save and Post

---

## ❌ Common Mistakes to Avoid

### Mistake 1: Crediting Commission Paid
**Wrong:**
```
Cr. Commission Paid    ₹10,000  ❌
Dr. Bank Account       ₹10,000
```
This makes it look like you earned commission when you actually paid it!

**Correct:**
```
Dr. Commission Paid    ₹10,000  ✅
    Cr. Bank Account               ₹10,000
```

### Mistake 2: Debiting Commission Received
**Wrong:**
```
Dr. Commission Received ₹10,000  ❌
    Cr. Bank Account                 ₹10,000
```
This makes it look like you paid commission when you actually received it!

**Correct:**
```
Dr. Bank Account        ₹10,000  ✅
    Cr. Commission Received          ₹10,000
```

### Mistake 3: Using Wrong Account
**Wrong:**
```
Dr. Commission Received ₹10,000  ❌ (Using revenue account for expense)
    Cr. Bank Account                 ₹10,000
```

**Correct:**
```
Dr. Commission Paid     ₹10,000  ✅ (Using expense account for expense)
    Cr. Bank Account                 ₹10,000
```

---

## 📝 Accounting Principles Reminder

### The Golden Rules

**For Real Accounts (Assets, Liabilities):**
- Debit what comes in
- Credit what goes out

**For Personal Accounts (Debtors, Creditors):**
- Debit the receiver
- Credit the giver

**For Nominal Accounts (Expenses, Income):**
- **Debit all expenses and losses**  ← Commission Paid goes here!
- **Credit all incomes and gains**   ← Commission Received goes here!

---

## 🔄 Impact on Financial Statements

### Commission Paid (Expense)
- Appears in **Profit & Loss Statement** under Expenses
- **Reduces** your profit
- **Debit** balance in Trial Balance

### Commission Received (Revenue)
- Appears in **Profit & Loss Statement** under Income
- **Increases** your profit
- **Credit** balance in Trial Balance

---

## 💡 Pro Tips

1. **Always think: "Am I paying or receiving?"**
   - Paying = Debit Commission Paid
   - Receiving = Credit Commission Received

2. **Verify the totals balance** before posting

3. **Use descriptive narrations** including:
   - Agent/Client name
   - Related trade/invoice number
   - Date of transaction

4. **Link to related trade** if possible for better tracking

5. **Double-check the account code:**
   - 5303 for expenses
   - 4103 for income

---

## ✅ Summary

**Commission Paid (Expense):**
- **ALWAYS DEBIT** Commission Paid account
- ALWAYS CREDIT Bank/Cash account

**Commission Received (Income):**
- **ALWAYS CREDIT** Commission Received account
- ALWAYS DEBIT Bank/Cash account

**Remember:** Expenses = Debit | Income = Credit

---

## 🎓 Training Required

All users entering commission journal entries should:
1. Read this guide
2. Understand the difference between:
   - Commission Paid (Expense - DEBIT)
   - Commission Received (Income - CREDIT)
3. Practice with sample entries
4. Verify entries before posting

---

## 📞 Support

If you're unsure about how to enter a commission transaction:
1. Identify: Are you paying or receiving commission?
2. Use the templates above
3. Verify totals balance
4. Contact accounting supervisor if still unclear

**Last Updated:** 2026-03-03
