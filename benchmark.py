from diff_reader import get_diff
from report import build_report

KNOWN_BUGS = {"numbers_upto", "is_adult", "greet", "add_item"}


def run_benchmark(repo_path="sandbox_repo"):
    diff = get_diff(repo_path)
    report = build_report(diff, repo_path=repo_path)

    confirmed = [r for r in report if r["verdict"] == "confirmed bug"]
    true_positives = [r for r in confirmed if r["location"] in KNOWN_BUGS]
    false_positives = [r for r in confirmed if r["location"] not in KNOWN_BUGS]
    detected_locations = {r["location"] for r in true_positives}
    missed = KNOWN_BUGS - detected_locations

    detection_rate = len(true_positives) / len(KNOWN_BUGS)
    false_positive_rate = len(false_positives) / len(confirmed) if confirmed else 0.0

    return {
        "flagged_total": len(report),
        "confirmed_total": len(confirmed),
        "true_positives": sorted(detected_locations),
        "missed": sorted(missed),
        "false_positives": [r["location"] for r in false_positives],
        "detection_rate": detection_rate,
        "false_positive_rate": false_positive_rate,
    }


if __name__ == "__main__":
    results = run_benchmark()
    print(f"Detection accuracy: {results['detection_rate']:.0%} "
          f"({len(results['true_positives'])}/{len(KNOWN_BUGS)})")
    print(f"False positive rate: {results['false_positive_rate']:.0%} "
          f"({len(results['false_positives'])}/{results['confirmed_total']})")
    if results["missed"]:
        print(f"Missed: {results['missed']}")
