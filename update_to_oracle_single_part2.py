#!/usr/bin/env python3
"""Update oracle prices for B200 provider-specific markets (Part 2).

This script updates the MultiAssetOracle with current market prices for:
- CoreWeave B200
- Google Cloud B200

Prices are read from b200_weighted_index.json (effective_price after discounts).

Usage:
    python update_to_oracle_single_part2.py
    python update_to_oracle_single_part2.py --coreweave-b200 42.00 --gcp-b200 18.50
    python update_to_oracle_single_part2.py --all 5.00  # Set all to same price
    python update_to_oracle_single_part2.py --show-only  # Just show current prices
"""

import json
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
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

# Asset IDs (keccak256 of asset names) - Part 2
ASSET_IDS = {
    "COREWEAVE_B200": "0x67a96f399341b1228769fdb687640ca37844b30f83f09a6de6e06888876a29d1",
    "GCP_B200": "0xe54dd81ff75d2b3f55dc0203f393dda742a93a45a42f8c7e726fd47d639dfd27",
}

# Mapping from asset names to provider names in b200_normalized_prices.json
PROVIDER_MAPPING = {
    "COREWEAVE_B200": "CoreWeave",
    "GCP_B200": "Google Cloud",
}

# Fallback prices (effective prices) only used if weighted index is unavailable
FALLBACK_PRICES = {
    "COREWEAVE_B200": 18.08,  # CoreWeave B200 effective price
    "GCP_B200": 7.28,         # Google Cloud B200 effective price
}


