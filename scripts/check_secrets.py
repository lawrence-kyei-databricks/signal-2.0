"""Fail if the working tree contains anything that looks like a credential.

Run before every commit:  python scripts/check_secrets.py
Exit code 1 lists the offending files and line numbers (values are never printed).
"""
import os, re, sys

PATTERNS = {
    "Databricks PAT": re.compile(r"\bdapi[0-9a-f]{32}\b"),
    "Salesforce consumer key": re.compile(r"\b3MVG9[A-Za-z0-9._]{40,}"),
    "Bearer token literal": re.compile(r"Bearer\s+[A-Za-z0-9._\-]{40,}"),
    "Password assignment": re.compile(r"(?i)(password|passwd|security_token|client_secret)\s*=\s*[\'\"][^\'\"\s]{6,}[\'\"]"),
    "Private key": re.compile(r"-----BEGIN (RSA |EC )?PRIVATE KEY-----"),
}
SKIP_DIRS = {".git", "__pycache__", ".ipynb_checkpoints"}

def main(root="."):
    hits = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            path = os.path.join(dirpath, name)
            try:
                lines = open(path, encoding="utf-8").read().splitlines()
            except (UnicodeDecodeError, OSError):
                continue
            for i, line in enumerate(lines, 1):
                for label, pat in PATTERNS.items():
                    if pat.search(line):
                        hits.append(f"{path}:{i}  {label}")
    if hits:
        print("Possible secrets found (values not shown):")
        print("\n".join(hits))
        return 1
    print("No secrets found")
    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "."))
