# Commands

```powershell
make verify-fast
make verify-full
make pr-ready TITLE="<PR标题>"
make pr-diagnose PR=<PR号>
make pr-resolve-threads THREADS="<thread-id> [<thread-id>...]"
make pr-complete TITLE="<PR标题>"
make pr-merge PR=<PR号>
make pr-cleanup PR=<PR号>
make ai-review
make risk-check
.\.venv\Scripts\python.exe -m scripts.research.governance verify full
.\.venv\Scripts\python.exe -m scripts.research.governance.pr_flow resolve-threads <thread-id> [<thread-id>...]
.\.venv\Scripts\python.exe -m scripts.research.governance.pr_flow complete --title "<PR标题>" --pr <PR号>
```
