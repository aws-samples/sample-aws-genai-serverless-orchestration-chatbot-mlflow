#!/bin/bash

# Create the layer directory structure
LAYER_DIR="layers/python/python/lib/python3.12/site-packages"
mkdir -p "$LAYER_DIR"

# Remove any existing packages
rm -rf "$LAYER_DIR"/*

# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies into the layer directory
pip install --platform manylinux2014_x86_64 \
    --target="$LAYER_DIR" \
    --implementation cp \
    --python-version 3.12 \
    --only-binary=:all: \
    -r requirements.txt

# Deactivate virtual environment
deactivate

# Clean up
rm -rf .venv
