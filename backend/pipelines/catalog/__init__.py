"""Builds the product catalog from the Amazon Reviews 2023 dataset.

download -> select -> embed -> neighbors -> load. Each step reads the previous step's
files from a local workspace folder, so any step can be re-run on its own.
"""
