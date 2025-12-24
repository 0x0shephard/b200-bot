#!/usr/bin/env python3
"""B200 GPU Oracle price updater script."""

import json
import os
import sys
from datetime import datetime, timezone
from typing import Tuple

from dotenv import load_dotenv
from eth_account import Account
from web3 import Web3

load_dotenv()

# Configuration
SEPOLIA_RPC_URL = os.getenv("SEPOLIA_RPC_URL") or "https://rpc.sepolia.org"
PRIVATE_KEY = os.getenv("ORACLE_UPDATER_PRIVATE_KEY") or os.getenv("PRIVATE_KEY")
MULTI_ASSET_ORACLE_ADDRESS = os.getenv("MULTI_ASSET_ORACLE_ADDRESS") or "0xB44d652354d12Ac56b83112c6ece1fa2ccEfc683"
PRICE_DECIMALS = int(os.getenv("ORACLE_DECIMALS") or "18")

# B200 Asset ID (keccak256("B200_HOURLY"))
B200_ASSET_ID = "0xc087ecb79f2df80d1dbf828d80ca18ff0b385e5806b3ec42da93e23eb0136348"

# MultiAssetOracle ABI (minimal subset for price updates)
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
        "name": "getPrice",
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
            {"name": "updatedAt", "type": "uint256", "internalType": "uint256"}
        ],
        "stateMutability": "view",
    },
    {
        "type": "function",
        "name": "isAssetRegistered",
        "inputs": [
            {"name": "assetId", "type": "bytes32", "internalType": "bytes32"}
        ],
        "outputs": [
            {"name": "", "type": "bool", "internalType": "bool"}
        ],
        "stateMutability": "view",
    },
]


class B200OraclePriceUpdater:
    """Update B200 GPU rental prices on the multi-asset oracle contract."""

    def __init__(self, rpc_url: str, private_key: str, contract_address: str, decimals: int):
        self.w3 = Web3(Web3.HTTPProvider(rpc_url))
        if not self.w3.is_connected():
            raise ConnectionError(f"Failed to connect to Sepolia RPC: {rpc_url}")

        self.account = Account.from_key(private_key)
        self.address = self.account.address
        self.contract = self.w3.eth.contract(
            address=Web3.to_checksum_address(contract_address),
            abi=MULTI_ASSET_ORACLE_ABI,
        )
        self.decimals = decimals

        balance_eth = self.w3.from_wei(self.w3.eth.get_balance(self.address), "ether")

        print("=" * 60)
        print("B200 ORACLE PRICE UPDATER")
        print("=" * 60)
        print(f"Connected to Sepolia testnet")
        print(f"   Chain ID: {self.w3.eth.chain_id}")
        print(f"   Latest block: {self.w3.eth.block_number}")
        print(f"   Updater address: {self.address}")
        print(f"   Balance: {balance_eth:.4f} ETH")
        print(f"   MultiAssetOracle: {contract_address}")
        print(f"   Price decimals: {self.decimals}")
        print("")

        # Check B200 asset registration
        is_registered = self.is_asset_registered()
        if is_registered:
            current_price = self.get_current_price()
            print(f"✓ B200_HOURLY asset is registered")
            print(f"   Current price: ${current_price:.6f}/hr")
        else:
            print("✗ B200_HOURLY asset NOT registered!")
            print("   Run the deployment script first to register the asset")
            sys.exit(1)
        print("")

    def _build_dynamic_fee(self) -> Tuple[int, int]:
        """Calculate dynamic gas fees."""
        base_fee = self.w3.eth.gas_price
        max_priority = self.w3.to_wei(1, "gwei")
        max_fee = max(base_fee * 2, max_priority * 2)
        return max_fee, max_priority

    def _send_transaction(self, func, gas_limit: int) -> Tuple[str, dict]:
        """Build, sign, and send a transaction to the blockchain."""
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

        if hasattr(signed, "raw_transaction"):
            raw_tx = signed.raw_transaction
        elif hasattr(signed, "rawTransaction"):
            raw_tx = signed.rawTransaction
        else:
            raw_tx = signed

        tx_hash = self.w3.eth.send_raw_transaction(raw_tx)
        receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=180)
        return tx_hash.hex(), dict(receipt)

    def is_asset_registered(self) -> bool:
        """Check if B200 asset is registered in the oracle."""
        try:
            return self.contract.functions.isAssetRegistered(B200_ASSET_ID).call()
        except Exception:
            return False

    def get_current_price(self) -> float:
        """Get current B200 price from the oracle."""
        try:
            price_raw = self.contract.functions.getPrice(B200_ASSET_ID).call()
            return price_raw / (10 ** self.decimals)
        except Exception:
            return 0.0

    def update_price(self, price_usd: float) -> str:
        """Update B200 price on the oracle."""
        price_scaled = int(price_usd * (10 ** self.decimals))
        current_price = self.get_current_price()

        print("=" * 60)
        print("UPDATING B200 PRICE")
        print("=" * 60)

        if current_price > 0:
            delta = price_usd - current_price
            change_pct = (delta / current_price) * 100
            print(f"Current B200 price: ${current_price:.6f}/hr")
            print(f"New B200 price:     ${price_usd:.6f}/hr")
            print(f"Change:             {delta:+.6f} ({change_pct:+.2f}%)")
        else:
            print(f"New B200 price: ${price_usd:.6f}/hr")

        print("")
        print("Sending transaction...")

        tx_hash, receipt = self._send_transaction(
            self.contract.functions.updatePrice(B200_ASSET_ID, price_scaled),
            gas_limit=100_000,
        )

        print(f"✓ Transaction confirmed: {tx_hash}")
        print(f"   Gas used: {receipt['gasUsed']:,}")
        print("")

        # Verify the update
        latest_price = self.get_current_price()
        if abs(latest_price - price_usd) < 0.000001:  # Account for rounding
            print(f"✓ On-chain price verified: ${latest_price:.6f}/hr")
        else:
            print(f"⚠ WARNING: On-chain price mismatch!")
            print(f"   Expected: ${price_usd:.6f}/hr")
            print(f"   Got: ${latest_price:.6f}/hr")

        return tx_hash

    def log_update(self, price_usd: float, tx_hash: str) -> None:
        """Log the update to a JSON file."""
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "asset": "B200_HOURLY",
            "price_usd": price_usd,
            "tx_hash": tx_hash,
            "block_number": self.w3.eth.block_number,
            "contract_address": MULTI_ASSET_ORACLE_ADDRESS,
            "network": "sepolia",
            "updater_address": self.address,
        }

        log_file = "b200_oracle_update_log.json"
        logs = []

        if os.path.exists(log_file):
            try:
                with open(log_file, "r", encoding="utf-8") as handle:
                    logs = json.load(handle)
                if not isinstance(logs, list):
                    logs = []
            except Exception:
                logs = []

        logs.append(log_entry)
        logs = logs[-100:]  # Keep last 100 entries

        try:
            with open(log_file, "w", encoding="utf-8") as handle:
                json.dump(logs, handle, indent=2)
            print(f"✓ Logged update to {log_file}")
        except Exception as exc:
            print(f"⚠ Failed to write log file: {exc}")


