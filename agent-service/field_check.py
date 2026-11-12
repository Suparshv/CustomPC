import json
from pathlib import Path
import pandas as pd

raw_dir = Path("agent-service/data/raw")
files = [
    "cpu.json",
    "motherboard.json",
    "video-card.json",
    "memory.json",
    "internal-hard-drive.json",
    "power-supply.json",
    "case.json",
    "cpu-cooler.json",
]

report_lines = [
    "# Dataset Field Check & Completeness Report",
    "",
    "> Generated on 2026-11-12 from docyx/pc-part-dataset (MIT License, July 2025 scrape).",
    "",
    "## 1. Summary of Categories & Price Availability",
    "",
    "| Category File | Total Parts | Priced Parts | % with Price | Total Fields |",
    "|---|---|---|---|---|",
]

total_all = 0
total_priced = 0
category_details = []

def is_non_empty(val):
    if val is None:
        return False
    if isinstance(val, (list, tuple, dict, str)):
        return len(val) > 0
    try:
        if pd.isna(val):
            return False
    except Exception:
        pass
    return True

for filename in files:
    path = raw_dir / filename
    if not path.exists():
        continue
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    df = pd.DataFrame(data)
    total_count = len(df)
    total_all += total_count

    # Check for price field
    has_price = False
    priced_count = 0
    if "price" in df.columns:
        has_price = True
        priced_df = df[df["price"].notna() & (df["price"] > 0)]
        priced_count = len(priced_df)
        total_priced += priced_count

    pct_priced = (priced_count / total_count * 100) if total_count > 0 else 0
    report_lines.append(
        f"| `{filename}` | {total_count:,} | {priced_count:,} | {pct_priced:.1f}% | {len(df.columns)} |"
    )

    # Calculate non-null percentage per field
    field_stats = []
    for col in df.columns:
        non_empty_cnt = df[col].apply(is_non_empty).sum()
        pct = (non_empty_cnt / total_count * 100) if total_count > 0 else 0
        field_stats.append((col, int(non_empty_cnt), pct))

    # Sort field stats by descending completeness
    field_stats.sort(key=lambda x: x[2], reverse=True)
    category_details.append((filename, total_count, priced_count, field_stats, list(df.columns)))

report_lines.append(
    f"| **Total (8 Categories)** | **{total_all:,}** | **{total_priced:,}** | **{(total_priced / total_all * 100):.1f}%** | - |"
)
report_lines.append("")
report_lines.append("---")
report_lines.append("")
report_lines.append("## 2. Field-by-Field Completeness Analysis")
report_lines.append("")

for filename, total_cnt, pr_cnt, stats, cols in category_details:
    cat_name = filename.replace(".json", "")
    report_lines.append(f"### `{filename}` ({cat_name})")
    report_lines.append(f"- **Total Rows:** {total_cnt:,}")
    report_lines.append(f"- **Rows with Valid Price:** {pr_cnt:,} ({(pr_cnt/total_cnt*100):.1f}%)")
    report_lines.append("")
    report_lines.append("| Field Name | Non-Empty Count | Completeness % | Notes / Ingestion Feasibility |")
    report_lines.append("|---|---|---|---|")
    for col, count, pct in stats:
        note = "Complete" if pct > 99 else ("Partially available" if pct > 50 else "Sparse")
        if col == "price":
            note = "**Required filter:** unpriced parts are excluded"
        elif col in ("name", "model"):
            note = "Key component identifier"
        report_lines.append(f"| `{col}` | {count:,} | {pct:.1f}% | {note} |")
    report_lines.append("")

report_lines.append("---")
report_lines.append("")
report_lines.append("## 3. Compatibility Field Gaps & Ingestion Strategy")
report_lines.append("")
report_lines.append("The raw dataset is missing several critical hardware compatibility attributes required for physical checks. These are derived or handled as follows:")
report_lines.append("")
report_lines.append("1. **CPU Socket Missing:**")
report_lines.append("   - `cpu.json` contains `name` and `microarchitecture` but no direct `socket` field.")
report_lines.append("   - *Strategy:* Derive socket from name and microarchitecture: Ryzen 3000-5000 -> AM4; Ryzen 7000-9000 -> AM5; Intel 12th-14th Gen -> LGA1700; Core Ultra (Arrow Lake) -> LGA1851.")
report_lines.append("")
report_lines.append("2. **Motherboard RAM Generation Missing:**")
report_lines.append("   - `motherboard.json` specifies socket and form factor, but RAM type (DDR4 vs DDR5) is not an explicit column.")
report_lines.append("   - *Strategy:* Derive from socket: AM5 and LGA1851 are exclusively DDR5; AM4 is DDR4. For LGA1700 boards, inspect the name for 'DDR4' or 'D4' (DDR4) or qualify verified DDR5 boards. Non-conforming LGA1700 boards are excluded.")
report_lines.append("")
report_lines.append("3. **GPU Wattage / TDP:**")
report_lines.append("   - `video-card.json` contains chipset, memory, and length, but power consumption is omitted.")
report_lines.append("   - *Strategy:* Use default TDP tables by chipset family on Day 7.")
report_lines.append("")
report_lines.append("4. **Case Clearance & Cooler Height:**")
report_lines.append("   - GPU maximum length clearance and cooler height clearance are sparsely populated across cases.")
report_lines.append("   - *Strategy:* Curate standard clearance thresholds on Day 7.")
report_lines.append("")
report_lines.append("5. **Stock Availability:**")
report_lines.append("   - Scraped PCPartPicker data has no inventory status.")
report_lines.append("   - *Strategy:* Deterministically simulate ~92% in-stock based on a hash of the part ID, clearly marked `in_stock: true/false` and `stock_simulated: true`.")

output_path = Path("docs/dataset-field-check.md")
output_path.parent.mkdir(parents=True, exist_ok=True)
with open(output_path, "w", encoding="utf-8") as f:
    f.write("\n".join(report_lines) + "\n")

print(f"Report written to: {output_path}")
print(f"Total parts analyzed: {total_all:,}, Priced parts: {total_priced:,}")
