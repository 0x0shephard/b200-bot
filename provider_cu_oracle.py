#!/usr/bin/env python3
"""CuOracle updater for B200 provider-specific markets."""

import argparse
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from dotenv import load_dotenv

from cu_oracle_client import (
    DEFAULT_CU_ORACLE_ADDRESS,
    CuOracleClient,
    OracleUpdate,
    OracleUpdateResult,
    price_to_x18,
    x18_to_usd,
)

load_dotenv()

CU_ORACLE_ADDRESS = os.getenv("CU_ORACLE_ADDRESS") or DEFAULT_CU_ORACLE_ADDRESS
PRIVATE_KEY = os.getenv("ORACLE_UPDATER_PRIVATE_KEY") or os.getenv("PRIVATE_KEY")
SEPOLIA_RPC_URL = os.getenv("SEPOLIA_RPC_URL")


@dataclass(frozen=True)
class ProviderConfig:
    asset_name: str
    provider_name: str
    env_var: str
    fallback_price: float
    default_asset_id: str


PROVIDERS: Dict[str, ProviderConfig] = {
    "ORACLE_B200": ProviderConfig(
        "ORACLE_B200",
        "Oracle",
        "ORACLE_B200_ASSET_ID",
        14.00,
        "0x9bf58bdbcbc9ddfd61f5add09163bfa8392f346eaf046baebcf3474867d92d41",
    ),
    "AWS_B200": ProviderConfig(
        "AWS_B200",
        "AWS",
        "AWS_B200_ASSET_ID",
        3.87,
        "0xd4cb0c395efb880df5c098c103eb6dfd23ee89a322b22e473e29c476f5240bd4",
    ),
    "COREWEAVE_B200": ProviderConfig(
        "COREWEAVE_B200",
        "CoreWeave",
        "COREWEAVE_B200_ASSET_ID",
        18.08,
        "0x7cfd459019cab14dcd5a85a668482047debede1f13dfb31be53aeb279791325b",
    ),
    "GCP_B200": ProviderConfig(
        "GCP_B200",
        "Google Cloud",
        "GCP_B200_ASSET_ID",
        7.28,
        "0x76d0a44da38fe3b87efb5f30986a5be867c6685bbaf1a26fb154c63a6fc23f0c",
    ),
}


def load_scraped_prices(selected: Iterable[str]) -> Dict[str, float]:
    weighted_index_file = Path(__file__).with_name("b200_weighted_index.json")
    selected = list(selected)
    prices: Dict[str, float] = {}

    if not weighted_index_file.exists():
        print(f"WARNING: {weighted_index_file.name} not found, using fallback prices")
        return {name: PROVIDERS[name].fallback_price for name in selected}

    try:
        with weighted_index_file.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except Exception as exc:
        print(f"WARNING: Failed to read {weighted_index_file.name}: {exc}")
        return {name: PROVIDERS[name].fallback_price for name in selected}

    all_provider_data = data.get("all_provider_data", {})
    for asset_name in selected:
        config = PROVIDERS[asset_name]
        provider_info = all_provider_data.get(config.provider_name, {})
        effective_price = provider_info.get("effective_price")
        original_price = provider_info.get("original_price")
        if effective_price is not None and float(effective_price) > 0:
            prices[asset_name] = float(effective_price)
            print(
                f"  Loaded {asset_name}: ${float(effective_price):.2f}/hr "
                f"(effective, original: ${float(original_price or 0):.2f}/hr)"
            )
        else:
            prices[asset_name] = config.fallback_price
            print(
                f"  WARNING: Missing {config.provider_name}, "
                f"using fallback ${config.fallback_price:.2f}/hr"
            )
    return prices


def configured_asset_ids(selected: Iterable[str]) -> Dict[str, str]:
    asset_ids: Dict[str, str] = {}
    for asset_name in selected:
        config = PROVIDERS[asset_name]
        asset_id = os.getenv(config.env_var) or config.default_asset_id
        if asset_id:
            asset_ids[asset_name] = asset_id
        else:
            print(f"Skipping {asset_name}: no asset ID configured")
    return asset_ids


