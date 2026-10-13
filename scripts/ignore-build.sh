#!/bin/bash
# Vercel "Ignored Build Step": exit 0 = skip the build, exit 1 = build.
# Skip only when nothing that is served changed since the last deployed commit (hourly data commits, docs, tests...).
[ -n "$VERCEL_GIT_PREVIOUS_SHA" ] || exit 1
git diff --quiet "$VERCEL_GIT_PREVIOUS_SHA" HEAD -- . \
  ':(exclude)docs/live.json' ':(exclude)docs/xcheck.json' ':(exclude)data' ':(exclude)hazeshaman' \
  ':(exclude)tests' ':(exclude)social' ':(exclude)README.md' ':(exclude)requirements.txt' 2>/dev/null
[ $? -eq 0 ] && exit 0
exit 1
