#!/usr/bin/env python3
"""Update oracle prices for all H200 provider-specific markets.

This script updates the MultiAssetOracle with current market prices for:
- Oracle Cloud H200: $6.47/hour
- AWS H200: $4.04/hour
- CoreWeave H200: $14.53/hour
- Google Cloud H200: $6.60/hour

Usage:
    python scripts/update_h200_provider_prices.py
    python scripts/update_h200_provider_prices.py --oracle-h200 6.50 --aws-h200 4.10
    python scripts/update_h200_provider_prices.py --all 5.00  # Set all to same price
"""

import json
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, Optional, Tuple

from dotenv import load_dotenv
from eth_account import Account
from web3 import Web3

load_dotenv()

SEPOLIA_RPC_URL = os.getenv("SEPOLIA_RPC_URL", "https://rpc.sepolia.org")
PRIVATE_KEY = os.getenv("PRIVATE_KEY") or os.getenv("ORACLE_UPDATER_PRIVATE_KEY")
MULTI_ASSET_ORACLE_ADDRESS = os.getenv(
    "MULTI_ASSET_ORACLE_ADDRESS",
    "0xB44d652354d12Ac56b83112c6ece1fa2ccEfc683",
)

# Asset IDs (keccak256 of asset names)
ASSET_IDS = {
    "ORACLE_H200": "0xf162ee5639707284e5b6a23eeb0b5d6627a935f1ff571463d1eb29e4e2800e6c",
    "AWS_H200": "0xaea03c0d396f0037b42610d8306208c650a1390eba181b60426a65fb244e4b96",
    "COREWEAVE_H200": "0x67a96f399341b1228769fdb687640ca37844b30f83f09a6de6e06888876a29d1",
    "GCP_H200": "0xe54dd81ff75d2b3f55dc0203f393dda742a93a45a42f8c7e726fd47d639dfd27",
}

# Default prices (update these with current market rates)
DEFAULT_PRICES = {
    "ORACLE_H200": 6.47,  # Oracle Cloud H200
    "AWS_H200": 4.04,      # AWS H200
    "COREWEAVE_H200": 14.53,  # CoreWeave H200
    "GCP_H200": 6.60,      # Google Cloud H200
}

PRICE_DECIMALS = 18

# MultiAssetOracle ABI - minimal interface
MULTI_ASSET_ORACLE_ABI = [
    {
        "type": "function",
        "name": "updatePrice",
        "inputs": [
            {"name": "assetId", "type": "bytes32", "internalType": "bytes32"},
            {"name": "newPrice", "type": "uint256", "internalType": "uint256"},
        ],
        "outputs": [],
        "stateMutability": "nonpayable",
    },
    {
        "type": "function",
        "name": "prices",
        "inputs": [
            {"name": "assetId", "type": "bytes32", "internalType": "bytes32"}
        ],
        "outputs": [
            {"name": "", "type": "uint256", "internalType": "uint256"}
        ],
        "stateMutability": "view",
    },
    {
        "type": "function",
        "name": "getPriceData",
        "inputs": [
            {"name": "assetId", "type": "bytes32", "internalType": "bytes32"}
        ],
        "outputs": [
            {"name": "price", "type": "uint256", "internalType": "uint256"},
            {"name": "lastUpdated", "type": "uint256", "internalType": "uint256"},
        ],
        "stateMutability": "view",
    },
    {
        "type": "event",
        "name": "PriceUpdated",
        "inputs": [
            {"name": "assetId", "type": "bytes32", "indexed": True, "internalType": "bytes32"},
            {"name": "price", "type": "uint256", "indexed": False, "internalType": "uint256"},
            {"name": "timestamp", "type": "uint256", "indexed": False, "internalType": "uint256"},
        ],
        "anonymous": False,
    },
]


@dataclass
class AssetPrice:
    """Asset price data."""
    asset_name: str
    asset_id: str
    price_usd: float

    @property
    def price_scaled(self) -> int:
        """Price in WAD format (1e18)."""
        return int(self.price_usd * (10 ** PRICE_DECIMALS))