def load_scraped_prices() -> Dict[str, float]:
    """Load effective prices from the b200_weighted_index.json file.

    Uses the effective_price (after discounts/normalization) for each provider,
    NOT the original/raw scraped prices.

    Returns:
        Dictionary mapping asset names to effective prices in USD/hour
    """
    script_dir = Path(__file__).parent
    weighted_index_file = script_dir / "b200_weighted_index.json"

    prices = {}

    if not weighted_index_file.exists():
        print(f"WARNING: {weighted_index_file} not found, using fallback prices")
        return FALLBACK_PRICES.copy()

    try:
        with open(weighted_index_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        all_provider_data = data.get("all_provider_data", {})

        for asset_name, provider_name in PROVIDER_MAPPING.items():
            if provider_name in all_provider_data:
                provider_info = all_provider_data[provider_name]
                # Use effective_price (normalized/discounted) instead of original_price
                effective_price = provider_info.get("effective_price")
                original_price = provider_info.get("original_price")

                if effective_price is not None and effective_price > 0:
                    prices[asset_name] = float(effective_price)
                    print(f"  Loaded {asset_name}: ${effective_price:.2f}/hr (effective price, original: ${original_price:.2f}/hr)")
                else:
                    prices[asset_name] = FALLBACK_PRICES[asset_name]
                    print(f"  WARNING: Invalid effective_price for {provider_name}, using fallback ${FALLBACK_PRICES[asset_name]:.2f}/hr")
            else:
                prices[asset_name] = FALLBACK_PRICES[asset_name]
                print(f"  WARNING: {provider_name} not found in weighted index, using fallback ${FALLBACK_PRICES[asset_name]:.2f}/hr")

        return prices

    except Exception as e:
        print(f"ERROR: Failed to load weighted index prices: {e}")
        return FALLBACK_PRICES.copy()

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


class B200ProviderPriceUpdater:
    """Update B200 provider-specific prices on MultiAssetOracle contract."""

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
        print("B200 PROVIDER PRICE UPDATER")
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

    def _send_transaction(self, func, gas_limit: int, nonce: Optional[int] = None) -> Tuple[str, dict]:
        """Build, sign, and send a transaction.

        Args:
            func: Contract function call
            gas_limit: Gas limit
            nonce: Optional explicit nonce (recommended when sending multiple txs)
        """
        max_fee, max_priority = self._build_dynamic_fee()
        if nonce is None:
            nonce = self.w3.eth.get_transaction_count(self.address)
        tx = func.build_transaction(
            {
                "from": self.address,
                "nonce": nonce,
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
        print("UPDATING ALL B200 PROVIDER PRICES")
        print("=" * 70)

        results = {}

        # When sending multiple txs back-to-back, rely on an explicit sequential nonce.
        next_nonce = self.w3.eth.get_transaction_count(self.address)

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
                # Wait for each transaction receipt before proceeding.
                tx_hash, receipt = self._send_transaction(
                    self.contract.functions.updatePrice(
                        asset_price.asset_id,
                        asset_price.price_scaled,
                    ),
                    gas_limit=150_000,
                    nonce=next_nonce,
                )

                print(f"  Transaction: {tx_hash}")
                print(f"  Gas used: {receipt['gasUsed']:,}")

                # Verify update
                verified_price, _ = self.get_current_price(asset_price.asset_id)
                if abs(verified_price - asset_price.price_usd) < 0.01:
                    print(f"  ✓ Verified: ${verified_price:.2f}/hr")
                else:
                    print(f"  ⚠ WARNING: Price mismatch!")
                    print(f"    Expected: ${asset_price.price_usd:.2f}/hr")
                    print(f"    Got: ${verified_price:.2f}/hr")

                results[asset_name] = tx_hash
                next_nonce += 1

                # Give the network/RPC a moment to propagate the new nonce.
                time.sleep(2)
            except Exception as exc:
                print(f"\nERROR updating {asset_name}: {exc}")
                results[asset_name] = None

        return results

    def show_price_comparison(self):
        """Display price comparison across all H200 providers."""
        print("\n" + "=" * 70)
        print("B200 PROVIDER PRICE COMPARISON")
        print("=" * 70)

        prices = {}
        for asset_name, asset_id in ASSET_IDS.items():
            price, last_updated = self.get_current_price(asset_id)
            prices[asset_name] = price

        # Sort by price
        sorted_prices = sorted(prices.items(), key=lambda x: x[1])

        print(f"\n{'Provider':<20} {'Price':<12} {'Premium vs Cheapest':<18}")
        print("-" * 70)

        cheapest_price = min((p for p in prices.values() if p > 0), default=0)

        for asset_name, price in sorted_prices:
            provider_name = asset_name.replace("_B200", "").replace("_", " ").title()
            price_str = f"${price:.2f}/hr" if price > 0 else "Not set"

            if price > 0 and cheapest_price > 0:
                premium = ((price - cheapest_price) / cheapest_price) * 100
                premium_str = "Baseline" if abs(premium) < 1e-9 else f"+{premium:.1f}%"
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
            print(f"  Cheapest:      {cheapest[0].replace('_B200', '').replace('_', ' ').title()} (${cheapest[1]:.2f}/hr)")
            print(f"  Most Expensive: {most_expensive[0].replace('_B200', '').replace('_', ' ').title()} (${most_expensive[1]:.2f}/hr)")
            print(f"  Spread:        ${spread:.2f}/hr ({spread_pct:.1f}%)")
            print(f"\n  Strategy: Short {most_expensive[0].replace('_B200', '').replace('_', ' ').title()}, Long {cheapest[0].replace('_B200', '').replace('_', ' ').title()}")
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

        log_file = "b200_provider_price_updates.json"
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
        description="Update B200 provider-specific oracle prices (Part 2: CoreWeave & GCP)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:

  # Update CoreWeave & GCP with scraped prices from b200_normalized_prices.json
  python update_to_oracle_single_part2.py

  # Update specific providers with custom prices
  python update_to_oracle_single_part2.py --coreweave-b200 42.00 --gcp-b200 18.50

  # Set both providers to the same price
  python update_to_oracle_single_part2.py --all 5.00

  # Just show current prices (no updates)
  python update_to_oracle_single_part2.py --show-only

Environment Variables:
  SEPOLIA_RPC_URL              Ethereum RPC endpoint
  PRIVATE_KEY / ORACLE_UPDATER_PRIVATE_KEY
                              Wallet private key for signing transactions
  MULTI_ASSET_ORACLE_ADDRESS   MultiAssetOracle contract address
        """,
    )

    parser.add_argument("--coreweave-b200", type=float, help="CoreWeave B200 price (USD/hr) - overrides scraped price")
    parser.add_argument("--gcp-b200", type=float, help="Google Cloud B200 price (USD/hr) - overrides scraped price")
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
        updater = B200ProviderPriceUpdater(
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

    # Load effective prices from weighted index
    print("\n📊 Loading effective prices from b200_weighted_index.json...")
    scraped_prices = load_scraped_prices()

    # Determine prices to update
    prices: Dict[str, float] = {}

    if args.all is not None:
        # Set both to same price
        for asset_name in ASSET_IDS.keys():
            prices[asset_name] = args.all
    else:
        # Use CLI overrides or scraped prices
        prices["COREWEAVE_B200"] = (
            args.coreweave_b200
            if args.coreweave_b200 is not None
            else scraped_prices["COREWEAVE_B200"]
        )
        prices["GCP_B200"] = (
            args.gcp_b200 if args.gcp_b200 is not None else scraped_prices["GCP_B200"]
        )

    # Validate prices
    for asset_name, price in prices.items():
        if price <= 0:
            print(f"\nERROR: {asset_name} price must be greater than zero (got {price})")
            sys.exit(1)
        if price > 100:
            print(f"\nWARNING: {asset_name} price ${price:.2f}/hr seems unusually high")
            print("Expected range: $1-50/hour for B200 GPUs")

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
