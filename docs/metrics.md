# Metrics

A record, not a dashboard. One row per measurement, newest last, with the exact
command that produced it. A number here without a command is a number somebody
remembered, which is how a project convinces itself it is growing.

The rule this file exists to enforce: **no claim about progress without a
measurement that someone else can repeat.**

## How to measure

```sh
gh api repos/lyear12/citevouch \
  --jq '{stars:.stargazers_count,forks:.forks_count,watchers:.subscribers_count,issues:.open_issues_count}'

gh api repos/lyear12/citevouch/releases \
  --jq '.[] | "\(.tag_name) " + ([.assets[] | "\(.name):\(.download_count)"] | join(","))'

curl -s -o /dev/null -w '%{http_code}\n' https://pypi.org/pypi/citevouch/json
```

## What counts, and what does not

- **Stars** — a bookmark, not a user. Useful as direction; useless as proof.
- **Release downloads** — the closest thing to "somebody installed it". Every
  download by the release workflow itself is a false positive, and this project
  publishes a lot, so treat single-digit counts as noise.
- **Open issues** — the only metric that means the tool reached someone's
  actual work. One real issue outweighs a hundred stars.
- **PyPI 404** — the single biggest blocker. Until this is a 200,
  `pip install citevouch` fails and every other number is capped.

## Log

| date | stars | forks | watchers | open issues | release downloads | PyPI | note |
|---|---|---|---|---|---|---|---|
| 2026-10-30 | 0 | 0 | 0 | 0 | 6 (across 16 releases) | 404 | first 16 releases shipped in ~2 days, all automated |

Nothing above is growth. At this size the honest read is: **nobody has used it
yet**, and the numbers that matter (issues, downloads) are the ones that will
move first when somebody does.

## What would make me change course

Written down in advance, so the decision is not made by whoever is most tired
that day:

- **30 days, still zero downloads and zero issues** → the gap is not
  discoverability, it is that the problem is not painful. Stop adding
  capabilities; find one person with a real manuscript and watch them use it.
- **Issues arrive but all say "I could not start"** → the gap is onboarding.
  `doctor` and `draft` move to P0 and nothing else ships until the first-run
  path is clean.
- **Downloads but no issues** → the tool works and nobody needs it. That is a
  positioning answer, not an engineering one, and no amount of code fixes it.

## Deliberately not tracked

- Commits per day, lines of code, number of tests. They move when nothing
  happens and they reward the wrong behaviour — the 30-minute loop could triple
  all three without anyone being able to use the tool.
