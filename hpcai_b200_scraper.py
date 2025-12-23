#!/usr/bin/env python3
"""
HPC-AI B200 GPU Pricing Scraper
"""

import requests
from bs4 import BeautifulSoup
import re
import json
import time
from typing import Dict
from selenium import webdriver
from selenium.webdriver.chrome.options import Options


class HPCAIB200Scraper:
    def __init__(self):
        self.name = "HPC-AI"
        self.base_url = "https://www.hpc-ai.com"
        self.pricing_url = "https://www.hpc-ai.com/"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        }

    def get_b200_prices(self) -> Dict[str, str]:
        print(f"🔍 Fetching {self.name} B200 pricing...")
        print("=" * 80)

        methods = [
            ("Homepage/Pricing", self._try_pricing_page),
            ("Selenium", self._try_selenium),
        ]

        for method_name, method_func in methods:
            print(f"\n📋 Method: {method_name}")
            try:
                prices = method_func()
                if prices:
                    print(f"   ✅ Found {len(prices)} B200 prices!")
                    return prices
                print(f"   ❌ No prices found")
            except Exception as e:
                print(f"   ⚠️  Error: {str(e)[:100]}")

        return {'Error': 'Unable to fetch B200 pricing'}

    def _try_pricing_page(self) -> Dict[str, str]:
        try:
            response = requests.get(self.pricing_url, headers=self.headers, timeout=20)
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                text = soup.get_text()

                if 'b200' not in text.lower():
                    return {}

                print(f"      ✓ Page contains B200 data")

                patterns = [
                    (r'B200[^\$\n]{0,200}\$([0-9.]+)/hr', 'B200 (HPC-AI)'),
                    (r'B200[^\$\n]{0,200}\$([0-9.]+)\s*per\s*hour', 'B200 (HPC-AI)'),
                    (r'\$([0-9.]+)/hr[^\n]{0,100}B200', 'B200 (HPC-AI)'),
                ]

                for pattern, variant in patterns:
                    matches = re.findall(pattern, text, re.IGNORECASE | re.DOTALL)
                    for match in matches:
                        try:
                            price = float(match)
                            if 1.0 <= price <= 100.0:
                                print(f"        ✓ {variant} = ${price:.2f}/hr")
                                return {variant: f"${price:.2f}/hr"}
                        except ValueError:
                            pass
        except Exception as e:
            print(f"      Error: {str(e)[:50]}")
        return {}

    def _try_selenium(self) -> Dict[str, str]:
        try:
            print("    Setting up Selenium...")
            chrome_options = Options()
            chrome_options.add_argument('--headless')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')

            driver = webdriver.Chrome(options=chrome_options)
            driver.get(self.pricing_url)
            time.sleep(5)

            text = driver.page_source
            driver.quit()

            if 'b200' in text.lower():
                match = re.search(r'B200[^\$\n]{0,200}\$([0-9.]+)', text, re.IGNORECASE)
                if match:
                    price = float(match.group(1))
                    if 1.0 <= price <= 100.0:
                        variant = 'B200 (HPC-AI)'
                        print(f"        Selenium ✓ {variant} = ${price:.2f}/hr")
                        return {variant: f"${price:.2f}/hr"}
        except Exception as e:
            print(f"      Error: {str(e)[:50]}")
        return {}


def main():
    scraper = HPCAIB200Scraper()
    prices = scraper.get_b200_prices()

    if prices and 'Error' not in prices:
        output_file = "hpcai_b200_prices.json"
        output_data = {
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'provider': 'HPC-AI',
            'providers': {
                'HPC-AI': {
                    'name': 'HPC-AI',
                    'url': 'https://www.hpc-ai.com',
                    'variants': {}
                }
            }
        }

        for variant, price in prices.items():
            price_match = re.search(r'\$([0-9.]+)', price)
            if price_match:
                price_num = float(price_match.group(1))
                output_data['providers']['HPC-AI']['variants'][variant] = {
                    'gpu_model': 'B200',
                    'gpu_memory': '180GB',
                    'price_per_hour': price_num,
                    'currency': 'USD',
                    'availability': 'on-demand'
                }

        with open(output_file, 'w') as f:
            json.dump(output_data, f, indent=2)
        print(f"\n💾 Saved to: {output_file}")


if __name__ == "__main__":
    main()
