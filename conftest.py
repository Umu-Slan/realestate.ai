"""Pytest configuration. Use demo settings for tests."""
import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
os.environ.setdefault("DEMO_MODE", "True")
