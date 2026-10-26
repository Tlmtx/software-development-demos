Order CSV cleanup and reporting

Self-initiated portfolio demonstration. AI-assisted implementation. The input
records are synthetic and this is not a paid client project.

Run with Python 3.10 or newer. No third-party packages are required.
  python3 clean_orders.py sample_orders.csv --output output

Multiple files may be supplied after the script name. They are processed in
filename order. Input columns must be order_id,date,store,sku,quantity,unit_price.

Outputs:
  cleaned_orders.csv: accepted records, amounts and source locations
  exceptions.csv: excluded records and reasons
  summary.json: row counts and accepted-record total

Exact duplicates are removed. When an order ID has conflicting values, the
first valid record is retained and the later record is excluded and explicitly
flagged for review. No conflicting value is silently overwritten. Missing or
invalid required values are excluded. Prices use decimal arithmetic. Formula-
like CSV text is escaped to reduce spreadsheet formula injection risks.

The summary total includes the retained first record for a conflicting ID;
conflicts must be reviewed before using the output as a final business report.

Verification:
  python3 -m unittest -v
