#!/usr/bin/env bash
# Run the direct-mode tests on GenVM v0.6 against a Bradbury build.
#
#   pip install --pre genlayer-test==0.30.0rc2     # in a separate virtualenv
#   tools/test_v6.sh /path/to/that/venv [bradbury/build/auction_deposit_packed.py]
#
# The test files are the same as for Studio (GenVM v0.2); only the shared
# helpers differ, so a scratch copy of the repo swaps in tests/conftest_v6.py.
# Builds: python3 bradbury/port.py contracts/auction_deposit.py bradbury/build/auction_deposit.py
#         python3 bradbury/port.py contracts/auction_deposit.py bradbury/build/auction_deposit_packed.py --pack
set -euo pipefail
VENV="${1:?path to a virtualenv with genlayer-test 0.30.0rc2}"
BUILD="${2:-bradbury/build/auction_deposit_packed.py}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
(cd "$ROOT" && git ls-files -co --exclude-standard -- contracts tests tools bradbury examples gltest.config.yaml | tar -cf - -T -) | tar -xf - -C "$TMP"
cp "$TMP/tests/conftest_v6.py" "$TMP/tests/direct/conftest.py"
cd "$TMP"
GENVM_VERSION="${GENVM_VERSION:-v0.6.0-rc10}" AD_CONTRACT="$BUILD" PYTHONPATH=. \
  "$VENV/bin/python" -m pytest tests/direct -q -p no:cacheprovider
