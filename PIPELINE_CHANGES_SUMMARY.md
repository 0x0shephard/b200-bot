# Pipeline Changes Summary

## Overview

The B200 bot now pushes the weighted B200 index into the deployed ByteStrike Sepolia `CuOracle` using the protocol's commit/reveal flow.

## Current On-Chain Target

- CuOracle: `0x97f557594bA32e51c0eA215B1886111F24E957af`
- Market: `B200-PERP-V2`
- Asset symbol: `B200`
- Asset ID: `0xcebd53e2877b54ffddc8abbb4764a279df3df948dcc2b606db94e6aae8a80995`

## Provider-Specific B200 Markets

| Market | Asset ID | vAMM | Oracle Adapter |
| --- | --- | --- | --- |
| `AWS-B200-PERP` | `0xd4cb0c395efb880df5c098c103eb6dfd23ee89a322b22e473e29c476f5240bd4` | `0x4ECd2da8789dd067833Acab3F4BF4857e8A0ca6B` | `0xDBA6Ce71E0d0cC7E9EE83B9cf57F173bF6a66e71` |
| `ORACLE-B200-PERP` | `0x9bf58bdbcbc9ddfd61f5add09163bfa8392f346eaf046baebcf3474867d92d41` | `0x0E9bF74e394219004CbD2b7d6Dd3443418d116E9` | `0x7F021ca464deE0446C18934639DA9cc98Baa3317` |
| `COREWEAVE-B200-PERP` | `0x7cfd459019cab14dcd5a85a668482047debede1f13dfb31be53aeb279791325b` | `0x283Eb1C70c1ddFed588EFFF0B20A129Bd366CB96` | `0xaD37F69ccB279A69E5037E5aF80B749b245e2780` |
| `GCP-B200-PERP` | `0x76d0a44da38fe3b87efb5f30986a5be867c6685bbaf1a26fb154c63a6fc23f0c` | `0x4c77B2c6ab65f21108B5AB24A0d73e66E1C7BC0e` | `0x02b9bbA6194b3eC79f7501fe8095A4f34BcA95c6` |

See `DEPLOYED_ADDRESSES.md` for the full address table.

## Files Modified

### `.github/workflows/scrape-and-upload.yml`

- Renamed the workflow to reference ByteStrike CuOracle.
- Changed the schedule to every 30 minutes so the B200 adapter stays below its 1 hour max-age.
- Replaced old `MultiAssetOracle` env vars with `CU_ORACLE_ADDRESS`.
- Pushes aggregate B200 plus provider-specific `ORACLE_B200`, `AWS_B200`, `COREWEAVE_B200`, and `GCP_B200` prices.

### `cu_oracle_client.py`

- Added a standalone Sepolia CuOracle client.
- Supports RPC fallback, EIP-1559 fee fields, commit/reveal delay, owner/role checks, and post-reveal verification.

### `update_to_oracle.py`

- Replaced direct `updatePrice` calls with:
  1. `commitPrice(assetId, keccak256(abi.encodePacked(priceX18, nonce)))`
  2. wait for the reveal delay
  3. `updatePrices(assetId, priceX18, nonce)`
- Logs both commit and reveal transaction hashes to `b200_oracle_update_log.json`.

### `provider_cu_oracle.py`

- Pushes provider-specific B200 prices through the same CuOracle commit/reveal flow.
- Defaults to the deployed Sepolia provider asset IDs, while still allowing `*_B200_ASSET_ID` environment overrides.

## Required GitHub Secrets

- `SUPABASE_URL`
- `SUPABASE_SERVICE_KEY`
- `ORACLE_UPDATER_PRIVATE_KEY`

Recommended:

- `SEPOLIA_RPC_URL`
- `CU_ORACLE_ADDRESS` only if overriding the default deployed oracle

## Operational Caveat

`CuOracle.latestPrices[assetId].lastUpdatedAt` is the commit block timestamp, not the reveal timestamp. The workflow should keep running comfortably under the deployed adapter's 1 hour max age.
