#!/bin/bash
# Build the screenshot fixture web app with caching.
# A cold fixture build took 66 s; this script uses a content stamp to skip
# rebuilds when inputs haven't changed (~0 s on cache hit).
set -euo pipefail

cd "$(dirname "$0")/.."

href="${1:-/app/}"

# Compute a stamp from all inputs that affect the build output.
# The stamp includes: base href, .fvmrc, pubspec.yaml, pubspec.lock, and all
# source files under lib/, tool/fixture/, web/, assets/.
stamp_file="build/web_fixture/.fixture-stamp"

compute_stamp() {
  {
    echo "$href"
    cat .fvmrc pubspec.yaml pubspec.lock 2>/dev/null || true
    git ls-files -co --exclude-standard lib tool/fixture web assets 2>/dev/null | sort | xargs sha256sum 2>/dev/null || true
  } | sha256sum | cut -d' ' -f1
}

stamp=$(compute_stamp)

# Check if cached build is valid.
if [[ -f "$stamp_file" && -f "build/web_fixture/main.dart.js" ]]; then
  cached_stamp=$(cat "$stamp_file" 2>/dev/null || true)
  if [[ "$cached_stamp" == "$stamp" ]]; then
    echo "fixture build up to date"
    exit 0
  fi
fi

# Build the fixture.
fvm flutter build web --release --no-pub --no-wasm-dry-run -O1 --no-source-maps -t tool/fixture/main.dart -o build/web_fixture --base-href "$href"

# Write stamp after successful build.
echo "$stamp" > "$stamp_file"
