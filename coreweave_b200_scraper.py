#!/usr/bin/env python3
"""
CoreWeave B200 GPU Pricing Scraper
Extracts B200 pricing from coreweave.com using multiple methods
"""

import requests
from bs4 import BeautifulSoup
import re
import json
import time
from typing import Dict, Optional
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException


class CoreWeaveB200Scraper:
    """Scraper for CoreWeave B200 pricing"""

    def __init__(self):
        self.name = "CoreWeave"
        self.base_url = "https://www.coreweave.com"
        self.pricing_url = "https://www.coreweave.com/pricing"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
        }

    def get_b200_prices(self) -> Dict[str, str]:
        """Main method to extract B200 prices"""
        print(f"🔍 Fetching {self.name} B200 pricing...")
        print("=" * 80)

        b200_prices = {}

        # Try multiple methods
        methods = [
            ("API Endpoint", self._try_api),
            ("Pricing Page", self._try_pricing_page),
            ("GPU Products Page", self._try_gpu_products),
            ("Selenium Scraper", self._try_selenium_scraper),
        ]

        for method_name, method_func in methods:
            print(f"\n📋 Method: {method_name}")
            try:
                prices = method_func()
                if prices:
                    b200_prices.update(prices)
                    print(f"   ✅ Found {len(prices)} B200 prices!")
                    # Return on first success
                    return b200_prices
                else:
                    print(f"   ❌ No prices found")
            except Exception as e:
                print(f"   ⚠️  Error: {str(e)[:100]}")

        if not b200_prices:
            print("\n❌ All methods failed - unable to extract B200 pricing")
            return {'Error': 'Unable to fetch B200 pricing from CoreWeave'}

        return b200_prices

    def _try_api(self) -> Dict[str, str]:
        """Try CoreWeave API endpoints"""
        b200_prices = {}

        api_urls = [
            "https://www.coreweave.com/api/pricing",
            "https://api.coreweave.com/pricing",
            "https://www.coreweave.com/api/v1/pricing",
            "https://api.coreweave.com/v1/gpu-pricing",
        ]

        for api_url in api_urls:
            try:
                print(f"    Trying API: {api_url}")
                response = requests.get(api_url, headers=self.headers, timeout=20)

                if response.status_code == 200:
                    try:
                        data = response.json()
                        print(f"      ✓ Got JSON response")

                        found_prices = self._extract_from_json(data)
                        if found_prices:
                            b200_prices.update(found_prices)
                            return b200_prices

                    except json.JSONDecodeError:
                        print(f"      ⚠️  Response is not JSON")
                elif response.status_code == 404:
                    print(f"      Status 404")
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
            "https://www.coreweave.com/pricing",
            "https://www.coreweave.com/gpu-cloud-pricing",
            "https://coreweave.com/pricing",
        ]

        for url in urls:
            try:
                print(f"    Trying: {url}")
                response = requests.get(url, headers=self.headers, timeout=20)

                if response.status_code == 200:
                    soup = BeautifulSoup(response.content, 'html.parser')
                    html_content = str(soup)
                    text_content = soup.get_text()

                    if 'B200' not in text_content and 'b200' not in text_content.lower():
                        print(f"      ⚠️  Page doesn't contain B200 references")
                        continue

                    print(f"      ✓ Page contains B200 data")

                    # Look for B200 pricing patterns
                    b200_patterns = [
                        (r'B200[^\$\n]{0,200}\$([0-9.]+)/hr', 'B200 (CoreWeave)'),
                        (r'B200[^\$\n]{0,200}\$([0-9.]+)\s*per\s*hour', 'B200 (CoreWeave)'),
                        (r'NVIDIA\s+B200[^\$\n]{0,200}\$([0-9.]+)', 'B200 (CoreWeave)'),
                        (r'\$([0-9.]+)/hr[^\n]{0,200}B200', 'B200 (CoreWeave)'),
                    ]

                    for pattern, default_variant in b200_patterns:
                        matches = re.findall(pattern, text_content, re.IGNORECASE | re.DOTALL)
                        for match in matches:
                            try:
                                price = float(match)
                                if 1.0 <= price <= 100.0:
                                    variant_name = default_variant

                                    if variant_name not in b200_prices:
                                        b200_prices[variant_name] = f"${price:.2f}/hr"
                                        print(f"        Pattern ✓ {variant_name} = ${price:.2f}/hr")
                            except ValueError:
                                continue

                    if b200_prices:
                        return b200_prices

                    # Try structured extraction
                    found_prices = self._extract_from_page_structure(soup)
                    if found_prices:
                        b200_prices.update(found_prices)
                        return b200_prices

                    # Try embedded JSON
                    found_prices = self._extract_from_embedded_json(html_content)
                    if found_prices:
                        b200_prices.update(found_prices)
                        return b200_prices

                else:
                    print(f"      Status {response.status_code}")

            except Exception as e:
                print(f"      Error: {str(e)[:50]}...")
                continue

        return b200_prices

    def _try_gpu_products(self) -> Dict[str, str]:
        """Try to extract from GPU products page"""
        b200_prices = {}

        urls = [
            "https://www.coreweave.com/gpu-cloud",
            "https://www.coreweave.com/products",
        ]

        for url in urls:
            try:
                print(f"    Trying: {url}")
                response = requests.get(url, headers=self.headers, timeout=20)

                if response.status_code == 200:
                    soup = BeautifulSoup(response.content, 'html.parser')
                    text_content = soup.get_text()

                    if 'B200' in text_content or 'b200' in text_content.lower():
                        print(f"      ✓ Page contains B200 data")

                        patterns = [
                            (r'B200[^\$]{0,200}\$([0-9.]+)', 'B200 (CoreWeave)'),
                        ]

                        for pattern, variant in patterns:
                            matches = re.findall(pattern, text_content, re.IGNORECASE | re.DOTALL)
                            for match in matches:
                                try:
                                    price = float(match)
                                    if 1.0 <= price <= 100.0 and variant not in b200_prices:
                                        b200_prices[variant] = f"${price:.2f}/hr"
                                        print(f"        Pattern ✓ {variant} = ${price:.2f}/hr")
                                except ValueError:
                                    continue

                        if b200_prices:
                            return b200_prices

            except Exception as e:
                print(f"      Error: {str(e)[:50]}...")
                continue

        return b200_prices

    def _extract_from_json(self, data, path="") -> Dict[str, str]:
        """Recursively search JSON for B200 pricing"""
        prices = {}

        if isinstance(data, dict):
            if 'name' in data or 'model' in data or 'gpu' in data or 'type' in data:
                name = data.get('name', data.get('model', data.get('gpu', data.get('type', ''))))

                if isinstance(name, str) and ('b200' in name.lower() or 'B200' in name):
                    print(f"        Found B200 entry: {name}")

                    price_fields = ['price', 'pricePerHour', 'hourlyPrice', 'cost', 'rate', 'priceHr']

                    for field in price_fields:
                        if field in data:
                            price_val = data[field]

                            if isinstance(price_val, (int, float)) and 1.0 < price_val < 100:
                                prices[f'B200 ({name})'] = f"${price_val:.2f}/hr"
                                print(f"        ✓ Found price: ${price_val:.2f}/hr")
                                return prices

            for key, value in data.items():
                if isinstance(value, (dict, list)):
                    nested_prices = self._extract_from_json(value, f"{path}.{key}")
                    if nested_prices:
                        prices.update(nested_prices)
                        if prices:
                            return prices

        elif isinstance(data, list):
            for i, item in enumerate(data):
                if isinstance(item, (dict, list)):
                    nested_prices = self._extract_from_json(item, f"{path}[{i}]")
                    if nested_prices:
                        prices.update(nested_prices)
                        if prices:
                            return prices

        return prices

    def _extract_from_page_structure(self, soup: BeautifulSoup) -> Dict[str, str]:
        """Extract B200 pricing from structured HTML elements"""
        prices = {}

        pricing_items = soup.find_all(['div', 'tr', 'section'], class_=re.compile(r'(pricing|gpu|card|price)', re.I))

        print(f"      📋 Found {len(pricing_items)} pricing items")

        for item in pricing_items:
            item_text = item.get_text(separator=' ', strip=True)

            if 'B200' in item_text or 'b200' in item_text.lower():
                price_matches = re.findall(r'\$([0-9.]+)', item_text)

                for price_str in price_matches:
                    try:
                        price = float(price_str)

                        if 1.0 <= price <= 100.0:
                            variant_name = "B200 (CoreWeave)"

                            if variant_name not in prices:
                                prices[variant_name] = f"${price:.2f}/hr"
                                print(f"        Item ✓ {variant_name} = ${price:.2f}/hr")
                    except ValueError:
                        continue

        return prices

    def _extract_from_embedded_json(self, html_content: str) -> Dict[str, str]:
        """Extract B200 prices from embedded JSON in HTML"""
        prices = {}

        json_patterns = [
            r'<script[^>]*>.*?({.*?pricing.*?})</script>',
            r'data-pricing=["\']({.*?})["\']',
            r'window\.__PRICING__\s*=\s*({.*?});',
            r'window\.__NEXT_DATA__\s*=\s*({.*?});',
        ]

        for pattern in json_patterns:
            matches = re.findall(pattern, html_content, re.DOTALL | re.IGNORECASE)
            for match in matches:
                try:
                    data = json.loads(match)
                    found_prices = self._extract_from_json(data)
                    if found_prices:
                        prices.update(found_prices)
                        return prices
                except json.JSONDecodeError:
                    continue

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
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--window-size=1920,1080')
            chrome_options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')

            driver = webdriver.Chrome(options=chrome_options)

            try:
                print("    Loading pricing page...")
                driver.get(self.pricing_url)

                print("    Waiting for dynamic content to load...")
                time.sleep(5)

                page_source = driver.page_source
                soup = BeautifulSoup(page_source, 'html.parser')

                print("    ✓ Page loaded, extracting prices...")

                text_content = soup.get_text()

                if 'B200' in text_content or 'b200' in text_content.lower():
                    patterns = [
                        (r'B200[^\$]{0,200}\$([0-9.]+)/hr', 'B200 (CoreWeave)'),
                        (r'B200[^\$]{0,200}\$([0-9.]+)\s*per\s*hour', 'B200 (CoreWeave)'),
                        (r'\$([0-9.]+)/hr[^\n]{0,100}B200', 'B200 (CoreWeave)'),
                    ]

                    for pattern, variant in patterns:
                        matches = re.findall(pattern, text_content, re.IGNORECASE | re.DOTALL)
                        for match in matches:
                            try:
                                price = float(match)
                                if 1.0 <= price <= 100.0 and variant not in b200_prices:
                                    b200_prices[variant] = f"${price:.2f}/hr"
                                    print(f"        Selenium ✓ {variant} = ${price:.2f}/hr")
                            except ValueError:
                                continue

            finally:
                driver.quit()
                print("    WebDriver closed")

        except WebDriverException as e:
            print(f"      ⚠️  Selenium WebDriver error: {str(e)[:100]}")
        except Exception as e:
            print(f"      ⚠️  Error: {str(e)[:100]}")

        return b200_prices


