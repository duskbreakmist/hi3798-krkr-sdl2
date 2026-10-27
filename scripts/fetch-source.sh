#!/usr/bin/env bash
set -euo pipefail
work=${KRKR_WORK:-"$PWD/work"}
revision=949faf9a874f54b149a3fe5382cfccb38afb99bb
digest=75a950ad1733d76ef1c203f8adf5005c4448e491b6283702e3e0679396613d58
mkdir -p "$work"
archive="$work/upstream.tar.gz"
if [[ ! -f "$archive" ]]; then
  curl --fail --location --retry 3 --connect-timeout 20 \
    "https://codeload.github.com/DrFlyingPig/krkr-ns/tar.gz/$revision" -o "$archive"
fi
printf '%s  %s\n' "$digest" "$archive" | sha256sum -c -
if [[ ! -d "$work/source" ]]; then
  mkdir "$work/source"
  tar -xzf "$archive" --strip-components=1 -C "$work/source"
fi
