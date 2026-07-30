import json

from gemini_client import call_gemini

def flag_issues(diff_text):
    prompt =  f"""I want you to act as a very critical code reviewer, 
    you are going to inspect a diff for bugs 
    and from the diff identify what could actually be a bug 
    and what could've been an intentional change and flag the bugs
    The kinds of bugs to look out for are as follows(but not limited to): 
    logic errors like off-by-one mistakes, wrong comparisons, unhandled None, mutable defaults, etc.
    Your entire response will be passed directly to a JSON parser — any text outside the JSON array, including markdown fences or commentary, will cause it to crash. 
    - each object has exactly two keys : location(the function name) and description(what's wrong)
    Example output: [{{"location": "function_name", "description": "explanation of the bug"}}]
    - If you find no issues, respond with an empty array: []
    the diff text - {diff_text}"""

    return json.loads(call_gemini(prompt))

if __name__ == "__main__":
    from diff_reader import get_diff
    print(flag_issues(get_diff("sandbox_repo")))