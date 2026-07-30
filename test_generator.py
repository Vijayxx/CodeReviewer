from gemini_client import call_gemini

def generate_test(issue,diff_text):
    prompt = f"""You are an experienced tester.
    This is the diff from the two previous versions of the branch - {diff_text}
    and here are the actual specified flagged issues - function at {issue['location']},problem: {issue['description']}
    write exactly one pytest function that imports that function directly from bugs import <function_name>, no package prefix,
    the test must fail if the described is genuinely present, and would pass if the code were correct.
    Respond with only the raw Python code for the test function — no markdown fences, no explanation"""

    return call_gemini(prompt)

if __name__ == "__main__":
    from diff_reader import get_diff
    from flagger import flag_issues

    diff = get_diff("sandbox_repo")
    issues = flag_issues(diff)
    print(generate_test(issues[0], diff))