# Validate Transactions

Validate all transactions in `sample-transactions.json` without running the full pipeline.

## Steps

1. **Check prerequisites**
   - Verify `sample-transactions.json` exists in the project root.
   - Verify `agents/transaction_validator.py` exists.
   - If either is missing, report the error and stop.

2. **Run validator in dry-run mode**
   - Execute: `python agents/transaction_validator.py --dry-run`
   - Capture and display the full output.

3. **Report summary statistics**
   Display:
   - Total transaction count
   - Valid count (status = validated)
   - Invalid count (status = rejected)
   - List of rejection reasons with frequency

4. **Display results table**
   Show a formatted table with columns:
   | TXN ID | Status | Currency | Amount | Rejection Reason |
   |--------|--------|----------|--------|-----------------|

   For each of the 8 transactions, fill in the relevant data.
   Mark rejected rows clearly (e.g. ❌ REJECTED).

5. **Highlight key findings**
   - Which transactions were rejected and why.
   - Any currency validation failures.
   - Any amount validation failures.
