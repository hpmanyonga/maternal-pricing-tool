import json
from pathlib import Path
from typing import Dict, Iterable, List, Set, Tuple


DEFAULT_RULES_PATH = Path(__file__).resolve().parent.parent / "data" / "network_one_icd10_rules.json"


def load_icd10_rules(path: str = None) -> Dict:
    rules_path = Path(path) if path else DEFAULT_RULES_PATH
    with rules_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def infer_indicators_from_icd10(
    codes: Iterable[str] = None,
    descriptions: Iterable[str] = None,
    rules: Dict = None,
) -> Tuple[Set[str], List[str]]:
    codes = list(codes or [])
    descriptions = list(descriptions or [])
    rules = rules or load_icd10_rules()

    matched_indicators: Set[str] = set()
    trace: List[str] = []

    code_rules = rules.get("code_prefix_rules", {})
    for code in codes:
        normalized = str(code).strip().upper()
        if not normalized:
            continue
        for prefix, indicator in code_rules.items():
            if normalized.startswith(prefix):
                matched_indicators.add(indicator)
                trace.append(f"code:{normalized}->{indicator}")

    keyword_rules = rules.get("description_keyword_rules", {})
    for text in descriptions:
        normalized = str(text).strip().lower()
        if not normalized:
            continue
        for keyword, indicator in keyword_rules.items():
            if keyword.lower() in normalized:
                matched_indicators.add(indicator)
                trace.append(f"desc:{keyword}->{indicator}")

    return matched_indicators, trace


def explain_icd10_matches(
    codes: Iterable[str] = None,
    descriptions: Iterable[str] = None,
    rules: Dict = None,
) -> Dict:
    codes = list(codes or [])
    descriptions = list(descriptions or [])
    rules = rules or load_icd10_rules()

    code_rules = rules.get("code_prefix_rules", {})
    keyword_rules = rules.get("description_keyword_rules", {})

    code_matches = []
    for code in codes:
        normalized = str(code).strip().upper()
        if not normalized:
            continue
        indicators = sorted(
            {indicator for prefix, indicator in code_rules.items() if normalized.startswith(prefix)}
        )
        code_matches.append(
            {
                "code": normalized,
                "matched_indicators": indicators,
            }
        )

    description_matches = []
    for text in descriptions:
        normalized = str(text).strip()
        if not normalized:
            continue
        lowered = normalized.lower()
        keywords_hit = sorted(
            [keyword for keyword in keyword_rules.keys() if keyword.lower() in lowered]
        )
        indicators = sorted({keyword_rules[k] for k in keywords_hit})
        description_matches.append(
            {
                "description": normalized,
                "matched_keywords": keywords_hit,
                "matched_indicators": indicators,
            }
        )

    inferred_indicators, trace = infer_indicators_from_icd10(
        codes=codes,
        descriptions=descriptions,
        rules=rules,
    )

    return {
        "code_matches": code_matches,
        "description_matches": description_matches,
        "inferred_indicators": sorted(inferred_indicators),
        "trace": trace,
    }
