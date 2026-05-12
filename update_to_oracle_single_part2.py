#!/usr/bin/env python3
"""CuOracle updater for B200 provider markets, part 2."""

from provider_cu_oracle import run_provider_updater


if __name__ == "__main__":
    run_provider_updater(
        ["COREWEAVE_B200", "GCP_B200"],
        "Update B200 provider CuOracle prices (CoreWeave and Google Cloud)",
    )