def append_provider_log(results: List[OracleUpdateResult], prices: Dict[str, float], client: CuOracleClient) -> None:
    log_path = Path(__file__).with_name("b200_provider_price_updates.json")
    logs = []
    if log_path.exists():
        try:
            with log_path.open("r", encoding="utf-8") as handle:
                logs = json.load(handle)
            if not isinstance(logs, list):
                logs = []
        except Exception:
            logs = []

    logs.append(
        {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "network": "sepolia",
            "oracle": client.contract_address,
            "updater_address": client.address,
            "updates": [
                {
                    "asset_name": result.asset_name,
                    "asset_id": result.asset_id,
                    "price_usd": prices[result.asset_name],
                    "price_x18": result.price_x18,
                    "commit_tx_hash": result.commit_tx_hash,
                    "reveal_tx_hash": result.reveal_tx_hash,
                    "commit_timestamp": result.commit_timestamp,
                }
                for result in results
            ],
        }
    )

    logs = logs[-100:]
    with log_path.open("w", encoding="utf-8") as handle:
        json.dump(logs, handle, indent=2)
    print(f"Logged provider updates to {log_path.name}")


def run_provider_updater(selected: List[str], description: str, argv: Optional[List[str]] = None) -> None:
    parser = argparse.ArgumentParser(description=description)
    for asset_name in selected:
        flag = "--" + asset_name.lower().replace("_", "-")
        parser.add_argument(flag, type=float, help=f"{asset_name} price in USD/hr")
    parser.add_argument("--all", type=float, help="Set selected providers to this price in USD/hr")
    parser.add_argument("--show-only", action="store_true", help="Only show current configured prices")
    parser.add_argument("--no-verify", action="store_true", help="Skip post-reveal verification")
    parser.add_argument("--reveal-wait-seconds", type=int, default=None)
    args = parser.parse_args(argv)

    asset_ids = configured_asset_ids(selected)
    if not asset_ids:
        print("No provider-specific B200 assets configured; nothing to push.")
        sys.exit(0)

    if not PRIVATE_KEY:
        print("ERROR: ORACLE_UPDATER_PRIVATE_KEY or PRIVATE_KEY is required")
        sys.exit(1)

    try:
        client = CuOracleClient(
            rpc_url=SEPOLIA_RPC_URL,
            private_key=PRIVATE_KEY,
            contract_address=CU_ORACLE_ADDRESS,
        )
        client.print_context()
    except Exception as exc:
        print(f"ERROR: Failed to initialize CuOracle updater: {exc}")
        sys.exit(1)

    if args.show_only:
        for asset_name, asset_id in asset_ids.items():
            price_x18, updated_at = client.get_latest_price(asset_id)
            print(f"{asset_name}: ${x18_to_usd(price_x18):.6f}/hr at {updated_at}")
        sys.exit(0)

    scraped_prices = load_scraped_prices(asset_ids.keys())
    prices: Dict[str, float] = {}
    for asset_name in asset_ids.keys():
        override = getattr(args, asset_name.lower())
        prices[asset_name] = args.all if args.all is not None else (
            override if override is not None else scraped_prices[asset_name]
        )

    updates = [
        OracleUpdate(
            asset_name=asset_name,
            asset_id=asset_ids[asset_name],
            market=f"{asset_name.replace('_', '-')}-PERP",
            price_x18=price_to_x18(price_usd),
        )
        for asset_name, price_usd in prices.items()
    ]

    try:
        results = client.commit_and_reveal(
            updates,
            verify=not args.no_verify,
            reveal_wait_seconds=args.reveal_wait_seconds,
        )
        append_provider_log(results, prices, client)
    except Exception as exc:
        print(f"ERROR: Provider CuOracle update failed: {exc}")
        import traceback

        traceback.print_exc()
        sys.exit(1)

    print("Provider-specific B200 CuOracle update complete.")
