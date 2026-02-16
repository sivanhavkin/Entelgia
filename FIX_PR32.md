# Quick Fix for PR #32 Issue

## Problem
Dependabot PRs (like #32) show warnings about missing labels.

## Solution
Create the following labels in GitHub:

### Using GitHub Web UI
Go to: https://github.com/sivanhavkin/Entelgia/labels

Click "New label" and create:

1. **dependencies**
   - Description: Pull requests that update dependencies
   - Color: `#0366d6`

2. **github-actions**
   - Description: Pull requests that update GitHub Actions workflows
   - Color: `#000000`

3. **python**
   - Description: Pull requests that update Python dependencies
   - Color: `#2b67c6`

### Using GitHub CLI (fastest)
```bash
gh label create dependencies --description "Pull requests that update dependencies" --color "0366d6" --repo sivanhavkin/Entelgia
gh label create github-actions --description "Pull requests that update GitHub Actions workflows" --color "000000" --repo sivanhavkin/Entelgia
gh label create python --description "Pull requests that update Python dependencies" --color "2b67c6" --repo sivanhavkin/Entelgia
```

## More Details
See [docs/DEPENDABOT_SETUP.md](docs/DEPENDABOT_SETUP.md) for complete documentation.
