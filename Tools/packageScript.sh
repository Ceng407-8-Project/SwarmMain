#!/bin/bash

cd $(dirname "$0")/..

for dir in src; do
    if [ -d "$dir" ]; then
        bloom-generate rosdebian --os-name ubuntu --os-version jammy --ros-distro jazzy

        nocheck=1 fakeroot debian/rules binary
    fi
done

mkdir -p package
mv *.deb package/
mv *.ddeb package/