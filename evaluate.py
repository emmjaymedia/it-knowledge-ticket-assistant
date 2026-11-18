"""Evaluate top citation and abstention against synthetic labeled questions."""
import json
import math
import statistics
import time
from pathlib import Path

from engine import answer


def evaluate():
    cases = json.loads(Path(__file__).with_name("eval_cases.json").read_text())
    results = {}
    for strategy in ("keyword", "vector"):
        passed, times, failures = 0, [], []
        for question, role, expected in cases:
            start = time.perf_counter()
            result = answer(question, role, strategy, use_model=False)
            times.append((time.perf_counter() - start) * 1000)
            actual = (result["citation"] or {}).get("id")
            passed += actual == expected
            if actual != expected:
                failures.append({"question": question, "expected": expected, "actual": actual})
        results[strategy] = {
            "passed": passed, "total": len(cases),
            "median_ms": round(statistics.median(times), 3),
            "p95_ms": round(sorted(times)[math.ceil(.95 * len(times)) - 1], 3),
            "failures": failures,
        }
    return results


if __name__ == "__main__":
    print(json.dumps(evaluate(), indent=2))
