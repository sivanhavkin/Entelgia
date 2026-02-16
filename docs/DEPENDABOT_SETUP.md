# Dependabot Setup Guide

## Issue with PR #32

PR #32 was a Dependabot pull request that updated `actions/upload-artifact` from v4 to v6. While the PR was successfully merged, Dependabot reported a warning:

```
### Labels

The following labels could not be found: `dependencies`, `github-actions`. 
Please create them before Dependabot can add them to a pull request.

Please fix the above issues or remove invalid values from `dependabot.yml`.
```

## Root Cause

The Dependabot configuration file (`.github/dependabot.yml`) references labels that don't exist in the repository:
- `dependencies` - Used for both Python and GitHub Actions updates
- `github-actions` - Used specifically for GitHub Actions updates
- `python` - Used specifically for Python package updates

## Solution

Create the missing labels in the GitHub repository. This can be done in several ways:

### Option 1: Using GitHub Web UI

1. Navigate to the repository on GitHub
2. Go to **Issues** → **Labels** (or directly to `https://github.com/sivanhavkin/Entelgia/labels`)
3. Click **New label** for each missing label:

   **Label: dependencies**
   - Name: `dependencies`
   - Description: `Pull requests that update dependencies`
   - Color: `#0366d6` (blue)

   **Label: github-actions**
   - Name: `github-actions`
   - Description: `Pull requests that update GitHub Actions workflows`
   - Color: `#000000` (black)

   **Label: python**
   - Name: `python`
   - Description: `Pull requests that update Python dependencies`
   - Color: `#2b67c6` (blue)

### Option 2: Using GitHub CLI

If you have the GitHub CLI (`gh`) installed and authenticated:

```bash
# Create dependencies label
gh label create dependencies \
  --description "Pull requests that update dependencies" \
  --color "0366d6" \
  --repo sivanhavkin/Entelgia

# Create github-actions label
gh label create github-actions \
  --description "Pull requests that update GitHub Actions workflows" \
  --color "000000" \
  --repo sivanhavkin/Entelgia

# Create python label
gh label create python \
  --description "Pull requests that update Python dependencies" \
  --color "2b67c6" \
  --repo sivanhavkin/Entelgia
```

### Option 3: Using GitHub API

You can also create labels using curl with the GitHub API:

```bash
# Set your GitHub token
GITHUB_TOKEN="your_token_here"
REPO="sivanhavkin/Entelgia"

# Create dependencies label
curl -X POST \
  -H "Authorization: token $GITHUB_TOKEN" \
  -H "Accept: application/vnd.github.v3+json" \
  https://api.github.com/repos/$REPO/labels \
  -d '{"name":"dependencies","description":"Pull requests that update dependencies","color":"0366d6"}'

# Create github-actions label
curl -X POST \
  -H "Authorization: token $GITHUB_TOKEN" \
  -H "Accept: application/vnd.github.v3+json" \
  https://api.github.com/repos/$REPO/labels \
  -d '{"name":"github-actions","description":"Pull requests that update GitHub Actions workflows","color":"000000"}'

# Create python label
curl -X POST \
  -H "Authorization: token $GITHUB_TOKEN" \
  -H "Accept: application/vnd.github.v3+json" \
  https://api.github.com/repos/$REPO/labels \
  -d '{"name":"python","description":"Pull requests that update Python dependencies","color":"2b67c6"}'
```

## Verification

After creating the labels:

1. Visit `https://github.com/sivanhavkin/Entelgia/labels` to verify all labels exist
2. Future Dependabot PRs will automatically have these labels applied
3. No more warnings will appear in Dependabot PR comments

## Dependabot Configuration

The current Dependabot configuration (`.github/dependabot.yml`) is set up as follows:

- **Python dependencies**: Checks weekly on Mondays, applies `dependencies` and `python` labels
- **GitHub Actions**: Checks weekly on Mondays, applies `dependencies` and `github-actions` labels

This configuration is optimal and doesn't need to be changed. Only the labels need to be created.

## Future PRs

Once the labels are created, all future Dependabot PRs will:
- Be properly labeled for easy filtering and organization
- Not show any warnings about missing labels
- Follow the same commit message conventions (prefixed with `chore:` for Python, `ci:` for Actions)
