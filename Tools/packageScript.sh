#!/bin/bash

set -Eeuo pipefail

PROJECT_DIR=$(cd "$(dirname "$0")/.." && pwd)
SRC_DIR="$PROJECT_DIR/src"
PACKAGE_DIR="$PROJECT_DIR/package"

mkdir -p "$PACKAGE_DIR"

PACKAGE_XML=("$SRC_DIR"/*/package.xml)

if [ "${#PACKAGE_XML[@]}" -eq 0 ]; then
    echo "Ros paketi bulunamadı: $SRC_DIR" >&2
    exit 1
fi

for xml in "${PACKAGE_XML[@]}"; do
    PACKAGE_PATH=$(dirname "$xml")
    PACKAGE_NAME=$(basename "$PACKAGE_PATH")

    echo "========== $PACKAGE_NAME =========="
    cd "$PACKAGE_PATH"

    bloom-generate rosdebian --os-name ubuntu --os-version noble --ros-distro jazzy

    DEB_BUILD_OPTIONS=nocheck fakeroot debian/rules binary

    mv "$SRC_DIR"/*.deb" "$PACKAGE_DIR/"
    mv "$SRC_DIR"/*.ddeb" "$PACKAGE_DIR/"
done