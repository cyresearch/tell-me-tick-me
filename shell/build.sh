#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
swiftc -swift-version 5 -O -framework AppKit -framework WebKit main.swift -o TellMeTickMe
echo "OK -> $(pwd)/TellMeTickMe"
