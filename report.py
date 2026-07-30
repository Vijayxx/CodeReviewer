from flagger import flag_issues
from test_generator import generate_test
from test_executor import run_test


def build_report(diff_text, repo_path="sandbox_repo"):
    issues = flag_issues(diff_text)
    report = []

    for i, issue in enumerate(issues):
        test_code = generate_test(issue, diff_text)
        result = run_test(test_code, repo_path=repo_path, test_filename=f"test_generated_{i}.py")
        verdict = "confirmed bug" if not result["passed"] else "false positive"

        report.append({
            "location": issue["location"],
            "description": issue["description"],
            "test_code": test_code,
            "test_passed": result["passed"],
            "test_output": result["output"],
            "verdict": verdict,
        })

    return report


if __name__ == "__main__":
    from diff_reader import get_diff

    diff = get_diff("sandbox_repo")
    for entry in build_report(diff):
        print(f"{entry['location']}: {entry['verdict']}")
