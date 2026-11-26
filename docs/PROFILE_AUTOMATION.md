# Profile automation

`profile_gen` regenerates the dynamic parts of `README.md` and the contribution graph SVGs in `assets/`. A scheduled GitHub Actions workflow (`.github/workflows/update-profile.yml`) runs it and commits any changes.

## Section markers

Each generated section lives between a pair of HTML comment markers in `README.md`:

```markdown
<!-- NAME:START -->
...generated content...
<!-- NAME:END -->
```

| Marker name     | Content                                                        |
| --------------- | -------------------------------------------------------------- |
| `FEATURED`      | Featured repositories listed in `featured_repos`               |
| `STATS`         | Aggregate profile statistics                                   |
| `GRAPH`         | Contribution graph picture (light and dark SVGs from `assets/`) |
| `ACTIVITY`      | Recent public activity feed                                    |
| `CONTRIBUTIONS` | Contributions to repositories outside your own account         |

Rules:

- Only the text between a marker pair is replaced. Everything outside the markers is kept exactly as written, so edit the rest of the README freely.
- Do not edit text between markers by hand. The next run overwrites it.
- Each of the five sections needs exactly one `START` and one `END` marker, with `START` first. Names are case-sensitive.
- If any marker is missing, duplicated, or out of order, the generator exits with an error naming the section and does not modify any file.
- If fetching data for a section fails, that section keeps its previous content and the error is logged.

## Configuration

Settings are in `profile.config.json` at the repository root. Invalid values stop the run with a `ERROR config:` message.

| Option                     | Type             | Default  | Description                                                                   |
| -------------------------- | ---------------- | -------- | ----------------------------------------------------------------------------- |
| `owner`                    | string, required | none     | GitHub username. The profile repository is `<owner>/<owner>`.                 |
| `featured_repos`           | list of strings  | `[]`     | Repositories to feature, each in `owner/name` form.                           |
| `org_allow_list`           | list of strings  | `[]`     | Organizations whose contributions may be shown.                               |
| `feed_length`              | positive integer | `10`     | Maximum number of entries in the activity feed.                               |
| `contribution_period_days` | positive integer | `365`    | Look-back window for contributions. Maximum 365.                              |
| `max_contribution_repos`   | positive integer | `10`     | Maximum number of repositories in the contributions section.                  |
| `max_title_length`         | positive integer | `72`     | Maximum length of titles before they are truncated.                           |

Example:

```json
{
  "owner": "kelvinmanavar",
  "featured_repos": ["kelvinmanavar/some-project"],
  "org_allow_list": [],
  "feed_length": 10,
  "contribution_period_days": 365
}
```

## Running locally

Requires Python 3.

```bash
python3 -m profile_gen
```

Run it from the repository root. It reads `profile.config.json` and `README.md`, then rewrites the marked sections and `assets/contribution-graph-{dark,light}.svg`. Review the result with `git diff`.

Options:

- `--root PATH`: use a different repository root (defaults to the directory containing `profile_gen`).

Without `PROFILE_STATS_TOKEN` set, the generator runs in Public mode and shows only publicly available data. To run in Extended mode locally, export the token first:

```bash
export PROFILE_STATS_TOKEN=<your token>
python3 -m profile_gen
```

Do not commit the token or paste it into files. The generator redacts it from log output.

## PROFILE_STATS_TOKEN

`PROFILE_STATS_TOKEN` is an optional personal access token that lets the generator read data the default workflow token cannot, such as private-repository contribution counts. Without it, or if GitHub rejects it, the generator logs a warning and falls back to Public mode.

### Create a read-only token

Use a fine-grained personal access token with the fewest permissions possible:

1. Open GitHub **Settings > Developer settings > Personal access tokens > Fine-grained tokens** and choose **Generate new token**.
2. Name it (for example `profile-stats`) and set a short expiration, such as 90 days.
3. Set **Resource owner** to your account.
4. Under **Repository access**, choose **Public repositories (read-only)**, or select only the repositories you want counted.
5. Under **Permissions**, grant only **Metadata: Read-only**, which is mandatory. Add **Contents: Read-only** only if you need to count commits in selected private repositories. Grant no write permissions.
6. Generate the token and copy it. GitHub shows it once.

If you use a classic token instead, select only `read:user`, plus `repo` only if private data is required. `repo` also grants write access, so prefer the fine-grained token.

### Store it as a repository secret

1. In the profile repository, open **Settings > Secrets and variables > Actions**.
2. Choose **New repository secret**.
3. Set the name to exactly `PROFILE_STATS_TOKEN` and paste the token as the value.
4. Choose **Add secret**.

The workflow passes it to the generator as the `PROFILE_STATS_TOKEN` environment variable. Rotate the token before it expires by updating the secret with a new value.
