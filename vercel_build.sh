#!/bin/bash
# Vercel build script to optimize memory usage

echo "Starting optimized build for Vercel..."

# Set memory-efficient pip options
export PIP_NO_CACHE_DIR=1
export PIP_DISABLE_PIP_VERSION_CHECK=1

# Install packages with memory optimization
pip install --no-deps --timeout=300 -r requirements.txt

echo "Build completed successfully"