# Claude skills (vendored)

Writing skills available to Claude Code in this repository. Both are MIT-licensed
and vendored here so they load automatically in any session on this repo,
including remote/web sessions.

| Skill | Source | Version | Pinned commit |
|---|---|---|---|
| `humanizer` | [blader/humanizer](https://github.com/blader/humanizer) | 2.9.1 | `523374d` |
| `agentic-humanizer` | [numen-tech/slopornot](https://github.com/numen-tech/slopornot) | 0.3.0 | `71bf2ea` |
| `slop-check` | [numen-tech/slopornot](https://github.com/numen-tech/slopornot) | 0.3.0 | `71bf2ea` |

Vendored on 2026-08-11.

## What each one does

- **humanizer** — single-pass editor built on Wikipedia's "Signs of AI writing"
  guide (WikiProject AI Cleanup). 33 numbered patterns, plus a false-positive
  list so technical prose is not flattened. Accepts a writing sample for voice
  calibration, which overrides its own style rules.
- **agentic-humanizer** — five-pass rewrite loop (pattern surgery, voice match,
  reading level, mechanical artefacts, structural refinement). Supports English
  plus da/de/es/it/no/sv tell-lists. Voice fingerprint needs 200+ words of your
  own writing to be useful.
- **slop-check** — routes to the Slop or Not local detector/readability tools.
  Requires a Mac with the Slop or Not app; without it the other two still work.

## Updating

    git clone --depth 1 https://github.com/blader/humanizer /tmp/h
    cp /tmp/h/SKILL.md .claude/skills/humanizer/SKILL.md
