# Metrics

A record, not a dashboard. One row per measurement, newest last, with the exact
command that produced it. A number here without a command is a number somebody
remembered, which is how a project convinces itself it is growing.

The rule this file exists to enforce: **no claim about progress without a
measurement that someone else can repeat.**

## How to measure

```sh
# Bookmarks and counts. Cheap, and the only numbers here that update themselves.
gh api repos/lyear12/citevouch \
  --jq '{stars:.stargazers_count,forks:.forks_count,watchers:.subscribers_count,issues:.open_issues_count}'

# How many releases, and how many bytes have been fetched from them.
#
# `per_page` is not optional. Without it GitHub returns thirty releases, so the
# totals below are silently a slice: measured 2026-11-15, the bare call reported
# 30 releases and 83 downloads, while the paginated one reported 255 and 732.
# A measurement that truncates is worse than no measurement, because it still
# looks like one - and the shape of the mistake is "the number stopped moving",
# which is exactly the signal this file exists to read.
gh api "repos/lyear12/citevouch/releases?per_page=100" --paginate --jq '.[].tag_name' | wc -l

gh api "repos/lyear12/citevouch/releases?per_page=100" --paginate \
  --jq '.[].assets[].download_count' | awk '{s+=$1} END {print s+0}'

curl -s -o /dev/null -w '%{http_code}\n' https://pypi.org/pypi/citevouch/json
```

## What counts, and what does not

The distinction that matters is not big numbers versus small ones. It is **whose behaviour produced
the number**: automation this project runs, or a person who arrived.

| signal | what it can support | what it cannot |
|---|---|---|
| **Stars** | someone saw the page and bookmarked it | that anything was installed or run |
| **Release downloads** | bytes left GitHub's servers | that a person asked for them. The nightly fetches the newest wheel daily, and this session fetches releases to check clean installs, the archive's own suite and the published record. A count that rises with the number of releases, spread evenly across all of them, is automation; a person arrives at one release and stays there. |
| **Open issues** | a person ran the tool on their own work and something went wrong | nothing at all when it reads zero — see below |
| **PyPI 404** | `pip install citevouch` does not work, so the funnel stops at the README | — |

So: **zero issues is not evidence that nobody uses it, and it is certainly not evidence that it
works.** It means no external user has reported anything. Likewise a download count is not evidence
of users, because this project's own automation is indistinguishable from a person at this
granularity. What would be evidence is a download that clusters on one version, or an issue quoting
an error the reporter could only have got by running it.

**PyPI 404** remains the largest engineering-adjacent blocker: until that is a 200, the documented
install line fails, and every other number is capped by a funnel that ends in a 404.

## Log

| date | stars | forks | watchers | open issues | release downloads | PyPI | note |
|---|---|---|---|---|---|---|---|
| 2026-10-30 | 0 | 0 | 0 | 0 | 6 (across 16 releases) | 404 | first 16 releases shipped in ~2 days, all automated |
| 2026-10-30 | 0 | 0 | 0 | 0 | 6 (across 18 releases) | 404 | README now opens with two generated figures; v0.16.0 |
| 2026-10-30 | 0 | 0 | 0 | 0 | 57 (across 26 releases) | 404 | v0.16.3; the count rose 9x in 90 minutes, which is not 9x the users |
| 2026-10-30 | 0 | 0 | 0 | 0 | 68 (across 30 releases) | 404 | v0.17.1; 11 downloads in 30 releases is still the automated-checkup shape, not a user |
| 2026-10-31 | 0 | 0 | 0 | 0 | 90 (across 40 releases) | 404 | v0.18.9; 22 downloads over 10 releases in four hours, all of them mine |
| 2026-10-31 | 0 | 0 | 0 | 0 | 99 (across 45 releases) | 404 | v0.19.3; five releases in the five hours since, still ~2 per release |
| 2026-10-31 | 0 | 0 | 0 | 0 | 111 (across 51 releases) | 404 | v0.19.9; 12 downloads over 6 releases - the automated-checkup shape, still no outside user |
| 2026-11-15 | 0 | 0 | 0 | 0 | 732 (across 255 releases) | 404 | v0.26.0; 2.9 downloads per release, evenly spread - still the automated shape, now measured with a command that does not stop at thirty releases |

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

Nothing above is growth, and the honest read is narrower than "nobody uses it": **there is no
evidence that anybody outside this project has run it**, and the two numbers that would move first
are the two that have not moved at all. The 2026-11-15 row is the same shape at a larger scale —
2.9 downloads per release across 255 releases, dusted evenly over all of them, which is what
automation looks like and not what a person looks like.

## What would make me change course

Written down in advance, so the decision is not made by whoever is most tired that day. Each row
keeps the trigger it always had, and states what the trigger can actually support:

| trigger | what it supports | what it does not support | next move |
|---|---|---|---|
| **30 days, still zero downloads and zero issues** | nobody outside has arrived | that the problem is not painful — a tool nobody can install cannot demonstrate pain either way | stop adding capabilities; find one person with a real manuscript and watch them use it |
| **Issues arrive but all say "I could not start"** | the gap is onboarding | — | `doctor` and `draft` move to P0 and nothing else ships until the first-run path is clean |
| **Downloads but no issues** | nothing yet, on its own | "it works and nobody needs it": automation produces that pattern too | separate automation from people first — look for downloads clustered on one version, or a report quoting a real error. If it is still people, that is a positioning question, not an engineering one |

The first row is the one that used to overreach. "Zero downloads means the problem is not painful"
assumes the funnel was open; with PyPI at 404 and a README-only entry point, an empty column is
consistent with both "nobody needs this" and "nobody could install it", and the measurement cannot
tell those apart.

## Deliberately not tracked

- Commits per day, lines of code, number of tests. They move when nothing
  happens and they reward the wrong behaviour — the 30-minute loop could triple
  all three without anyone being able to use the tool.
