# B200 GPU Pricing Aggregator

A comprehensive Python-based tool for scraping, collecting, and normalizing NVIDIA B200 GPU pricing across multiple cloud providers.

## Overview

This project monitors and compares hourly rental prices for B200 GPUs (NVIDIA's latest Blackwell architecture with 180GB HBM3e memory) from **11 different cloud service providers**. It helps users identify the most cost-effective options for renting B200 GPUs.

## Supported Providers

### Original Batch (5)
1. **AWS** - EC2 P6-B200 instances - $9.66/hr
2. **Civo** - Civo Cloud B200 offerings - $27.92/hr
3. **RunPod** - On-demand B200 instances - $5.98/hr
4. **GreenAI Cloud** - EU-based B200 hosting - $3.75/hr
5. **Nebius** - NVIDIA HGX B200 instances - $5.50/hr

### Second Batch (4)
6. **Vultr** - Cloud GPU B200 instances - $2.89/hr
7. **CoreWeave** - Specialized GPU cloud - $42.00/hr
8. **Cirrascale** - GPU cloud solutions - $17.00/hr
9. **Crusoe** - Energy-efficient cloud computing - $4.29/hr

### Third Batch (2)
10. **ComputePrices** - Price comparison aggregator - $2.49/hr
11. **HPC-AI** - High-performance computing cloud - **$1.49/hr (CHEAPEST!)**

## Current Pricing Summary

Based on latest scraper results (Dec 2025):

| Rank | Provider | Price/GPU/hr | Notes |
|------|----------|--------------|-------|
| 🥇 1 | **HPC-AI** | **$1.49** | **Cheapest - Best value!** |
| 🥈 2 | ComputePrices | $2.49 | Price aggregator |
| 🥉 3 | Vultr | $2.89 | Great value |
| 4 | GreenAI Cloud | $3.75 | EU-based |
| 5 | Crusoe | $4.29 | Energy-efficient |
| 6 | Nebius | $5.50 | HGX B200 |
| 7 | RunPod | $5.98 | On-demand |
| 8 | AWS | $9.66 | Multiple regions |
| 9 | Cirrascale | $17.00 | Enterprise |
| 10 | Civo | $27.92 | - |
| 11 | CoreWeave | $42.00 | Most expensive |

**Statistics:**
- **Cheapest**: $1.49/hr (HPC-AI)
- **Most Expensive**: $42.00/hr (CoreWeave)
- **Average**: $11.18/hr
- **Median**: $5.50/hr
- **Price Range**: $1.49 - $42.00/hr (28x difference!)

## Features

- **Multi-method scraping**: Each scraper tries 3-5 different methods (API → Web scraping → Selenium)
- **Price normalization**: Standardizes all prices to per-GPU/hour for fair comparison
- **Statistical analysis**: Min, max, average, median, and deviation calculations
- **Robust error handling**: Graceful degradation with fallback methods
- **Automated discovery**: Normalization script automatically finds all provider data

## Installation

### Prerequisites
- Python 3.8+
- Chrome/Chromium (for Selenium scrapers)
- ChromeDriver (for Selenium scrapers)

### Install Dependencies

```bash
pip install -r requirements.txt
```

Or manually:

```bash
pip install requests beautifulsoup4 selenium
```

## Usage

### Run Individual Scrapers

Run any individual scraper:

```bash
python3 aws_b200_scraper.py
python3 vultr_b200_scraper.py
python3 coreweave_b200_scraper.py
# ... etc
```

Each scraper will:
1. Try multiple methods to fetch pricing
2. Display progress and results in the terminal
3. Save results to `{provider}_b200_prices.json`

### Run All Scrapers at Once

Use the master script to run all 12 scrapers sequentially:

```bash
python3 run_all_scrapers.py
```

This will:
1. Run all provider scrapers
2. Save individual JSON files for each provider
3. Automatically run price normalization
4. Generate a comprehensive pricing report

### Price Normalization

Run the normalization script separately:

```bash
python3 normalize_b200_prices.py
```

This generates:
- Comparative analysis across all providers
- Statistical summaries (min, max, average, median)
- Price deviation analysis
- Performance/cost efficiency metrics
- Output: `b200_normalized_prices.json`

## Project Structure

```
b200/
├── requirements.txt                   # Python dependencies
├── run_all_scrapers.py               # Master script (11 providers)
├── normalize_b200_prices.py          # Price normalization and analysis
├── venv/                             # Virtual environment
│
├── Provider Scrapers (11 total):
│   ├── aws_b200_scraper.py           # AWS EC2 P6-B200
│   ├── civo_b200_scraper.py          # Civo Cloud
│   ├── runpod_b200_scraper.py        # RunPod
│   ├── greenai_b200_scraper.py       # GreenAI Cloud
│   ├── nebius_b200_scraper.py        # Nebius
│   ├── vultr_b200_scraper.py         # Vultr
│   ├── coreweave_b200_scraper.py     # CoreWeave
│   ├── cirrascale_b200_scraper.py    # Cirrascale
│   ├── crusoe_b200_scraper.py        # Crusoe
│   ├── computeprices_b200_scraper.py # ComputePrices
│   └── hpcai_b200_scraper.py         # HPC-AI
│
└── Output Files (JSON):
    ├── *_b200_prices.json            # Individual provider data (11 files)
    └── b200_normalized_prices.json   # Aggregated report
```

## Output Format

### Individual Provider Files

Each scraper generates a JSON file with this structure:

```json
{
  "timestamp": "2025-12-23 12:00:00",
  "provider": "Vultr",
  "providers": {
    "Vultr": {
      "name": "Vultr",
      "url": "https://www.vultr.com",
      "variants": {
        "B200 (Vultr)": {
          "gpu_model": "B200",
          "gpu_memory": "180GB",
          "price_per_hour": 5.98,
          "currency": "USD",
          "availability": "on-demand"
        }
      }
    }
  }
}
```

### Normalized Report

The normalization script generates a comprehensive report:

```json
{
  "timestamp": "2025-12-23 12:05:00",
  "base_model": {
    "name": "NVIDIA B200",
    "memory_gb": 180,
    "architecture": "Blackwell"
  },
  "statistics": {
    "count": 12,
    "min": 3.75,
    "max": 27.92,
    "average": 10.56,
    "median": 5.98,
    "cheapest_provider": "GreenAI Cloud",
    "most_expensive_provider": "Civo"
  },
  "providers": { ... }
}
```

## Scraper Architecture

Each scraper follows a consistent pattern:

1. **Multi-method fallback**:
   - Method 1: API endpoints (fastest, most reliable)
   - Method 2: HTML page scraping with BeautifulSoup
   - Method 3: Selenium browser automation (for JavaScript-heavy pages)
   - Fallback: Known/cached pricing data

2. **Price validation**:
   - Checks for reasonable price ranges ($1-100/hr for B200)
   - Filters out invalid or malformed data

3. **Error handling**:
   - Graceful degradation if methods fail
   - Detailed logging of errors and progress
   - User-friendly status indicators (✅ ❌ ⚠️)

## Customization

### Adding a New Provider

1. Copy an existing scraper as a template
2. Update the class name, URLs, and scraping logic
3. Follow the naming convention: `{provider}_b200_scraper.py`
4. The normalization script will automatically discover it

### Adjusting Price Ranges

Edit the price validation in each scraper:

```python
if 1.0 <= price <= 100.0:  # Adjust these values
    b200_prices[variant_name] = f"${price:.2f}/hr"
```

## Known Limitations

- **Selenium dependency**: Some scrapers require Chrome/ChromeDriver
- **Rate limiting**: Running all scrapers rapidly may trigger rate limits
- **Dynamic pricing**: Prices change frequently; data may be stale
- **Availability**: Not all providers may have B200 GPUs available yet
- **Regional variation**: Some providers have different pricing by region

## Troubleshooting

### Selenium WebDriver Errors

Install ChromeDriver:

```bash
# macOS
brew install chromedriver

# Ubuntu/Debian
sudo apt-get install chromium-chromedriver

# Or download from: https://chromedriver.chromium.org/
```

### Module Not Found Errors

Ensure all dependencies are installed:

```bash
pip install -r requirements.txt
```

### No Prices Found

Some providers may not have B200 pricing publicly available yet. The scraper will:
- Try all fallback methods
- Report "No prices found" if unsuccessful
- Continue with other providers

## Contributing

To add a new provider:
1. Create a new scraper following the existing pattern
2. Test it individually first
3. Add it to `run_all_scrapers.py`
4. Update this README

## Performance Benchmarks

B200 relative performance (used in cost efficiency calculations):
- **B200**: 1.0x (baseline)
- **H200**: 0.75x
- **H100**: 0.50x (B200 is ~2x faster)
- **A100**: 0.33x

## License

This project is for research and comparison purposes.

## Disclaimer

Pricing data is scraped from public provider websites and may not be 100% accurate or up-to-date. Always verify prices on the provider's official website before making purchasing decisions.
