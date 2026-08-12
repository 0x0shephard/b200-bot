#!/usr/bin/env python3
"""Small CuOracle commit/reveal client for ByteStrike Sepolia bots."""

import os
import time
from dataclasses import dataclass
from decimal import Decimal
from typing import Dict, Iterable, List, Optional, Tuple

from eth_account import Account
from web3 import Web3
from web3.exceptions import TimeExhausted


DEFAULT_CU_ORACLE_ADDRESS = "0x97f557594bA32e51c0eA215B1886111F24E957af"
DEFAULT_B200_ASSET_ID = "0xcebd53e2877b54ffddc8abbb4764a279df3df948dcc2b606db94e6aae8a80995"
DEFAULT_CHAIN_ID = 11155111
PRICE_DECIMALS = 18

DEFAULT_RPC_URLS = [
    "https://ethereum-sepolia-rpc.publicnode.com",
    "https://sepolia.drpc.org",
]


CU_ORACLE_ABI = [
    {
        "type": "function",
        "name": "owner",
        "inputs": [],
        "outputs": [{"name": "", "type": "address"}],
        "stateMutability": "view",
    },
    {
        "type": "function",
        "name": "allowedRoles",
        "inputs": [{"name": "", "type": "address"}],
        "outputs": [{"name": "", "type": "bool"}],
        "stateMutability": "view",
    },
    {
        "type": "function",
        "name": "supportedAssets",
        "inputs": [{"name": "", "type": "bytes32"}],
        "outputs": [{"name": "", "type": "bool"}],
        "stateMutability": "view",
    },
    {
        "type": "function",
        "name": "latestPrices",
        "inputs": [{"name": "", "type": "bytes32"}],
        "outputs": [
            {"name": "price", "type": "uint256"},
            {"name": "lastUpdatedAt", "type": "uint256"},
        ],
        "stateMutability": "view",
    },
    {
        "type": "function",
        "name": "getLatestPrice",
        "inputs": [{"name": "_assetId", "type": "bytes32"}],
        "outputs": [
            {
                "name": "",
                "type": "tuple",
                "components": [
                    {"name": "price", "type": "uint256"},
                    {"name": "lastUpdatedAt", "type": "uint256"},
                ],
            }
        ],
        "stateMutability": "view",
    },
    {
        "type": "function",
        "name": "minTimeInterval",
        "inputs": [],
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
    },
    {
        "type": "function",
        "name": "minCommitRevealDelay",
        "inputs": [],
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
    },
    {
        "type": "function",
        "name": "maxCommitAge",
        "inputs": [],
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
    },
    {
        "type": "function",
        "name": "lastCommitTimestamp",
        "inputs": [{"name": "", "type": "bytes32"}],
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
    },
    {
        "type": "function",
        "name": "commitPrice",
        "inputs": [
            {"name": "_assetId", "type": "bytes32"},
            {"name": "_commit", "type": "bytes32"},
        ],
        "outputs": [],
        "stateMutability": "nonpayable",
    },
    {
        "type": "function",
        "name": "updatePrices",
        "inputs": [
            {"name": "_assetId", "type": "bytes32"},
            {"name": "_price", "type": "uint256"},
            {"name": "_nonce", "type": "bytes32"},
        ],
        "outputs": [],
        "stateMutability": "nonpayable",
    },
]


@dataclass
class OracleUpdate:
    asset_name: str
    asset_id: str
    price_x18: int
    market: str = ""

    @property
    def price_usd(self) -> float:
        return self.price_x18 / 10**PRICE_DECIMALS


@dataclass
class OracleUpdateResult:
    asset_name: str
    asset_id: str
    market: str
    price_x18: int
    nonce: str
    commit_hash: str
    commit_tx_hash: str
    reveal_tx_hash: str
    commit_block: int
    reveal_block: int
    commit_timestamp: int


def price_to_x18(price_usd: float) -> int:
    return int(Decimal(str(price_usd)) * (Decimal(10) ** PRICE_DECIMALS))


def x18_to_usd(price_x18: int) -> float:
    return price_x18 / 10**PRICE_DECIMALS


