# GitHub Actions Setup Guide

## Overview

This guide explains how to configure GitHub Actions to automatically scrape B200 GPU prices and upload them to Supabase and the ByteStrike CuOracle on Ethereum Sepolia.

## Workflow File

The workflow is located at: `.github/workflows/scrape-and-upload.yml`

## Setup Steps

### 1. Configure GitHub Secrets

You need to add your Supabase and Oracle credentials as GitHub repository secrets:

1. Go to your GitHub repository
2. Click on **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret**
4. Add the following secrets:

#### Supabase Secrets

| Secret Name | Description | Example |
|------------|-------------|---------|
| `SUPABASE_URL` | Your Supabase project URL | `https://xxxxx.supabase.co` |
| `SUPABASE_SERVICE_KEY` | Your Supabase service role key | `eyJhbGciOiJIUzI1Ni...` |

**Finding your Supabase credentials:**
- Log in to [Supabase Dashboard](https://app.supabase.com)
- Select your project
- Go to **Settings** → **API**
- Copy the **Project URL** (for `SUPABASE_URL`)
- Copy the **service_role** key (for `SUPABASE_SERVICE_KEY`)

⚠️ **Important:** Use the `service_role` key (not the `anon` key) to ensure write permissions.

#### Oracle (Blockchain) Secrets

| Secret Name | Required | Description | Example |
|------------|----------|-------------|---------|
| `SEPOLIA_RPC_URL` | Recommended | Sepolia testnet RPC endpoint | `https://sepolia.infura.io/v3/YOUR_KEY` |
| `ORACLE_UPDATER_PRIVATE_KEY` | **Yes** | Private key for the CuOracle owner wallet | `0x1234...abcd` |
| `CU_ORACLE_ADDRESS` | No | ByteStrike CuOracle address | `0x97f557594bA32e51c0eA215B1886111F24E957af` |

**Setting up Oracle credentials:**

1. **Get a Wallet Private Key:**
   - Create a new wallet specifically for oracle updates (use MetaMask, etc.)
   - Export the private key (including the `0x` prefix)
   - ⚠️ **NEVER share or commit this private key**
   - Fund this wallet with Sepolia ETH for gas fees ([Sepolia Faucet](https://sepoliafaucet.com/))

2. **Get an RPC URL (Optional):**
   - Get a free RPC URL from [Infura](https://infura.io/) or [Alchemy](https://www.alchemy.com/)
   - The bot has a public Sepolia fallback, but a dedicated provider is more reliable.

3. **Oracle Contract Address (Optional):**
   - Default value is pre-configured: `0x97f557594bA32e51c0eA215B1886111F24E957af`
   - Only override if using a custom CuOracle deployment

### 1.1. Deployed ByteStrike Markets

The workflow pushes the aggregate B200 index and the four deployed provider-specific B200 markets. The full table is in `DEPLOYED_ADDRESSES.md`.

| Market | Asset Symbol | Asset ID |
| --- | --- | --- |
| `B200-PERP-V2` | `B200` | `0xcebd53e2877b54ffddc8abbb4764a279df3df948dcc2b606db94e6aae8a80995` |
| `AWS-B200-PERP` | `AWS-B200` | `0xd4cb0c395efb880df5c098c103eb6dfd23ee89a322b22e473e29c476f5240bd4` |
| `ORACLE-B200-PERP` | `ORACLE-B200` | `0x9bf58bdbcbc9ddfd61f5add09163bfa8392f346eaf046baebcf3474867d92d41` |
| `COREWEAVE-B200-PERP` | `COREWEAVE-B200` | `0x7cfd459019cab14dcd5a85a668482047debede1f13dfb31be53aeb279791325b` |
| `GCP-B200-PERP` | `GCP-B200` | `0x76d0a44da38fe3b87efb5f30986a5be867c6685bbaf1a26fb154c63a6fc23f0c` |

### 2. Set Up Supabase Table

Make sure you have a table named `b200_index_prices` in your Supabase database with the following schema:

```sql
CREATE TABLE b200_index_prices (
  id BIGSERIAL PRIMARY KEY,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  timestamp TEXT NOT NULL,
  index_price DECIMAL(10, 2) NOT NULL,
  hyperscaler_component DECIMAL(10, 2),
  non_hyperscaler_component DECIMAL(10, 2),
  metadata JSONB
);
```

### 3. Workflow Triggers

The workflow runs automatically in three scenarios:

#### a. **Manual Trigger**
- Go to **Actions** tab in your GitHub repository
- Select **Scrape B200 Prices and Upload to Supabase**
- Click **Run workflow**
- Select the branch and click **Run workflow**

#### b. **Scheduled Run** (Every 30 minutes)
- Runs frequently enough to keep the deployed `CuOracleAdapter` under its 1 hour max-age check.
- Modify the cron schedule in `.github/workflows/scrape-and-upload.yml` if needed:
  ```yaml
  schedule:
    - cron: '*/30 * * * *'
  ```

Common cron schedules:
- Every hour: `'0 * * * *'`
- Every 12 hours: `'0 */12 * * *'`
- Daily at midnight: `'0 0 * * *'`
- Every Monday at 9 AM: `'0 9 * * 1'`

#### c. **Push to Branches** (Optional)
- Triggers on push to `master` or `update1` branches
- Remove this trigger if you don't want it:
  ```yaml
  # Remove or comment out this section
  # push:
  #   branches:
  #     - master
  #     - update1
  ```

## Workflow Steps

The workflow performs the following:

1. **Checkout code** - Gets the latest repository code
2. **Set up Python 3.11** - Installs Python environment
3. **Install Chrome & ChromeDriver** - For Selenium-based scrapers
4. **Install dependencies** - Installs required Python packages (including web3, eth-account)
5. **Run scrapers** - Executes `run_all_scrapers.py`
   - Scrapes all 13 provider websites
   - Generates individual JSON files
   - Creates normalized pricing report
   - Calculates weighted index
6. **Verify outputs** - Checks that JSON files were created
7. **Push to Supabase** - Executes `push_to_supabase.py`
   - Validates pricing data
   - Uploads to Supabase database
8. **Push to CuOracle** - Executes `update_to_oracle.py`
   - Extracts weighted index price from JSON
   - Connects to Ethereum Sepolia testnet
   - Commits the B200 price hash
   - Waits for the configured commit/reveal delay
   - Reveals the B200 price to `B200-PERP-V2`
   - Logs commit and reveal transaction hashes
9. **Push provider-specific B200 prices** - Executes `update_to_oracle_single.py` and `update_to_oracle_single_part2.py`
   - Pushes Oracle, AWS, CoreWeave, and GCP B200 prices to their deployed provider-specific markets
   - Uses the deployed default asset IDs from `provider_cu_oracle.py`
   - Logs commit and reveal transaction hashes to `b200_provider_price_updates.json`
10. **Upload artifacts** - Saves JSON files and oracle logs for 7 days (for debugging)

## Monitoring

### View Workflow Runs
- Go to **Actions** tab in your repository
- Click on a workflow run to see detailed logs
- Check each step for success/failure status

### Download Artifacts
- Click on a completed workflow run
- Scroll to **Artifacts** section
- Download `b200-pricing-data-XXX.zip` to inspect JSON files

### Check Supabase Data
- Log in to Supabase Dashboard
- Go to **Table Editor**
- Select `b200_index_prices` table
- View the latest entries

### Check Oracle Data (Blockchain)
- Visit [Sepolia Etherscan](https://sepolia.etherscan.io/)
- Enter your oracle updater wallet address to see transaction history
- View the CuOracle contract at the configured address
- Check recent commit and reveal transactions for successful price updates
- Review the `b200_oracle_update_log.json` artifact for transaction details

## Troubleshooting

### Workflow fails with "Supabase credentials not found"
- Verify secrets are set correctly in repository settings
- Check secret names match exactly: `SUPABASE_URL` and `SUPABASE_SERVICE_KEY`

### Workflow fails with "Oracle credentials not found" or "Private key not configured"
- Verify `ORACLE_UPDATER_PRIVATE_KEY` secret is set in GitHub repository settings
- Ensure the private key includes the `0x` prefix
- Check that the wallet has sufficient Sepolia ETH for gas fees

### "Failed to connect to Sepolia RPC"
- Public RPCs may be rate-limited or down
- Set `SEPOLIA_RPC_URL` secret with an Infura or Alchemy RPC endpoint
- Test RPC connectivity manually first

### "CuOracle.updatePrices is owner-only"
- The current contract only allows the owner to reveal prices
- Use the CuOracle owner key for `ORACLE_UPDATER_PRIVATE_KEY`, or transfer ownership to the bot wallet

### "Insufficient funds for gas"
- The updater wallet needs Sepolia ETH for transaction gas fees
- Get free Sepolia ETH from: [sepoliafaucet.com](https://sepoliafaucet.com/)
- Check wallet balance in workflow logs

### "B200 asset is not supported"
- The new protocol uses asset symbol `B200`
- The Sepolia asset ID is `0xcebd53e2877b54ffddc8abbb4764a279df3df948dcc2b606db94e6aae8a80995`
- Run the market deployment/registration script before using this workflow

### Provider-specific B200 asset is not supported
- Confirm the bot is using the current provider asset IDs from `DEPLOYED_ADDRESSES.md`
- The deployed defaults are already hardcoded in `provider_cu_oracle.py`
- Only set `AWS_B200_ASSET_ID`, `ORACLE_B200_ASSET_ID`, `COREWEAVE_B200_ASSET_ID`, or `GCP_B200_ASSET_ID` if overriding the deployed Sepolia addresses

### Scrapers fail or return no data
- Some providers may be temporarily unavailable
- Check individual scraper logs in workflow output
- The workflow uses `continue-on-error: false` to stop if scrapers fail

### Price validation fails (Supabase)
- The script validates new prices against historical averages (±25% tolerance)
- If validation fails, check if there's a genuine market change or scraping error
- Adjust tolerance in `push_to_supabase.py` line 114 if needed

### Chrome/Selenium errors
- The workflow automatically installs Chrome and ChromeDriver
- If issues persist, check the "Set up Chrome" step logs

### Transaction fails or gets stuck
- Check Sepolia network status at [sepolia.etherscan.io](https://sepolia.etherscan.io/)
- Increase gas limit if needed (current default: 100,000 gas)
- Review transaction logs in workflow output for error messages

## Customization

### Change Python Version
Edit `.github/workflows/scrape-and-upload.yml`:
```yaml
- name: Set up Python
  uses: actions/setup-python@v5
  with:
    python-version: '3.11'  # Change to 3.9, 3.10, 3.12, etc.
```

### Add Notifications
Add a notification step (e.g., Slack, email, Discord):
```yaml
- name: Notify on success
  if: success()
  uses: some-notification-action@v1
  with:
    message: "B200 scraping completed successfully!"
```

### Disable Artifacts Upload
Comment out or remove the "Upload artifacts" step to save storage:
```yaml
# - name: Upload artifacts
#   if: always()
#   uses: actions/upload-artifact@v4
#   ...
```

## Cost Considerations

- **GitHub Actions:** 2,000 free minutes/month for public repos; check usage in Settings → Billing
- **Supabase:** Free tier includes 500 MB database; monitor usage in Supabase Dashboard
- **Sepolia Testnet Gas:** Free testnet ETH from faucets; each oracle update costs ~0.001-0.003 Sepolia ETH
- **RPC Endpoints:** Free tier available on Infura/Alchemy (optional, default RPC is public and free)
- The workflow runs for ~5-10 minutes per execution

**Estimated Costs per Run:**
- GitHub Actions: ~5-10 minutes (free on public repos)
- Supabase: ~1 database insert (free tier: unlimited reads/writes)
- Oracle Update: ~0.002 Sepolia ETH per transaction (free from faucet)

**Monthly Costs (running every 30 minutes = ~1440 times/month):**
- GitHub Actions: depends on scraper runtime and may exceed the public free tier
- Supabase: ~1440 inserts/month (low storage impact)
- Oracle Gas: two Sepolia transactions per run (commit + reveal)

## Security Best Practices

✅ **Do:**
- Use GitHub Secrets for all credentials (API keys, private keys)
- Use `service_role` key for Supabase write access
- Create a dedicated wallet for oracle updates (don't use personal wallets)
- Regularly rotate Supabase keys and monitor wallet activity
- Review workflow logs for sensitive data leaks
- Keep minimal ETH in the oracle updater wallet (only what's needed for gas)
- Monitor transaction history on Etherscan

❌ **Don't:**
- Commit `.env` files with credentials or private keys
- Share `service_role` keys or private keys publicly
- Use `anon` keys for data writing
- Use personal wallets with significant funds for automated updates
- Commit private keys to version control (even in deleted commits)
- Share GitHub Action logs that may contain sensitive data

## Next Steps

1. **Set up GitHub Secrets** (see step 1)
   - Add Supabase credentials (`SUPABASE_URL`, `SUPABASE_SERVICE_KEY`)
   - Add Oracle credentials (`ORACLE_UPDATER_PRIVATE_KEY`)
   - Optionally add `SEPOLIA_RPC_URL` and `CU_ORACLE_ADDRESS`

2. **Create Supabase table** (see step 2)
   - Set up the `b200_index_prices` table schema

3. **Set up Oracle wallet**
   - Create a new wallet for oracle updates
   - Fund it with Sepolia ETH from a faucet
   - Ensure the B200 asset is registered in the oracle contract

4. **Commit and push the workflow file**
   ```bash
   git add .github/workflows/scrape-and-upload.yml requirements.txt
   git commit -m "Wire B200 bot to ByteStrike CuOracle"
   git push
   ```

5. **Run workflow manually to test**
   - Go to Actions tab → "Scrape B200 Prices and Upload to Supabase & ByteStrike CuOracle"
   - Click "Run workflow"
   - Monitor the logs for any errors

6. **Verify the uploads**
   - Check Supabase table for new entry
   - Check Etherscan for oracle update transaction
   - Review the artifacts for JSON files and logs

7. **Monitor scheduled runs**
   - Workflow runs automatically every 30 minutes
   - Check Actions tab for execution history
   - Monitor wallet balance and refill Sepolia ETH as needed

---

**Questions or Issues?**
- Check workflow logs in Actions tab
- Review Supabase dashboard for data
- Ensure all secrets are configured correctly