class H200ProviderPriceUpdater:
    """Update H200 provider-specific prices on MultiAssetOracle contract."""

    def __init__(self, rpc_url: str, private_key: str, contract_address: str):
        self.w3 = Web3(Web3.HTTPProvider(rpc_url))
        if not self.w3.is_connected():
            raise ConnectionError(f"Failed to connect to Sepolia RPC: {rpc_url}")

        self.account = Account.from_key(private_key)
        self.address = self.account.address
        self.contract = self.w3.eth.contract(
            address=Web3.to_checksum_address(contract_address),
            abi=MULTI_ASSET_ORACLE_ABI,
        )

        balance_eth = self.w3.from_wei(self.w3.eth.get_balance(self.address), "ether")
        print("=" * 70)
        print("H200 PROVIDER PRICE UPDATER")
        print("=" * 70)
        print(f"Connected to Sepolia testnet")
        print(f"  Chain ID: {self.w3.eth.chain_id}")
        print(f"  Latest block: {self.w3.eth.block_number}")
        print(f"  Updater address: {self.address}")
        print(f"  Balance: {balance_eth:.4f} ETH")
        print(f"  MultiAssetOracle: {contract_address}")
        print("=" * 70)

    def _build_dynamic_fee(self) -> Tuple[int, int]:
        """Build dynamic gas fees."""
        base_fee = self.w3.eth.gas_price
        max_priority = self.w3.to_wei(1, "gwei")
        max_fee = max(base_fee * 2, max_priority * 2)
        return max_fee, max_priority

    def _send_transaction(self, func, gas_limit: int) -> Tuple[str, dict]:
        """Build, sign, and send a transaction."""
        max_fee, max_priority = self._build_dynamic_fee()
        tx = func.build_transaction(
            {
                "from": self.address,
                "nonce": self.w3.eth.get_transaction_count(self.address),
                "gas": gas_limit,
                "maxFeePerGas": max_fee,
                "maxPriorityFeePerGas": max_priority,
                "chainId": 11155111,
            }
        )
        signed = self.account.sign_transaction(tx)

        # Handle different Web3.py versions
        if hasattr(signed, "raw_transaction"):
            raw_tx = signed.raw_transaction
        elif hasattr(signed, "rawTransaction"):
            raw_tx = signed.rawTransaction
        else:
            raw_tx = signed

        tx_hash = self.w3.eth.send_raw_transaction(raw_tx)
        receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=180)
        return tx_hash.hex(), dict(receipt)

    def get_current_price(self, asset_id: str) -> Tuple[float, int]:
        """Get current price and last update timestamp for an asset.

        Returns:
            Tuple of (price_usd, last_updated_timestamp)
        """
        try:
            price_raw, last_updated = self.contract.functions.getPriceData(asset_id).call()
            price_usd = price_raw / (10 ** PRICE_DECIMALS)
            return price_usd, last_updated
        except Exception:
            return 0.0, 0

    def update_price(self, asset_price: AssetPrice, show_detail: bool = True) -> str:
        """Update a single asset price.

        Args:
            asset_price: AssetPrice object with asset details
            show_detail: Whether to show detailed output

        Returns:
            Transaction hash
        """
        current_price, last_updated = self.get_current_price(asset_price.asset_id)

        if show_detail:
            print(f"\n[{asset_price.asset_name}]")
            if current_price > 0:
                delta = asset_price.price_usd - current_price
                change_pct = (delta / current_price) * 100
                print(f"  Current: ${current_price:.2f}/hr")
                print(f"  New:     ${asset_price.price_usd:.2f}/hr (Δ {change_pct:+.2f}%)")
            else:
                print(f"  Current: Not set")
                print(f"  New:     ${asset_price.price_usd:.2f}/hr")

            if last_updated > 0:
                time_ago = int(time.time()) - last_updated
                hours_ago = time_ago // 3600
                mins_ago = (time_ago % 3600) // 60
                print(f"  Last updated: {hours_ago}h {mins_ago}m ago")

        # Send transaction
        tx_hash, receipt = self._send_transaction(
            self.contract.functions.updatePrice(
                asset_price.asset_id,
                asset_price.price_scaled
            ),
            gas_limit=150_000,
        )

        if show_detail:
            print(f"  Transaction: {tx_hash}")
            print(f"  Gas used: {receipt['gasUsed']:,}")

        # Verify update
        verified_price, _ = self.get_current_price(asset_price.asset_id)
        if abs(verified_price - asset_price.price_usd) < 0.01:
            if show_detail:
                print(f"  ✓ Verified: ${verified_price:.2f}/hr")
        else:
            print(f"  ⚠ WARNING: Price mismatch!")
            print(f"    Expected: ${asset_price.price_usd:.2f}/hr")
            print(f"    Got: ${verified_price:.2f}/hr")

        return tx_hash

    def update_all_prices(self, prices: Dict[str, float]) -> Dict[str, str]:
        """Update all H200 provider prices.

        Args:
            prices: Dictionary mapping asset names to prices in USD/hour

        Returns:
            Dictionary mapping asset names to transaction hashes
        """
        print("\n" + "=" * 70)
        print("UPDATING ALL H200 PROVIDER PRICES")
        print("=" * 70)

        results = {}

        for asset_name, price_usd in prices.items():
            if asset_name not in ASSET_IDS:
                print(f"\nWARNING: Unknown asset '{asset_name}', skipping")
                continue

            asset_price = AssetPrice(
                asset_name=asset_name,
                asset_id=ASSET_IDS[asset_name],
                price_usd=price_usd
            )

            try:
                tx_hash = self.update_price(asset_price)
                results[asset_name] = tx_hash
            except Exception as exc:
                print(f"\nERROR updating {asset_name}: {exc}")
                results[asset_name] = None

        return results

    def show_price_comparison(self):
        """Display price comparison across all H200 providers."""
        print("\n" + "=" * 70)
        print("H200 PROVIDER PRICE COMPARISON")
        print("=" * 70)

        prices = {}
        for asset_name, asset_id in ASSET_IDS.items():
            price, last_updated = self.get_current_price(asset_id)
            prices[asset_name] = price

        # Sort by price
        sorted_prices = sorted(prices.items(), key=lambda x: x[1])

        print(f"\n{'Provider':<20} {'Price':<12} {'Premium vs AWS':<15}")
        print("-" * 70)

        aws_price = prices.get("AWS_H200", 0)

        for asset_name, price in sorted_prices:
            provider_name = asset_name.replace("_H200", "").replace("_", " ").title()
            price_str = f"${price:.2f}/hr" if price > 0 else "Not set"

            if price > 0 and aws_price > 0 and asset_name != "AWS_H200":
                premium = ((price - aws_price) / aws_price) * 100
                premium_str = f"+{premium:.1f}%"
            elif asset_name == "AWS_H200":
                premium_str = "Baseline"
            else:
                premium_str = "-"

            print(f"{provider_name:<20} {price_str:<12} {premium_str:<15}")

        print("=" * 70)

        # Show arbitrage opportunity
        if all(p > 0 for p in prices.values()):
            cheapest = min(sorted_prices, key=lambda x: x[1])
            most_expensive = max(sorted_prices, key=lambda x: x[1])

            spread = most_expensive[1] - cheapest[1]
            spread_pct = (spread / cheapest[1]) * 100

            print("\nARBITRAGE OPPORTUNITY:")
            print(f"  Cheapest:      {cheapest[0].replace('_H200', '').replace('_', ' ').title()} (${cheapest[1]:.2f}/hr)")
            print(f"  Most Expensive: {most_expensive[0].replace('_H200', '').replace('_', ' ').title()} (${most_expensive[1]:.2f}/hr)")
            print(f"  Spread:        ${spread:.2f}/hr ({spread_pct:.1f}%)")
            print(f"\n  Strategy: Short {most_expensive[0].replace('_H200', '').replace('_', ' ').title()}, Long {cheapest[0].replace('_H200', '').replace('_', ' ').title()}")
            print("=" * 70)

    def log_update(self, results: Dict[str, str], prices: Dict[str, float]):
        """Log price updates to JSON file."""
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "network": "sepolia",
            "contract_address": MULTI_ASSET_ORACLE_ADDRESS,
            "updater_address": self.address,
            "updates": []
        }

        for asset_name, tx_hash in results.items():
            if tx_hash:
                log_entry["updates"].append({
                    "asset_name": asset_name,
                    "asset_id": ASSET_IDS[asset_name],
                    "price_usd": prices[asset_name],
                    "price_scaled": int(prices[asset_name] * (10 ** PRICE_DECIMALS)),
                    "tx_hash": tx_hash,
                })

        log_file = "h200_provider_price_updates.json"
        logs = []

        # Load existing logs
        if os.path.exists(log_file):
            try:
                with open(log_file, "r", encoding="utf-8") as f:
                    logs = json.load(f)
                if not isinstance(logs, list):
                    logs = []
            except Exception:
                logs = []

        # Append and keep last 100
        logs.append(log_entry)
        logs = logs[-100:]

        # Save logs
        try:
            with open(log_file, "w", encoding="utf-8") as f:
                json.dump(logs, f, indent=2)
            print(f"\n✓ Logged updates to {log_file}")
        except Exception as exc:
            print(f"\nERROR: Failed to write log file: {exc}")


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Update H200 provider-specific oracle prices",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Update all providers with default prices
  python scripts/update_h200_provider_prices.py

  # Update specific providers
  python scripts/update_h200_provider_prices.py --oracle-h200 6.50 --aws-h200 4.10

  # Set all providers to the same price
  python scripts/update_h200_provider_prices.py --all 5.00

  # Just show current prices (no updates)
  python scripts/update_h200_provider_prices.py --show-only