def _clean_private_key(private_key: str) -> str:
    private_key = private_key.strip()
    if not private_key.startswith("0x"):
        private_key = f"0x{private_key}"
    return private_key


def _rpc_candidates(primary_rpc_url: Optional[str]) -> List[str]:
    candidates: List[str] = []
    if primary_rpc_url:
        candidates.append(primary_rpc_url)

    fallback_env = os.getenv("SEPOLIA_FALLBACK_RPC_URL", "")
    for item in fallback_env.split(","):
        item = item.strip()
        if item:
            candidates.append(item)

    candidates.extend(DEFAULT_RPC_URLS)

    deduped: List[str] = []
    for candidate in candidates:
        if candidate and candidate not in deduped:
            deduped.append(candidate)
    return deduped


class CuOracleClient:
    def __init__(
        self,
        rpc_url: Optional[str],
        private_key: str,
        contract_address: Optional[str] = None,
        chain_id: int = DEFAULT_CHAIN_ID,
    ) -> None:
        self.chain_id = chain_id
        self.account = Account.from_key(_clean_private_key(private_key))
        self.address = self.account.address
        self.w3, self.rpc_url = self._connect(rpc_url)
        self.contract_address = Web3.to_checksum_address(
            contract_address or DEFAULT_CU_ORACLE_ADDRESS
        )
        self.contract = self.w3.eth.contract(
            address=self.contract_address,
            abi=CU_ORACLE_ABI,
        )

        self.owner = self.contract.functions.owner().call()
        self.can_commit = (
            self.owner.lower() == self.address.lower()
            or self.contract.functions.allowedRoles(self.address).call()
        )
        self.can_reveal = self.owner.lower() == self.address.lower() or bool(
            self.contract.functions.allowedRoles(self.address).call()
        )

    def _connect(self, rpc_url: Optional[str]) -> Tuple[Web3, str]:
        errors: List[str] = []
        for candidate in _rpc_candidates(rpc_url):
            try:
                w3 = Web3(Web3.HTTPProvider(candidate, request_kwargs={"timeout": 30}))
                if not w3.is_connected():
                    errors.append(f"{candidate}: not connected")
                    continue
                if w3.eth.chain_id != self.chain_id:
                    errors.append(f"{candidate}: chain id {w3.eth.chain_id}")
                    continue
                return w3, candidate
            except Exception as exc:
                errors.append(f"{candidate}: {exc}")

        joined = "\n  ".join(errors) if errors else "no RPC URLs configured"
        raise ConnectionError(f"Failed to connect to Sepolia RPC:\n  {joined}")

    def print_context(self) -> None:
        balance_eth = self.w3.from_wei(
            self.w3.eth.get_balance(self.address),
            "ether",
        )
        print("=" * 70)
        print("BYTESTRIKE CUORACLE PRICE UPDATER")
        print("=" * 70)
        print(f"RPC: {self.rpc_url}")
        print(f"Chain ID: {self.w3.eth.chain_id}")
        print(f"Latest block: {self.w3.eth.block_number}")
        print(f"Updater address: {self.address}")
        print(f"Balance: {balance_eth:.6f} ETH")
        print(f"CuOracle: {self.contract_address}")
        print(f"Oracle owner: {self.owner}")
        print(f"Can commit: {self.can_commit}")
        print(f"Can reveal: {self.can_reveal}")
        print("=" * 70)

    def ensure_can_update(self) -> None:
        if not self.can_commit:
            raise PermissionError(
                f"{self.address} cannot commit prices. Grant the role or use the oracle owner key."
            )
        if not self.can_reveal:
            raise PermissionError(
                f"{self.address} is neither the CuOracle owner nor an allowed publisher role."
            )

    def is_supported_asset(self, asset_id: str) -> bool:
        return self.contract.functions.supportedAssets(asset_id).call()

    def get_latest_price(
        self,
        asset_id: str,
        block_identifier: Optional[int] = None,
    ) -> Tuple[int, int]:
        if block_identifier is None:
            price, last_updated = self.contract.functions.getLatestPrice(asset_id).call()
        else:
            price, last_updated = self.contract.functions.getLatestPrice(asset_id).call(
                block_identifier=block_identifier
            )
        return int(price), int(last_updated)

    def _build_fee_fields(self, multiplier_bps: int = 10_000) -> Dict[str, int]:
        priority_gwei = float(os.getenv("ORACLE_MAX_PRIORITY_FEE_GWEI", "0.05"))
        priority_fee = self.w3.to_wei(priority_gwei, "gwei")
        gas_price = self.w3.eth.gas_price
        latest_block = self.w3.eth.get_block("latest")
        base_fee = latest_block.get("baseFeePerGas", gas_price)
        max_fee = max(int(base_fee) * 2 + int(priority_fee), int(gas_price) + int(priority_fee))
        max_fee = (int(max_fee) * multiplier_bps) // 10_000
        priority_fee = (int(priority_fee) * multiplier_bps) // 10_000
        return {
            "maxFeePerGas": int(max_fee),
            "maxPriorityFeePerGas": int(priority_fee),
        }

    def _next_nonce(self) -> int:
        try:
            return self.w3.eth.get_transaction_count(self.address, "pending")
        except TypeError:
            return self.w3.eth.get_transaction_count(self.address)

    def _send_transaction(self, func, gas_limit: int, nonce: Optional[int] = None) -> Tuple[str, dict]:
        tx_nonce = self._next_nonce() if nonce is None else nonce
        timeout = int(os.getenv("ORACLE_TX_TIMEOUT_SECONDS", "300"))
        max_retries = int(os.getenv("ORACLE_TX_MAX_RETRIES", "4"))
        bump_bps = int(os.getenv("ORACLE_REPLACEMENT_FEE_BUMP_BPS", "1250"))

        for attempt in range(max_retries + 1):
            multiplier_bps = 10_000 + (attempt * bump_bps)
            tx = func.build_transaction(
                {
                    "from": self.address,
                    "nonce": tx_nonce,
                    "gas": gas_limit,
                    "chainId": self.chain_id,
                    **self._build_fee_fields(multiplier_bps=multiplier_bps),
                }
            )
            signed = self.account.sign_transaction(tx)
            raw_tx = getattr(signed, "raw_transaction", getattr(signed, "rawTransaction", signed))

            try:
                tx_hash = self.w3.eth.send_raw_transaction(raw_tx)
                receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=timeout)
                return tx_hash.hex(), dict(receipt)
            except TimeExhausted as exc:
                raise TimeoutError(
                    f"Transaction {tx_hash.hex()} was not mined after {timeout}s"
                ) from exc
            except Exception as exc:
                message = str(exc).lower()
                if "replacement transaction underpriced" in message and attempt < max_retries:
                    print(
                        "  RPC rejected tx as underpriced replacement; "
                        f"retrying nonce {tx_nonce} with higher fees..."
                    )
                    time.sleep(2)
                    continue
                if "nonce too low" in message and nonce is None and attempt < max_retries:
                    tx_nonce = self._next_nonce()
                    print(f"  RPC nonce moved; retrying with nonce {tx_nonce}...")
                    time.sleep(2)
                    continue
                raise

        raise RuntimeError("unreachable transaction retry state")

    def _sleep_until_commit_allowed(self, asset_id: str) -> None:
        last_commit = self.contract.functions.lastCommitTimestamp(asset_id).call()
        min_interval = self.contract.functions.minTimeInterval().call()
        latest_ts = self.w3.eth.get_block("latest")["timestamp"]
        ready_at = int(last_commit) + int(min_interval)
        if ready_at > latest_ts:
            wait_seconds = ready_at - int(latest_ts) + 1
            print(f"Waiting {wait_seconds}s for CuOracle minTimeInterval...")
            time.sleep(wait_seconds)

    def _commit_hash(self, price_x18: int, nonce: bytes) -> bytes:
        return Web3.solidity_keccak(["uint256", "bytes32"], [price_x18, nonce])

    def _verify_price(
        self,
        update: OracleUpdate,
        reveal_block: int,
        attempts: int = 5,
        delay_seconds: int = 3,
    ) -> Tuple[int, int]:
        for attempt in range(1, attempts + 1):
            try:
                price, last_updated = self.get_latest_price(
                    update.asset_id,
                    block_identifier=reveal_block,
                )
                if price == update.price_x18:
                    return price, last_updated
            except Exception:
                pass

            price, last_updated = self.get_latest_price(update.asset_id)
            if price == update.price_x18:
                return price, last_updated

            if attempt < attempts:
                time.sleep(delay_seconds)

        return self.get_latest_price(update.asset_id)

    def commit_and_reveal(
        self,
        updates: Iterable[OracleUpdate],
        verify: bool = True,
        reveal_wait_seconds: Optional[int] = None,
    ) -> List[OracleUpdateResult]:
        self.ensure_can_update()
        prepared = list(updates)
        if not prepared:
            print("No oracle updates to send.")
            return []

        min_delay = int(self.contract.functions.minCommitRevealDelay().call())
        configured_wait = int(os.getenv("ORACLE_REVEAL_WAIT_SECONDS", "3"))
        wait_seconds = max(min_delay, reveal_wait_seconds if reveal_wait_seconds is not None else configured_wait)

        pending = []
        print("Prepared CuOracle updates:")
        for update in prepared:
            if not self.is_supported_asset(update.asset_id):
                raise ValueError(f"{update.asset_name} asset is not supported: {update.asset_id}")
            current_price, last_updated = self.get_latest_price(update.asset_id)
            current_usd = x18_to_usd(current_price)
            delta_pct = 0.0
            if current_price > 0:
                delta_pct = ((update.price_x18 - current_price) / current_price) * 100
            label = f"{update.asset_name}"
            if update.market:
                label += f" ({update.market})"
            print(f"  {label}: ${current_usd:.6f}/hr -> ${update.price_usd:.6f}/hr ({delta_pct:+.2f}%)")
            if last_updated:
                age = int(time.time()) - int(last_updated)
                print(f"    Current commit timestamp age: {age}s")

        print("Committing prices...")
        for update in prepared:
            self._sleep_until_commit_allowed(update.asset_id)
            nonce = os.urandom(32)
            commit_hash = self._commit_hash(update.price_x18, nonce)
            tx_hash, receipt = self._send_transaction(
                self.contract.functions.commitPrice(update.asset_id, commit_hash),
                gas_limit=130_000,
            )
            print(f"  commit {update.asset_name}: {tx_hash} (gas {receipt['gasUsed']:,})")
            pending.append((update, nonce, commit_hash, tx_hash, receipt))

        print(f"Waiting {wait_seconds}s before reveal...")
        time.sleep(wait_seconds)

        print("Revealing prices...")
        results: List[OracleUpdateResult] = []
        for update, nonce, commit_hash, commit_tx_hash, commit_receipt in pending:
            tx_hash, receipt = self._send_transaction(
                self.contract.functions.updatePrices(
                    update.asset_id,
                    update.price_x18,
                    nonce,
                ),
                gas_limit=170_000,
            )
            print(f"  reveal {update.asset_name}: {tx_hash} (gas {receipt['gasUsed']:,})")

            verified_price, commit_timestamp = (0, 0)
            if verify:
                verified_price, commit_timestamp = self._verify_price(
                    update,
                    reveal_block=int(receipt["blockNumber"]),
                )
                if verified_price != update.price_x18:
                    raise RuntimeError(
                        f"Verification failed for {update.asset_name}: "
                        f"expected {update.price_x18}, got {verified_price}"
                    )
                print(
                    f"  verified {update.asset_name}: "
                    f"${x18_to_usd(verified_price):.6f}/hr at commit timestamp {commit_timestamp}"
                )

            results.append(
                OracleUpdateResult(
                    asset_name=update.asset_name,
                    asset_id=update.asset_id,
                    market=update.market,
                    price_x18=update.price_x18,
                    nonce=f"0x{nonce.hex()}",
                    commit_hash=commit_hash.hex(),
                    commit_tx_hash=commit_tx_hash,
                    reveal_tx_hash=tx_hash,
                    commit_block=int(commit_receipt["blockNumber"]),
                    reveal_block=int(receipt["blockNumber"]),
                    commit_timestamp=int(commit_timestamp),
                )
            )

        return results
