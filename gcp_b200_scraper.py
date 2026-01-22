#!/usr/bin/env python3
"""
Google Cloud Platform (GCP) B200 GPU Price Scraper
Extracts B200 pricing from Google Cloud A4 VM instances

GCP offers B200 GPUs in:
- A4 VMs: 8 x B200 GPUs
- A4X VMs: 72 x B200 GPUs (GB200 NVL72)

Reference: https://cloud.google.com/compute/gpus-pricing
"""

import requests
from bs4 import BeautifulSoup
import re
import json
import time
from typing import Dict, Optional


class GCPB200Scraper:
    """Scraper for Google Cloud Platform B200 GPU pricing"""
    
    def __init__(self):
        self.name = "Google Cloud"
        self.base_urls = [
            "https://cloud.google.com/compute/gpus-pricing",
            "https://cloud.google.com/compute/vm-instance-pricing",
        ]
        # Vantage.sh URLs for multiple GCP regions - A4 instances have B200 GPUs
        self.vantage_regions = [
            ("us-central1", "https://instances.vantage.sh/gcp/a4-ultragpu-8g?region=us-central1"),
            ("us-east4", "https://instances.vantage.sh/gcp/a4-ultragpu-8g?region=us-east4"),
            ("us-west1", "https://instances.vantage.sh/gcp/a4-ultragpu-8g?region=us-west1"),
            ("europe-west4", "https://instances.vantage.sh/gcp/a4-ultragpu-8g?region=europe-west4"),
            ("asia-east1", "https://instances.vantage.sh/gcp/a4-ultragpu-8g?region=asia-east1"),
        ]
        self.vantage_base = "https://instances.vantage.sh/gcp/a4-ultragpu-8g"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
        }
    
    def get_b200_prices(self) -> Dict[str, str]:
        """Main method to extract B200 prices from GCP - multi-region for volatility"""
        print(f"🔍 Fetching {self.name} B200 pricing (multi-region)...")
        print("=" * 80)
        
        b200_prices = {}
        
        # Try multiple methods - Vantage multi-region first for volatility
        methods = [
            ("Vantage Multi-Region Pricing", self._try_vantage_multi_region),
            ("GCP Pricing API", self._try_gcp_pricing_api),
            ("GPU Pricing Page Scraping", self._try_pricing_page),
            ("Selenium Scraper", self._try_selenium_scraper),
        ]
        
        for method_name, method_func in methods:
            print(f"\n📋 Method: {method_name}")
            try:
                prices = method_func()
                if prices and self._validate_prices(prices):
                    b200_prices.update(prices)
                    print(f"   ✅ Found {len(prices)} B200 prices!")
                    break
                else:
                    print(f"   ❌ No valid prices found")
            except Exception as e:
                print(f"   ⚠️  Error: {str(e)[:100]}")
                continue
        
        if not b200_prices:
            print("\n❌ All live methods failed - no fallback data (live data only mode)")
            return {}
        
        print(f"\n✅ Final extraction: {len(b200_prices)} B200 price variants")
        return b200_prices
    
    def _validate_prices(self, prices: Dict[str, str]) -> bool:
        """Validate that prices are in a reasonable range for B200 GPUs (per-GPU)"""
        if not prices:
            return False
        
        for variant, price_str in prices.items():
            if 'Error' in variant:
                continue
            try:
                price_match = re.search(r'([0-9.]+)', price_str)
                if price_match:
                    price = float(price_match.group(1))
                    # Per-GPU B200 pricing should be $5-25/hr after normalization
                    if 5 < price < 30:
                        return True
            except:
                continue
        return False
    
    def _try_vantage_multi_region(self) -> Dict[str, str]:
        """Fetch B200 prices from multiple GCP regions via Vantage.sh for volatility"""
        b200_prices = {}
        
        print(f"    Fetching prices from {len(self.vantage_regions)} GCP regions...")
        
        for region_code, url in self.vantage_regions:
            try:
                response = requests.get(url, headers=self.headers, timeout=15)
                
                if response.status_code == 200:
                    soup = BeautifulSoup(response.content, 'html.parser')
                    text_content = soup.get_text()
                    
                    # Look for pricing patterns
                    price_patterns = [
                        r'\$([0-9]+\.?[0-9]*)\s*(?:per\s+hour|/hr|/hour)',
                        r'On.?Demand[:\s]+\$([0-9]+\.?[0-9]*)',
                        r'hourly[:\s]+\$([0-9]+\.?[0-9]*)',
                        r'\$([0-9]+\.[0-9]+)',
                    ]
                    
                    for pattern in price_patterns:
                        matches = re.findall(pattern, text_content, re.IGNORECASE)
                        for match in matches:
                            try:
                                price = float(match)
                                # Instance price for 8 B200 GPUs ~$60-120/hr
                                if 50 < price < 180:
                                    per_gpu_price = price / 8
                                    region_name = region_code.replace('-', ' ').title()
                                    variant_name = f"A4 B200 ({region_name})"
                                    b200_prices[variant_name] = f"${per_gpu_price:.2f}/hr"
                                    print(f"      ✓ {region_code}: ${price:.2f}/instance → ${per_gpu_price:.2f}/GPU")
                                    break
                                # Already per-GPU price
                                elif 5 < price < 25:
                                    region_name = region_code.replace('-', ' ').title()
                                    variant_name = f"A4 B200 ({region_name})"
                                    b200_prices[variant_name] = f"${price:.2f}/hr"
                                    print(f"      ✓ {region_code}: ${price:.2f}/GPU")
                                    break
                            except ValueError:
                                continue
                        if region_code.replace('-', ' ').title() in str(b200_prices):
                            break
                            
            except Exception as e:
                print(f"      ⚠️ {region_code}: Error - {str(e)[:30]}")
                continue
        
        if b200_prices:
            print(f"    Found prices from {len(b200_prices)} regions")
        
        return b200_prices
    
    def _try_gcp_pricing_api(self) -> Dict[str, str]:
        """Try GCP Pricing API endpoints"""
        b200_prices = {}
        
        # GCP Cloud Billing API endpoints
        api_urls = [
            "https://cloudbilling.googleapis.com/v1/services/6F81-5844-456A/skus",  # Compute Engine
        ]
        
        for api_url in api_urls:
            try:
                print(f"    Trying API: {api_url}")
                # Note: Would need API key for full access
                # Here we're just checking accessibility
                response = requests.head(api_url, headers=self.headers, timeout=10)
                
                if response.status_code == 200 or response.status_code == 401:
                    print(f"      ⚠️  API accessible but requires authentication")
                else:
                    print(f"      Status {response.status_code}")
                        
            except Exception as e:
                print(f"      Error: {str(e)[:50]}...")
                continue
        
        return b200_prices
    
    def _try_pricing_page(self) -> Dict[str, str]:
        """Scrape GCP pricing pages for B200 prices"""
        b200_prices = {}
        
        for url in self.base_urls:
            try:
                print(f"    Trying: {url}")
                response = requests.get(url, headers=self.headers, timeout=20)
                
                if response.status_code == 200:
                    soup = BeautifulSoup(response.content, 'html.parser')
                    text_content = soup.get_text()
                    html_content = str(soup)
                    
                    print(f"      Content length: {len(text_content)}")
                    
                    # Check for B200 or A4 VM mentions
                    if ('B200' in text_content or 'b200' in text_content.lower() or 
                        'A4' in text_content or 'a4' in text_content.lower()):
                        print(f"      ✓ Found B200/A4 content")
                        
                        # Extract from tables
                        found_prices = self._extract_from_tables(soup)
                        if found_prices:
                            b200_prices.update(found_prices)
                            return b200_prices
                        
                        # Extract from text patterns
                        found_prices = self._extract_from_text(text_content)
                        if found_prices:
                            b200_prices.update(found_prices)
                            return b200_prices
                    else:
                        print(f"      ⚠️  No B200/A4 content found")
                else:
                    print(f"      Status {response.status_code}")
                    
            except Exception as e:
                print(f"      Error: {str(e)[:50]}...")
                continue
        
        return b200_prices
    
    def _extract_from_tables(self, soup: BeautifulSoup) -> Dict[str, str]:
        """Extract B200 prices from HTML tables - handles 8-GPU instance pricing"""
        prices = {}
        
        tables = soup.find_all('table')
        print(f"      Found {len(tables)} tables")
        
        for table in tables:
            table_text = table.get_text()
            
            # Look for A4 VM or B200 mentions
            if not ('B200' in table_text or 'A4' in table_text or 'Blackwell' in table_text or 
                    'a4-' in table_text.lower() or 'nvidia-b200' in table_text.lower()):
                continue
            
            print(f"      📋 Processing table with B200/A4 data")
            
            rows = table.find_all('tr')
            for row in rows:
                cells = row.find_all(['td', 'th'])
                row_text = ' '.join([cell.get_text().strip() for cell in cells])
                
                # Check for B200/A4/accelerator rows
                if ('B200' in row_text or 'A4' in row_text or 'a4-' in row_text.lower() or
                    'nvidia-b200' in row_text.lower() or 'accelerator' in row_text.lower()) and '$' in row_text:
                    print(f"         Row: {row_text[:150]}")
                    
                    # Extract all prices from the row
                    price_matches = re.findall(r'\$([0-9.]+)', row_text)
                    
                    for price_str in price_matches:
                        try:
                            instance_price = float(price_str)
                            
                            # GCP A4 VMs have 8 x B200 GPUs
                            # Instance prices ~$80-200/hr → divide by 8 for per-GPU
                            if 50 < instance_price < 250:
                                per_gpu_price = instance_price / 8
                                variant_name = "A4 B200 (Google Cloud)"
                                if variant_name not in prices:
                                    prices[variant_name] = f"${per_gpu_price:.2f}/hr"
                                    print(f"        Table ✓ {variant_name} = ${per_gpu_price:.2f}/hr (from ${instance_price:.2f}/instance ÷ 8 GPUs)")
                            # Also accept already per-GPU prices
                            elif 5 < instance_price < 30:
                                variant_name = "A4 B200 (Google Cloud)"
                                if variant_name not in prices:
                                    prices[variant_name] = f"${instance_price:.2f}/hr"
                                    print(f"        Table ✓ {variant_name} = ${instance_price:.2f}/hr")
                        except ValueError:
                            continue
        
        return prices
    
    def _extract_from_text(self, text_content: str) -> Dict[str, str]:
        """Extract B200 prices from text content - handles 8-GPU instance pricing"""
        prices = {}
        
        # GCP pricing patterns for A4 VMs with B200
        # Looking for patterns like "$88.92 / 1 hour" near B200/A4 mentions
        
        # Pattern to find price mentions
        price_patterns = [
            r'a4-.*?\$([0-9.]+)',
            r'nvidia-b200.*?\$([0-9.]+)',
            r'B200.*?\$([0-9.]+)',
            r'Blackwell.*?\$([0-9.]+)',
            r'A4.*?\$([0-9.]+)',
            r'\$([0-9.]+).*?(?:per|/)?\s*(?:1\s+)?hour',
        ]
        
        for pattern in price_patterns:
            matches = re.findall(pattern, text_content, re.IGNORECASE | re.DOTALL)
            
            for price_str in matches:
                try:
                    instance_price = float(price_str)
                    
                    # Check if this is an 8-GPU instance price (~$80-200/hr)
                    if 50 < instance_price < 250:
                        per_gpu_price = instance_price / 8
                        variant_name = "A4 B200 (Google Cloud)"
                        if variant_name not in prices:
                            prices[variant_name] = f"${per_gpu_price:.2f}/hr"
                            print(f"        Pattern ✓ {variant_name} = ${per_gpu_price:.2f}/hr (from ${instance_price:.2f}/instance ÷ 8 GPUs)")
                            return prices  # Found valid price, return immediately
                    # Already per-GPU price
                    elif 5 < instance_price < 30:
                        variant_name = "A4 B200 (Google Cloud)"
                        if variant_name not in prices:
                            prices[variant_name] = f"${instance_price:.2f}/hr"
                            print(f"        Pattern ✓ {variant_name} = ${instance_price:.2f}/hr")
                            return prices
                except ValueError:
                    continue
        
        return prices
    
    def _try_selenium_scraper(self) -> Dict[str, str]:
        """Use Selenium to scrape JavaScript-loaded pricing from GCP"""
        b200_prices = {}
        
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
            from selenium.common.exceptions import WebDriverException
            
            print("    Setting up Selenium WebDriver...")
            
            # Configure Chrome options
            chrome_options = Options()
            chrome_options.add_argument('--headless')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--window-size=1920,1080')
            chrome_options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
            
            # Initialize the driver
            driver = webdriver.Chrome(options=chrome_options)
            
            try:
                for url in self.base_urls:
                    print(f"    Loading: {url}")
                    driver.get(url)
                    
                    # Wait for page to load
                    time.sleep(5)
                    
                    # Get the page source after JavaScript has loaded
                    page_source = driver.page_source
                    soup = BeautifulSoup(page_source, 'html.parser')
                    text_content = soup.get_text()
                    
                    print(f"    ✓ Page loaded, content length: {len(text_content)}")
                    
                    # Try extraction methods
                    found_prices = self._extract_from_tables(soup)
                    if found_prices:
                        b200_prices.update(found_prices)
                        break
                    
                    found_prices = self._extract_from_text(text_content)
                    if found_prices:
                        b200_prices.update(found_prices)
                        break
                
            finally:
                driver.quit()
                print("    WebDriver closed")
                
        except ImportError:
            print("      ⚠️  Selenium not installed. Run: pip install selenium")
        except WebDriverException as e:
            print(f"      ⚠️  Selenium WebDriver error: {str(e)[:100]}")
        except Exception as e:
            print(f"      ⚠️  Error: {str(e)[:100]}")
        
        return b200_prices
    
    def _get_known_pricing(self) -> Dict[str, str]:
        """
        Get known GCP B200 pricing as fallback.
        Based on research: GCP B200 pricing estimated ~$18.53/hr
        
        Reference: https://cloud.google.com/compute/gpus-pricing
        GCP A4 VMs with 8 x B200 GPUs
        """
        print("    Using estimated GCP B200 pricing...")
        
        # Based on market research and GCP GPU pricing patterns
        # B200 estimated at ~$18-19/GPU/hour on GCP
        known_prices = {
            'A4 B200 (Google Cloud)': '$18.50/hr',
        }
        
        print(f"    ✅ Using {len(known_prices)} estimated pricing entries")
        print(f"    ⚠️  Note: GCP B200 pricing not yet publicly available in detail")
        return known_prices
    
    def save_to_json(self, prices: Dict[str, str], filename: str = "gcp_b200_prices.json") -> bool:
        """Save results to a JSON file"""
        try:
            output_data = {
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "provider": self.name,
                "prices": prices,
                "notes": {
                    "instance_type": "A4 VM",
                    "gpu_model": "NVIDIA B200",
                    "gpu_count_per_instance": 8,
                    "pricing_type": "On-demand (estimated)",
                    "source": "https://cloud.google.com/compute/gpus-pricing",
                    "note": "A4X VMs with 72x B200 also available"
                }
            }
            
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(output_data, f, indent=2, ensure_ascii=False)
            
            print(f"💾 Results saved to: {filename}")
            return True
            
        except Exception as e:
            print(f"❌ Error saving to file: {str(e)}")
            return False


def main():
    """Main function to run the GCP B200 scraper"""
    print("🚀 Google Cloud Platform B200 GPU Pricing Scraper")
    print("=" * 80)
    print("Note: GCP offers B200 GPUs in A4 VMs (8 x B200)")
    print("=" * 80)
    
    scraper = GCPB200Scraper()
    
    start_time = time.time()
    prices = scraper.get_b200_prices()
    end_time = time.time()
    
    print(f"\n⏱️  Scraping completed in {end_time - start_time:.2f} seconds")
    
    # Display results
    if prices and 'Error' not in str(prices):
        print(f"\n✅ Successfully extracted {len(prices)} B200 price entries:\n")
        
        for variant, price in sorted(prices.items()):
            print(f"  • {variant:50s} {price}")
        
        # Save results to JSON
        scraper.save_to_json(prices)
    else:
        print("\n❌ No valid pricing data found")


if __name__ == "__main__":
    main()
