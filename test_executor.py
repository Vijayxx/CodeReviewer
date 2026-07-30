import subprocess


def run_test(test_code, repo_path="sandbox_repo", test_filename="test_generated.py"):
    test_path = f"{repo_path}/{test_filename}"
    with open(test_path, "w") as f:
        f.write(test_code)

    result = subprocess.run(
        ["python3", "-m", "pytest", test_filename, "-v"],
        cwd=repo_path,
        capture_output=True,
        text=True,
    )

    return {
        "passed": result.returncode == 0,
        "output": result.stdout + result.stderr,
    }