Environment Variables:
  SEPOLIA_RPC_URL    Ethereum RPC endpoint
  PRIVATE_KEY        Wallet private key for signing transactions
        """
    )

    parser.add_argument("--oracle-h200", type=float, help="Oracle Cloud H200 price (USD/hr)")
    parser.add_argument("--aws-h200", type=float, help="AWS H200 price (USD/hr)")
    parser.add_argument("--coreweave-h200", type=float, help="CoreWeave H200 price (USD/hr)")
    parser.add_argument("--gcp-h200", type=float, help="Google Cloud H200 price (USD/hr)")
    parser.add_argument("--all", type=float, help="Set all providers to this price (USD/hr)")
    parser.add_argument("--show-only", action="store_true", help="Only show current prices, don't update")

    args = parser.parse_args()

    # Validate environment
    if not PRIVATE_KEY:
        print("=" * 70)
        print("ERROR: Private key not configured")
        print("=" * 70)
        print("Set PRIVATE_KEY environment variable")
        print("=" * 70)
        sys.exit(1)

    # Initialize updater
    try:
        updater = H200ProviderPriceUpdater(
            rpc_url=SEPOLIA_RPC_URL,
            private_key=PRIVATE_KEY,
            contract_address=MULTI_ASSET_ORACLE_ADDRESS,
        )
    except Exception as exc:
        print(f"\nERROR: Failed to initialize updater: {exc}")
        sys.exit(1)

    # Show current prices
    if args.show_only:
        updater.show_price_comparison()
        sys.exit(0)

    # Determine prices to update
    prices = {}

    if args.all is not None:
        # Set all to same price
        for asset_name in ASSET_IDS.keys():
            prices[asset_name] = args.all
    else:
        # Use individual prices or defaults
        prices["ORACLE_H200"] = args.oracle_h200 if args.oracle_h200 is not None else DEFAULT_PRICES["ORACLE_H200"]
        prices["AWS_H200"] = args.aws_h200 if args.aws_h200 is not None else DEFAULT_PRICES["AWS_H200"]
        prices["COREWEAVE_H200"] = args.coreweave_h200 if args.coreweave_h200 is not None else DEFAULT_PRICES["COREWEAVE_H200"]
        prices["GCP_H200"] = args.gcp_h200 if args.gcp_h200 is not None else DEFAULT_PRICES["GCP_H200"]

    # Validate prices
    for asset_name, price in prices.items():
        if price <= 0:
            print(f"\nERROR: {asset_name} price must be greater than zero (got {price})")
            sys.exit(1)
        if price > 100:
            print(f"\nWARNING: {asset_name} price ${price:.2f}/hr seems unusually high")
            print("Expected range: $1-20/hour for H200 GPUs")

    # Update prices
    try:
        results = updater.update_all_prices(prices)

        # Log results
        updater.log_update(results, prices)

        # Show comparison
        updater.show_price_comparison()

        # Print summary
        print("\n" + "=" * 70)
        print("UPDATE SUMMARY")
        print("=" * 70)
        successful = sum(1 for tx in results.values() if tx is not None)
        failed = len(results) - successful
        print(f"  Successful: {successful}/{len(results)}")
        if failed > 0:
            print(f"  Failed: {failed}")
        print("\n  View transactions on Etherscan:")
        for asset_name, tx_hash in results.items():
            if tx_hash:
                print(f"    {asset_name}: https://sepolia.etherscan.io/tx/{tx_hash}")
        print("=" * 70)

        sys.exit(0 if failed == 0 else 1)

    except Exception as exc:
        print("\n" + "=" * 70)
        print("ERROR: UPDATE FAILED")
        print("=" * 70)
        print(f"  {exc}")
        print("=" * 70)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
