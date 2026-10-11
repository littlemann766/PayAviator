# PayAviator Connected Accounts Foundation

## Product rule
PayAviator remains read-only first. The goal is to turn real account activity into a trustworthy **Safe to Spend** number, not to move money.

## Data flow
PayAviator app → secure PayAviator backend → Plaid → financial institution.

## Build sequence
1. Connected Accounts UI and local account/transaction data contract.
2. Plaid Sandbox backend and Link flow.
3. Import balances and transactions.
4. Reconcile imported transactions with manual Spending/Bills.
5. Detect recurring income and obligations with user confirmation.
6. Feed verified data into the PayAviator Gauge.
7. Add authentication/encrypted storage and production hardening before live users.
