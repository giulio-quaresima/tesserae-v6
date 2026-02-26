# PR Review Procedure (Internal)

## When a Student Submits a PR

### 1. Review the Code

On the dev server, with Claude:

```
# Fetch the PR branch
git fetch origin
git checkout pr-branch-name

# Or use GitHub CLI
gh pr checkout 3
```

Ask Claude to review: "review PR #3" or paste the PR URL. Claude will read the diff and check for bugs, style issues, and potential breakage.

### 2. Test It

```
# Make sure the server is running
python3 main.py

# Run the full test suite
python3 tests/test_endpoints.py
```

All 29 tests must pass. If the student added new features, consider whether new tests are needed.

### 3. Respond

- **If it needs work:** Leave comments on the PR in GitHub. The student fixes and pushes.
- **If it passes:** Click "Merge pull request" on GitHub.

### 4. Deploy to Production

```
cd /var/www/tesseraev6_flask
git pull origin main
```

If frontend changed, the built `dist/` should already be in the PR (students should run `npm run build` before submitting). If not, build it on the server.

## Before Reviewing a Student PR

Make sure `neil-dev` is merged into `main` first, so the student's code is being tested against the latest state:

```
git checkout main
git pull origin main
git merge neil-dev
git push origin main
```

Then check out the student's branch for testing.

## Branch Strategy

- **`main`** — source of truth, always deployable, production runs from this
- **`neil-dev`** — Neil + Claude working branch, merged to main at end of sessions
- **Student branches** — branched from `main`, PRs back to `main`

## Key Rule

Students never push directly to `main`. All changes go through PRs.

## GitHub Branch Protection (Optional)

To enforce this, set up branch protection on `main`:
```
gh api repos/tesserae/tesserae-v6/branches/main/protection -X PUT \
  -f required_pull_request_reviews.required_approving_review_count=1
```

This prevents anyone from pushing directly to `main` without a reviewed PR.
