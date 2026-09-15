# Upstream

Vendored from [guillaumemeyer/watermarks-remover](https://github.com/guillaumemeyer/watermarks-remover)
at commit `196ba9d168d3bdabd4fc7cba8e739f6e234cb6cc`, path `skills/clean-user-facing-text/`.

Licensed MIT (see `LICENSE`). Copied verbatim; no modifications.

Only this text-hygiene skill was vendored. The upstream repository's other skill
(`remove-ai-marks`) and its HTTP service were not installed.

To refresh:

    git clone --depth 1 https://github.com/guillaumemeyer/watermarks-remover.git
    cp -r watermarks-remover/skills/clean-user-facing-text .claude/skills/
