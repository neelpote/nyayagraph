"""Hermetic defaults applied before application modules are imported."""

import os


os.environ["APP_ENV"] = "test"
os.environ["DEV_MODE"] = "true"
os.environ["AUTH_MODE"] = "dev_jwt"
os.environ["STORAGE_BACKEND"] = "local"
os.environ["FABRIC_ENABLED"] = "false"
os.environ["IPFS_ENABLED"] = "false"
os.environ["ENABLE_NEO4J"] = "false"
os.environ["PUBLIC_CHAIN_MODE"] = "mock"
