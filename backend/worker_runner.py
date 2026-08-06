#!/usr/bin/env python3
"""Standalone background worker entry point for Docker/Kubernetes container deployments."""

import sys
import logging
from backend.logging_config import setup_logger
from backend.worker import ReliableWorker

logger = setup_logger("seo_agent.worker_runner")

def main():
    logger.info("Initializing standalone SEO Agent background worker...")
    worker = ReliableWorker()
    try:
        worker.start(run_loop=True)
    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt received. Stopping worker...")
        worker.shutdown()
    sys.exit(0)

if __name__ == "__main__":
    main()
