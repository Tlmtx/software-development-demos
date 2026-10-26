"""Validate and combine order CSVs without silently choosing conflicting records."""
import argparse
import csv
from datetime import date
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path

FIELDS = ["order_id", "date", "store", "sku", "quantity", "unit_price"]


def clean(paths):
    records, issues, seen = [], [], {}
    counters = {"input_rows": 0, "valid_rows": 0, "duplicates_removed": 0, "rejected_rows": 0}
    for path in sorted(map(Path, paths)):
        with path.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames != FIELDS:
                raise ValueError(f"{path.name}: expected columns {FIELDS}")
            for line, row in enumerate(reader, 2):
                counters["input_rows"] += 1
                cleaned = {key: (row.get(key) or "").strip() for key in FIELDS}
                reason = None
                try:
                    if not all(cleaned[key] for key in FIELDS):
                        raise ValueError("Missing required value")
                    cleaned["date"] = date.fromisoformat(cleaned["date"]).isoformat()
                    quantity = int(cleaned["quantity"])
                    price = Decimal(cleaned["unit_price"])
                    if quantity <= 0 or not price.is_finite() or price < 0:
                        raise ValueError("Quantity must be positive; price must be finite and nonnegative")
                    if price != price.quantize(Decimal("0.01")):
                        raise ValueError("Unit price must have at most two decimal places")
                    cleaned["quantity"] = quantity
                    cleaned["unit_price"] = str(price.quantize(Decimal("0.01")))
                except (ValueError, InvalidOperation):
                    reason = "Invalid or missing required value"
                if reason:
                    counters["rejected_rows"] += 1
                elif cleaned["order_id"] in seen:
                    if cleaned == seen[cleaned["order_id"]]:
                        counters["duplicates_removed"] += 1
                        reason = "Exact duplicate removed"
                    else:
                        counters["rejected_rows"] += 1
                        reason = "Conflicting order ID: later record excluded; review retained original"
                else:
                    seen[cleaned["order_id"]] = cleaned.copy()
                    amount = Decimal(cleaned["unit_price"]) * cleaned["quantity"]
                    records.append({**cleaned, "amount": str(amount), "source_file": path.name, "source_line": line})
                    counters["valid_rows"] += 1
                if reason:
                    issues.append({"source_file": path.name, "source_line": line, "order_id": cleaned["order_id"], "reason": reason, "raw_record": json.dumps(row, ensure_ascii=False)})
    counters["total_amount"] = str(sum((Decimal(row["amount"]) for row in records), Decimal("0.00")))
    return records, issues, counters


def spreadsheet_safe(value):
    # Keep untrusted text from being interpreted as a spreadsheet formula.
    if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


def write_csv(path, rows, fields):
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows({key: spreadsheet_safe(row[key]) for key in fields} for row in rows)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inputs", nargs="+", type=Path)
    parser.add_argument("--output", type=Path, default=Path("output"))
    args = parser.parse_args()
    records, issues, summary = clean(args.inputs)
    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "cleaned_orders.csv", records, FIELDS + ["amount", "source_file", "source_line"])
    write_csv(args.output / "exceptions.csv", issues, ["source_file", "source_line", "order_id", "reason", "raw_record"])
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
