#!/bin/bash
set -e
git pull 2>/dev/null || echo "Note: not a git repo yet, skipping pull"
streamlit run dashboard.py
