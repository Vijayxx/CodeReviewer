#!/bin/bash
# Rebuilds sandbox_repo/ — a nested git repo with 4 deliberately planted bugs,
# used as the known-answer benchmark fixture for M1/M7.
set -e

rm -rf sandbox_repo
mkdir sandbox_repo
cd sandbox_repo
git init -q

cat > bugs.py << 'EOF'
def numbers_upto(n):
    return list(range(1,n+1))

def is_adult(age):
    return age >= 18

def greet(name = None):
    if name is None:
         return "Hello, there!"
    else:
        return f"Hello, {name}!"

def add_item(item,items = None):
    if items is None:
        items = []
    items.append(item)
    return items
EOF

git add bugs.py
git commit -q -m "correct baseline"

cat > bugs.py << 'EOF'
def numbers_upto(n):
    return list(range(1,n))

def is_adult(age):
    return age > 18

def greet(name = None):
    return f"Hello, {name.upper()}!"

def add_item(item,items = []):
    if items is None:
        items = []
    items.append(item)
    return items
EOF

git add bugs.py
git commit -q -m "simplify boundary checks and defaults"

# Untracked on purpose — keeps test_generated*.py out of `git status` noise
# without appearing in the HEAD~1..HEAD diff that M1 reads.
cat > .gitignore << 'EOF'
test_generated*.py
__pycache__/
.pytest_cache/
EOF

echo "sandbox_repo rebuilt: 2 commits, 4 planted bugs (numbers_upto, is_adult, greet, add_item)"
