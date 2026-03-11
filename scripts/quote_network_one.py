#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.network_one_pricing import build_default_quote


def parse_args():
    parser = argparse.ArgumentParser(description="Generate Network One episode quote from JSON payload.")
    parser.add_argument("--input", required=True, help="Path to quote input JSON.")
    parser.add_argument("--output", required=False, help="Optional output path for quote JSON.")
    return parser.parse_args()


def main():
    args = parse_args()
    input_path = Path(args.input)
    payload = json.loads(input_path.read_text(encoding="utf-8"))
    _, quote = build_default_quote(payload)

    result = {
        "patient_id": quote.patient_id,
        "payer_type": quote.payer_type,
        "complexity_score": quote.complexity_score,
        "complexity_tier": quote.complexity_tier,
        "base_price_zar": quote.base_price_zar,
        "risk_adjusted_price_zar": quote.risk_adjusted_price_zar,
        "final_price_zar": quote.final_price_zar,
        "clinical_bucket_amounts": quote.clinical_bucket_amounts,
        "installment_amounts": quote.installment_amounts,
        "rationale": quote.rationale,
    }

    output = json.dumps(result, indent=2)
    if args.output:
        Path(args.output).write_text(output + "\n", encoding="utf-8")
    else:
        print(output)


if __name__ == "__main__":
    main()
