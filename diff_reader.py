import subprocess

def get_diff(repo_path): 
    diff = subprocess.run(["git","diff","HEAD~1","HEAD"],cwd = repo_path,capture_output = True, text = True)

    return diff.stdout

if __name__ == "__main__":
    print(get_diff("sandbox_repo"))