def main():
    """Test the CoreWeave B200 scraper"""
    print("🚀 CoreWeave B200 GPU Pricing Scraper")
    print("=" * 80)
    print()

    scraper = CoreWeaveB200Scraper()
    b200_prices = scraper.get_b200_prices()

    print("\n" + "=" * 80)
    print("🎯 RESULTS - CoreWeave B200 Pricing")
    print("=" * 80)

    if b200_prices and 'Error' not in b200_prices:
        print(f"\n✅ Successfully extracted {len(b200_prices)} B200 price variants:\n")

        for variant, price in sorted(b200_prices.items()):
            print(f"  • {variant:50s} {price}")

        # Save to JSON
        output_file = "coreweave_b200_prices.json"
        output_data = {
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'provider': 'CoreWeave',
            'providers': {
                'CoreWeave': {
                    'name': 'CoreWeave',
                    'url': 'https://www.coreweave.com',
                    'variants': {}
                }
            }
        }

        for variant, price in b200_prices.items():
            price_match = re.search(r'\$([0-9.]+)', price)
            if price_match:
                price_num = float(price_match.group(1))

                output_data['providers']['CoreWeave']['variants'][variant] = {
                    'gpu_model': 'B200',
                    'gpu_memory': '180GB',
                    'price_per_hour': price_num,
                    'currency': 'USD',
                    'availability': 'on-demand'
                }

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2)

        print(f"\n💾 Results saved to: {output_file}")

    else:
        print("\n❌ Failed to extract B200 pricing")
        if 'Error' in b200_prices:
            print(f"   Error: {b200_prices['Error']}")

    print("\n" + "=" * 80)


if __name__ == "__main__":
    main()
