#!/usr/bin/env python3
"""An engine double that reads commands and never answers, until told to quit."""

import sys

for line in sys.stdin:
    if line.strip() == "quit":
        break
