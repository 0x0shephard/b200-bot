#!/usr/bin/env python3
"""
Master script to run all B200 GPU pricing scrapers
"""

import sys
import time
from typing import List, Tuple

# Import all scrapers
from aws_b200_scraper import AWSB200Scraper
from civo_b200_scraper import CivoB200Scraper
from runpod_b200_scraper import RunPodB200Scraper
from greenai_b200_scraper import GreenAIB200Scraper
from nebius_b200_scraper import NebiusB200Scraper
from vultr_b200_scraper import VultrB200Scraper
from coreweave_b200_scraper import CoreWeaveB200Scraper
from cirrascale_b200_scraper import CirrascaleB200Scraper
from crusoe_b200_scraper import CrusoeB200Scraper
from computeprices_b200_scraper import ComputePricesB200Scraper
from hpcai_b200_scraper import HPCAIB200Scraper
from gcp_b200_scraper import GCPB200Scraper

# Import normalization script
from normalize_b200_prices import B200PriceNormalizer

import json
import re


def run_scraper(scraper_class, name: str) -> Tuple[str, bool, dict]:
    """Run a single scraper and return results"""
    print("\n" + "=" * 80)
    print(f"🔄 Running {name} scraper...")
    print("=" * 80)

    try:
        scraper = scraper_class()
        prices = scraper.get_b200_prices()

        if prices and 'Error' not in prices:
            print(f"✅ {name} scraper completed successfully")
            return (name, True, prices)
        else:
            print(f"⚠️  {name} scraper completed with no results")
            return (name, False, prices)
    except Exception as e:
        print(f"❌ {name} scraper failed: {str(e)[:100]}")
        return (name, False, {})


def save_scraper_results(scraper_name: str, prices: dict):
    """Save scraper results to JSON file"""
    if not prices or 'Error' in prices:
        return

    # Generate filename based on scraper name
    filename = f"{scraper_name.lower().replace(' ', '_')}_b200_prices.json"

    # Create output structure
    output_data = {
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
        'provider': scraper_name,
        'providers': {
            scraper_name: {
                'name': scraper_name,
                'url': '',  # Will be set by individual scrapers
                'variants': {}
            }
        }
    }

    # Handle different price structures
    for variant, price in prices.items():
        price_match = re.search(r'\$([0-9.]+)', str(price))
        if price_match:
            price_num = float(price_match.group(1))

            output_data['providers'][scraper_name]['variants'][variant] = {
                'gpu_model': 'B200',
                'gpu_memory': '180GB',
                'price_per_hour': price_num,
                'currency': 'USD',
                'availability': 'on-demand'
            }

    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2)

    print(f"   💾 Results saved to: {filename}")


def main():
    """Run all B200 scrapers and generate normalized report"""
    print("🚀 B200 GPU Pricing - Master Scraper")
    print("=" * 80)
    print("Running all provider scrapers...")
    print()

    # Define all scrapers (12 providers with verified B200 pricing)
    scrapers = [
        # Original batch (5)
        (AWSB200Scraper, "AWS"),
        (CivoB200Scraper, "Civo"),
        (RunPodB200Scraper, "RunPod"),
        (GreenAIB200Scraper, "GreenAI Cloud"),
        (NebiusB200Scraper, "Nebius"),

        # Second batch (4)
        (VultrB200Scraper, "Vultr"),
        (CoreWeaveB200Scraper, "CoreWeave"),
        (CirrascaleB200Scraper, "Cirrascale"),
        (CrusoeB200Scraper, "Crusoe"),

        # Third batch (3)
        (ComputePricesB200Scraper, "ComputePrices"),
        (HPCAIB200Scraper, "HPC-AI"),
        (GCPB200Scraper, "Google Cloud"),
    ]

    results = []
    successful_count = 0

    # Run each scraper
    for scraper_class, name in scrapers:
        result = run_scraper(scraper_class, name)
        results.append(result)

        scraper_name, success, prices = result
        if success:
            successful_count += 1
            save_scraper_results(scraper_name, prices)

        # Small delay between scrapers to be polite to servers
        time.sleep(2)

    # Print summary
    print("\n" + "=" * 80)
    print("📊 SCRAPING SUMMARY")
    print("=" * 80)
    print(f"\n  Total Scrapers:     {len(scrapers)}")
    print(f"  Successful:         {successful_count}")
    print(f"  Failed/No Data:     {len(scrapers) - successful_count}")
    print()

    for name, success, prices in results:
        status = "✅" if success else "❌"
        count = len([p for p in prices.values() if 'Error' not in str(p)]) if success else 0
        print(f"  {status} {name:25s} ({count} variants found)")

    # Run normalization
    if successful_count > 0:
        print("\n" + "=" * 80)
        print("🔄 Running price normalization...")
        print("=" * 80)

        try:
            normalizer = B200PriceNormalizer()
            prices = normalizer.load_all_prices()

            if prices:
                normalized = normalizer.normalize_prices(prices)
                stats = normalizer.calculate_statistics(normalized)

                if stats:
                    normalizer.calculate_deviations(normalized, stats["average"])
                    normalizer.compare_with_h100(stats["average"])
                    normalizer.save_normalized_report(normalized, stats)

                print("\n✅ Normalization complete!")
            else:
                print("\n⚠️  No price files found for normalization")

        except Exception as e:
            print(f"\n❌ Normalization failed: {str(e)}")

    print("\n" + "=" * 80)
    print("✅ All operations complete!")
    print("=" * 80)


if __name__ == "__main__":
    main()
