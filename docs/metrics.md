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
| 2026-10-30 | 0 | 0 | 0 | 0 | 6 (across 18 releases) | 404 | README now opens with two generated figures; v0.16.0 |
| 2026-10-30 | 0 | 0 | 0 | 0 | 57 (across 26 releases) | 404 | v0.16.3; the count rose 9x in 90 minutes, which is not 9x the users |
| 2026-10-30 | 0 | 0 | 0 | 0 | 68 (across 30 releases) | 404 | v0.17.1; 11 downloads in 30 releases is still the automated-checkup shape, not a user |

A note on the image check, because it is the kind of thing this file is for: the
README's images were verified as *markup* (`gh api repos/lyear12/citevouch/readme
-H "Accept: application/vnd.github.html+json"` returns both `<img>` tags with the
right `src` and `alt`, and `repos/.../contents/docs/img` lists all four files at
the referenced path), but not as *pixels* — this machine cannot reach
`raw.githubusercontent.com`, so the browser reports `naturalWidth 0` for both.
That is a fact about this machine, not about the page, and it stays unresolved
until someone opens the repository from a network that can reach the CDN.

The download count is worth reading carefully, because it looks like the one
number that moved. It went from 6 to 57 between two measurements 90 minutes
apart, across 26 releases - about 2.2 downloads per release, spread evenly over
every artifact. That is the shape of automated fetching, not of people: this
session downloaded wheels and sdists by hand to check a clean install, to run
the archive's own suite, and to test the nightly job. A real user arrives at one
release, not at all of them. Until the counts cluster on one or two versions
instead of dusting every one, they measure my own verification, and this file
should say so rather than quote the bigger number.

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
