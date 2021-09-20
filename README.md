# github-pr-summary

Creates a summary of GitHub pull requests of specified users in specified repositories.

## Usage

You need the [GitHub CLI](https://cli.github.com/) installed and authenticated.

Usage:
```bash
python3 main.py \
  --repos "my-organization/my-repo" \
  --users ivanyu "other-guy" > index.html
```

Open `index.html` in a browser.

You can also schedule this with cron or other tool.