def main() -> None:
    """Main entry point for updating B200 GPU price."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Update B200 GPU hourly rental rate on MultiAssetOracle",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Update B200 price to $7.15/hour
  python scripts/update_b200_oracle_price.py 7.15

  # Update B200 price to $8.50/hour
  python scripts/update_b200_oracle_price.py 8.50

Note:
  - Requires PRIVATE_KEY or ORACLE_UPDATER_PRIVATE_KEY in .env
  - Requires sufficient Sepolia ETH for gas fees
  - B200 asset must be registered in the oracle first
        """,
    )
    parser.add_argument(
        "price",
        type=float,
        help="B200 hourly rental price in USD (e.g., 7.15)",
    )

    args = parser.parse_args()

    # Validate environment
    if not PRIVATE_KEY:
        print("ERROR: Private key not configured")
        print("Set ORACLE_UPDATER_PRIVATE_KEY or PRIVATE_KEY environment variable in .env")
        sys.exit(1)

    # Validate price
    if args.price <= 0:
        print(f"ERROR: Price must be > 0 (got {args.price})")
        sys.exit(1)

    if args.price > 100:
        print(f"WARNING: B200 price ${args.price:.2f}/hr seems unusually high")
        response = input("Continue anyway? (y/N): ")
        if response.lower() != "y":
            print("Aborted.")
            sys.exit(0)

    # Initialize updater
    try:
        updater = B200OraclePriceUpdater(
            rpc_url=SEPOLIA_RPC_URL,
            private_key=PRIVATE_KEY,
            contract_address=MULTI_ASSET_ORACLE_ADDRESS,
            decimals=PRICE_DECIMALS,
        )
    except Exception as exc:
        print(f"\nERROR: Failed to initialize updater: {exc}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    # Update price
    try:
        tx_hash = updater.update_price(args.price)
        updater.log_update(args.price, tx_hash)

        print("")
        print("=" * 60)
        print("SUCCESS! B200 PRICE UPDATED ON-CHAIN")
        print("=" * 60)
        print(f"   Transaction: {tx_hash}")
        print(f"   Etherscan: https://sepolia.etherscan.io/tx/{tx_hash}")
        print("=" * 60)
        sys.exit(0)
    except Exception as exc:
        print("")
        print("=" * 60)
        print("ERROR: PRICE UPDATE FAILED")
        print("=" * 60)
        print(f"   {exc}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
