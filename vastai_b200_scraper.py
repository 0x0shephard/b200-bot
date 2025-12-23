#!/usr/bin/env python3
"""
Vast.ai B200 GPU Pricing Scraper
Extracts B200 pricing from vast.ai using multiple methods
"""

import requests
from bs4 import BeautifulSoup
import re
import json
import time
from typing import Dict, Optional
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import WebDriverException


class VastAIB200Scraper:
    """Scraper for Vast.ai B200 pricing"""

    def __init__(self):
        self.name = "Vast.ai"
        self.base_url = "https://vast.ai"
        self.pricing_url = "https://vast.ai/pricing"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        }

    def get_b200_prices(self) -> Dict[str, str]:
        """Main method to extract B200 prices"""
        print(f"🔍 Fetching {self.name} B200 pricing...")
        print("=" * 80)

        b200_prices = {}

        methods = [
            ("API Endpoint", self._try_api),
            ("Pricing Page", self._try_pricing_page),
            ("Selenium Scraper", self._try_selenium_scraper),
        ]

        for method_name, method_func in methods:
            print(f"\n📋 Method: {method_name}")
            try:
                prices = method_func()
                if prices:
                    b200_prices.update(prices)
                    print(f"   ✅ Found {len(prices)} B200 prices!")
                    return b200_prices
                else:
                    print(f"   ❌ No prices found")
            except Exception as e:
                print(f"   ⚠️  Error: {str(e)[:100]}")

        if not b200_prices:
            print("\n❌ All methods failed - unable to extract B200 pricing")
            return {'Error': 'Unable to fetch B200 pricing from Vast.ai'}

        return b200_prices

    def _try_api(self) -> Dict[str, str]:
        """Try Vast.ai API endpoints"""
        b200_prices = {}

        api_urls = [
            "https://console.vast.ai/api/v0/",
            "https://vast.ai/api/pricing",
        ]

        for api_url in api_urls:
            try:
                print(f"    Trying API: {api_url}")
                response = requests.get(api_url, headers=self.headers, timeout=20)

                if response.status_code == 200:
                    try:
                        data = response.json()
                        print(f"      ✓ Got JSON response")

                        # Search for B200 in JSON
                        found_prices = self._extract_from_json(data)
                        if found_prices:
                            b200_prices.update(found_prices)
                            return b200_prices
                    except json.JSONDecodeError:
                        print(f"      ⚠️  Response is not JSON")
                else:
                    print(f"      Status {response.status_code}")

            except Exception as e:
                print(f"      Error: {str(e)[:50]}...")
                continue

        return b200_prices

    def _try_pricing_page(self) -> Dict[str, str]:
        """Try to extract prices from pricing page"""
        b200_prices = {}

        urls = [
            "https://vast.ai/pricing",
            "https://cloud.vast.ai/templates/",
        ]

        for url in urls:
            try:
                print(f"    Trying: {url}")
                response = requests.get(url, headers=self.headers, timeout=20)

                if response.status_code == 200:
                    soup = BeautifulSoup(response.content, 'html.parser')
                    text_content = soup.get_text()

                    if 'B200' not in text_content and 'b200' not in text_content.lower():
                        print(f"      ⚠️  Page doesn't contain B200 references")
                        continue

                    print(f"      ✓ Page contains B200 data")

                    patterns = [
                        (r'B200[^\$\n]{0,200}\$([0-9.]+)', 'B200 (Vast.ai)'),
                        (r'\$([0-9.]+)/hr[^\n]{0,100}B200', 'B200 (Vast.ai)'),
                    ]

                    for pattern, variant in patterns:
                        matches = re.findall(pattern, text_content, re.IGNORECASE | re.DOTALL)
                        for match in matches:
                            try:
                                price = float(match)
                                if 0.1 <= price <= 100.0 and variant not in b200_prices:
                                    b200_prices[variant] = f"${price:.2f}/hr"
                                    print(f"        Pattern ✓ {variant} = ${price:.2f}/hr")
                            except ValueError:
                                continue

                    if b200_prices:
                        return b200_prices

                else:
                    print(f"      Status {response.status_code}")

            except Exception as e:
                print(f"      Error: {str(e)[:50]}...")
                continue

        return b200_prices

    def _extract_from_json(self, data, path="") -> Dict[str, str]:
        """Recursively search JSON for B200 pricing"""
        prices = {}

        if isinstance(data, dict):
            for key, value in data.items():
                if isinstance(key, str) and 'b200' in key.lower():
                    if isinstance(value, (int, float)) and 0.1 < value < 100:
                        prices['B200 (Vast.ai)'] = f"${value:.2f}/hr"
                        return prices
                if isinstance(value, (dict, list)):
                    nested_prices = self._extract_from_json(value, f"{path}.{key}")
                    if nested_prices:
                        return nested_prices

        elif isinstance(data, list):
            for i, item in enumerate(data):
                if isinstance(item, (dict, list)):
                    nested_prices = self._extract_from_json(item, f"{path}[{i}]")
                    if nested_prices:
                        return nested_prices

        return prices

    def _try_selenium_scraper(self) -> Dict[str, str]:
        """Use Selenium to scrape JavaScript-loaded pricing"""
        b200_prices = {}

        try:
            print("    Setting up Selenium WebDriver...")

            chrome_options = Options()
            chrome_options.add_argument('--headless')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')

            driver = webdriver.Chrome(options=chrome_options)

            try:
                driver.get(self.pricing_url)
                time.sleep(5)

                page_source = driver.page_source
                soup = BeautifulSoup(page_source, 'html.parser')
                text_content = soup.get_text()

                if 'B200' in text_content or 'b200' in text_content.lower():
                    price_match = re.search(r'B200[^\$\n]{0,200}\$([0-9.]+)', text_content, re.IGNORECASE)
                    if price_match:
                        price = float(price_match.group(1))
                        if 0.1 <= price <= 100.0:
                            b200_prices['B200 (Vast.ai)'] = f"${price:.2f}/hr"
                            print(f"        Selenium ✓ B200 (Vast.ai) = ${price:.2f}/hr")

            finally:
                driver.quit()

        except Exception as e:
            print(f"      ⚠️  Error: {str(e)[:100]}")

        return b200_prices


def main():
    """Test the Vast.ai B200 scraper"""
    scraper = VastAIB200Scraper()
    b200_prices = scraper.get_b200_prices()

    if b200_prices and 'Error' not in b200_prices:
        output_file = "vastai_b200_prices.json"
        output_data = {
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'provider': 'Vast.ai',
            'providers': {
                'Vast.ai': {
                    'name': 'Vast.ai',
                    'url': 'https://vast.ai',
                    'variants': {}
                }
            }
        }

        for variant, price in b200_prices.items():
            price_match = re.search(r'\$([0-9.]+)', price)
            if price_match:
                price_num = float(price_match.group(1))
                output_data['providers']['Vast.ai']['variants'][variant] = {
                    'gpu_model': 'B200',
                    'gpu_memory': '180GB',
                    'price_per_hour': price_num,
                    'currency': 'USD',
                    'availability': 'marketplace'
                }

        with open(output_file, 'w') as f:
            json.dump(output_data, f, indent=2)


if __name__ == "__main__":
    main()
