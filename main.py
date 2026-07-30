from fastapi import FastAPI
from pydantic import BaseModel

from diff_reader import get_diff
from report import build_report

app = FastAPI()


class AuditRequest(BaseModel):
    repo_path: str = "sandbox_repo"


@app.post("/audit")
def audit(request: AuditRequest):
    diff = get_diff(request.repo_path)
    return {"report": build_report(diff, repo_path=request.repo_path)}
