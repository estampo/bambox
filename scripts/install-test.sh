#!/usr/bin/env bash
# Install the latest dev build of bambox from TestPyPI.
# Usage: ./scripts/install-test.sh
set -euo pipefail

# Find the latest dev version from the TestPyPI JSON API
LATEST=$(python3 -c "
import json, urllib.request
from packaging.version import Version
data = json.load(urllib.request.urlopen('https://test.pypi.org/pypi/bambox/json'))
devs = [v for v in data['releases'] if '.dev' in v and data['releases'][v]]
devs.sort(key=Version)
print(devs[-1])
")

if [ -z "$LATEST" ]; then
    echo "Could not find a dev version on TestPyPI"
    exit 1
fi

echo "Installing bambox==${LATEST} from TestPyPI..."
pip install --index-url https://test.pypi.org/simple/ \
    --extra-index-url https://pypi.org/simple/ \
    "bambox==${LATEST}"

echo ""
bambox --version
