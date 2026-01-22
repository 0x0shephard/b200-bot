#!/usr/bin/env python3
"""
AWS P6 Instance (B200 GPU) Price Scraper
Extracts B200 pricing from AWS EC2 Capacity Blocks pricing page

AWS offers B200 GPUs in P6-B200 instances (8 x B200 GPUs).

Reference: https://aws.amazon.com/ec2/capacityblocks/pricing/
"""

import requests
from bs4 import BeautifulSoup
import re
import json
import time
from typing import Dict, Optional


class AWSB200Scraper:
    """Scraper for AWS P6-B200 instance pricing"""
    
    def __init__(self):
        self.name = "AWS"
        self.base_url = "https://aws.amazon.com/ec2/capacityblocks/pricing/"
        # Vantage.sh URLs for multiple regions - P6 instances have B200 GPUs
        self.vantage_regions = [
            ("us-east-1", "https://instances.vantage.sh/aws/ec2/p6-b200.48xlarge?region=us-east-1"),
            ("us-east-2", "https://instances.vantage.sh/aws/ec2/p6-b200.48xlarge?region=us-east-2"),
            ("us-west-2", "https://instances.vantage.sh/aws/ec2/p6-b200.48xlarge?region=us-west-2"),
            ("eu-west-1", "https://instances.vantage.sh/aws/ec2/p6-b200.48xlarge?region=eu-west-1"),
            ("eu-central-1", "https://instances.vantage.sh/aws/ec2/p6-b200.48xlarge?region=eu-central-1"),
            ("ap-northeast-1", "https://instances.vantage.sh/aws/ec2/p6-b200.48xlarge?region=ap-northeast-1"),
        ]
        self.vantage_base = "https://instances.vantage.sh/aws/ec2/p6-b200.48xlarge"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
        }
    
    def get_b200_prices(self) -> Dict[str, str]:
        """Main method to extract B200 prices from AWS - multi-region for volatility"""
        print(f"🔍 Fetching {self.name} P6-B200 pricing (multi-region)...")
        print("=" * 80)
        
        b200_prices = {}
        
        # Try multiple methods in order - Vantage multi-region first for volatility
        methods = [
            ("Vantage Multi-Region Pricing", self._try_vantage_multi_region),
            ("AWS Pricing API", self._try_aws_pricing_api),
            ("Capacity Blocks Page Scraping", self._try_pricing_page),
            ("Selenium Scraper", self._try_selenium_scraper),
        ]
        
        for method_name, method_func in methods:
            print(f"\n📋 Method: {method_name}")
            try:
                prices = method_func()
                if prices and self._validate_prices(prices):
                    b200_prices.update(prices)
                    print(f"   ✅ Found {len(prices)} B200 prices!")
                    break  # Return on first successful method
                else:
                    print(f"   ❌ No valid prices found")
            except Exception as e:
                print(f"   ⚠️  Error: {str(e)[:100]}")
                continue
        
        if not b200_prices:
            print("\n❌ All live methods failed - no fallback data (live data only mode)")
            return {}
        
        # Normalize to per-GPU pricing
        normalized_prices = self._normalize_prices(b200_prices)
        
        print(f"\n✅ Final extraction: {len(normalized_prices)} B200 price variants")
        return normalized_prices
    
    def _validate_prices(self, prices: Dict[str, str]) -> bool:
        """Validate that prices are in a reasonable range for B200 GPUs"""
        if not prices:
            return False
        
        for variant, price_str in prices.items():
            if 'Error' in variant:
                continue
            try:
                price_match = re.search(r'\$([0-9.]+)', price_str)
                if price_match:
                    price = float(price_match.group(1))
                    # B200 pricing should be reasonable (AWS is around $9-10/GPU/hr)
                    if 5 < price < 20:
                        return True
            except:
                continue
        return False
    
    def _try_vantage_multi_region(self) -> Dict[str, str]:
        """Fetch B200 prices from multiple AWS regions via Vantage.sh for volatility"""
        b200_prices = {}
        
        print(f"    Fetching prices from {len(self.vantage_regions)} AWS regions...")
        
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
                                # Instance price for 8 B200 GPUs ~$70-100/hr
                                if 50 < price < 150:
                                    per_gpu_price = price / 8
                                    region_name = region_code.replace('-', ' ').title()
                                    variant_name = f"P6-B200.48xlarge ({region_name})"
                                    b200_prices[variant_name] = f"${per_gpu_price:.2f}/hr"
                                    print(f"      ✓ {region_code}: ${price:.2f}/instance → ${per_gpu_price:.2f}/GPU")
                                    break
                                # Already per-GPU price
                                elif 5 < price < 20:
                                    region_name = region_code.replace('-', ' ').title()
                                    variant_name = f"P6-B200.48xlarge ({region_name})"
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
    
    def _try_aws_pricing_api(self) -> Dict[str, str]:
        """Try AWS Pricing API endpoints"""
        b200_prices = {}
        
        # AWS Pricing API endpoints
        api_urls = [
            "https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonEC2/current/index.json",
            "https://api.pricing.us-east-1.amazonaws.com/",
        ]
        
        for api_url in api_urls:
            try:
                print(f"    Trying API: {api_url}")
                # Note: The full pricing index is extremely large (>100MB)
                # For production, you'd want to use the AWS Price List API with filtering
                # Here we'll just check if the endpoint is accessible
                response = requests.head(api_url, headers=self.headers, timeout=10)
                
                if response.status_code == 200:
                    print(f"      ✓ API accessible (not downloading full index due to size)")
                    print(f"      ⚠️  Full pricing API requires specialized filtering")
                else:
                    print(f"      Status {response.status_code}")
                        
            except Exception as e:
                print(f"      Error: {str(e)[:50]}...")
                continue
        
        return b200_prices
    
    def _try_pricing_page(self) -> Dict[str, str]:
        """Scrape the Capacity Blocks pricing page for B200 prices"""
        b200_prices = {}
        
        try:
            print(f"    Trying: {self.base_url}")
            response = requests.get(self.base_url, headers=self.headers, timeout=20)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                text_content = soup.get_text()
                
                print(f"      Content length: {len(text_content)}")
                
                # Check if page contains B200 data
                if 'B200' not in text_content and 'b200' not in text_content.lower():
                    print(f"      ⚠️  No B200 content found")
                    return b200_prices
                
                print(f"      ✓ Found B200 content")
                
                # Extract from pricing tables
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
                print(f"      Status {response.status_code}")
                
        except Exception as e:
            print(f"      Error: {str(e)[:50] }...")
        
        return b200_prices
    
    def _extract_from_tables(self, soup: BeautifulSoup) -> Dict[str, str]:
        """Extract B200 prices from HTML tables"""
        prices = {}
        
        tables = soup.find_all('table')
        print(f"      Found {len(tables)} tables")
        
        for table in tables:
            table_text = table.get_text()
            
            # Only process tables with B200 mentions
            if 'B200' not in table_text and 'b200' not in table_text.lower():
                continue
            
            print(f"      📋 Processing table with B200 data")
            
            rows = table.find_all('tr')
            for row in rows:
                cells = row.find_all(['td', 'th'])
                row_text = ' '.join([cell.get_text().strip() for cell in cells])
                
                if 'B200' in row_text and '$' in row_text:
                    print(f"         Row: {row_text[:150]}")
                    
                    # Extract price - AWS format: "$74.88 USD" or "$9.36 USD"
                    # Looking for per-GPU price in parentheses: ($9.36 USD)
                    price_matches = re.findall(r'\$([0-9.]+)\s*USD', row_text)
                    
                    for price_str in price_matches:
                        try:
                            price = float(price_str)
                            # Per-GPU pricing is typically in the $5-$15 range
                            if 5.0 < price < 20.0:
                                # Extract region if available
                                region = "Multiple Regions"
                                if "US East (Ohio)" in row_text:
                                    region = "US East (Ohio)"
                                elif "US East (N. Virginia)" in row_text:
                                    region = "US East (N. Virginia)"
                                elif "US West (Oregon)" in row_text:
                                    region = "US West (Oregon)"
                                
                                variant_name = f"P6-B200 ({region})"
                                if variant_name not in prices:
                                    prices[variant_name] = f"${price:.2f}/hr"
                                    print(f"        Table ✓ {variant_name} = ${price:.2f}/hr")
                        except ValueError:
                            continue
        
        return prices
    
    def _extract_from_text(self, text_content: str) -> Dict[str, str]:
        """Extract B200 prices from text content using regex patterns"""
        prices = {}
        
        # AWS pricing format for P6-B200:
        # "US East (Ohio)... $74.88 USD ($9.36 USD)... 8 x B200"
        # The price in parentheses is per-GPU
        
        # Find P6-B200 section
        p6_b200_section = re.search(
            r'P6-B200 Pricing.*?(?=P\d+\s+Pricing|Trn\d+|OS Pricing|$)',
            text_content, re.IGNORECASE | re.DOTALL
        )
        
        if p6_b200_section:
            section_text = p6_b200_section.group(0)
            print(f"      📋 Found P6-B200 Pricing section ({len(section_text)} chars)")
            
            # Extract all pricing entries in this section
            # Format: "US East (Ohio)... $74.88 USD ($9.36 USD)... 8 x B200"
            pricing_pattern = r'(US\s+(?:East|West)\s*\([^)]+\))[^\$]*\$[0-9.]+\s*USD\s*\(\$([0-9.]+)\s*USD\)[^\n]*8\s*x\s*B200'
            
            matches = re.findall(pricing_pattern, section_text, re.IGNORECASE)
            
            for region, per_gpu_price in matches:
                try:
                    price = float(per_gpu_price)
                    if 5 < price < 20:
                        variant_name = f"P6-B200 ({region})"
                        prices[variant_name] = f"${price:.2f}/hr"
                        print(f"        Pattern ✓ {variant_name} = ${price:.2f}/hr")
                except ValueError:
                    continue
        
        return prices
    
    def _try_selenium_scraper(self) -> Dict[str, str]:
        """Use Selenium to scrape JavaScript-loaded pricing from AWS"""
        b200_prices = {}
        
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
            from selenium.webdriver.common.by import By
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
                print("    Loading pricing page...")
                driver.get(self.base_url)
                
                # Wait for page to load
                print("    Waiting for dynamic content to load...")
                time.sleep(5)  # Wait for JavaScript to render
                
                # Get the page source after JavaScript has loaded
                page_source = driver.page_source
                soup = BeautifulSoup(page_source, 'html.parser')
                text_content = soup.get_text()
                
                print(f"    ✓ Page loaded, content length: {len(text_content)}")
                
                # Extract prices using same methods
                found_prices = self._extract_from_tables(soup)
                if found_prices:
                    b200_prices.update(found_prices)
                else:
                    found_prices = self._extract_from_text(text_content)
                    if found_prices:
                        b200_prices.update(found_prices)
                
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
        Get known AWS P6-B200 pricing as fallback.
        Based on AWS's published Capacity Blocks pricing page.
        
        Reference: https://aws.amazon.com/ec2/capacityblocks/pricing/
        
        P6-B200: $9.36 per GPU-hour (8 x B200 instances)
        Available in multiple regions
        """
        print("    Using known AWS P6-B200 pricing data...")
        
        known_prices = {
            'P6-B200 (US East Ohio)': '$9.36/hr',
            'P6-B200 (US East N. Virginia)': '$9.36/hr',
            'P6-B200 (US West Oregon)': '$9.36/hr',
        }
        
        print(f"    ✅ Using {len(known_prices)} known pricing entries")
        return known_prices
    
    def _normalize_prices(self, prices: Dict[str, str]) -> Dict[str, str]:
        """
        Normalize prices - AWS already provides per-GPU pricing.
        Calculate average across all regions for a single representative price.
        """
        if not prices:
            return {}
        
        per_gpu_prices = []
        
        print("\n   📊 Normalizing AWS P6-B200 pricing...")
        
        for variant, price_str in prices.items():
            if 'Error' in variant:
                continue
            
            try:
                # Extract price value
                price_match = re.search(r'\$([0-9.]+)', price_str)
                if price_match:
                    price = float(price_match.group(1))
                    per_gpu_prices.append(price)
                    print(f"      {variant}: ${price:.2f}/hr")
                    
            except (ValueError, TypeError) as e:
                print(f"      ⚠️ Error normalizing {variant}: {e}")
                continue
        
        if per_gpu_prices:
            # Calculate average per-GPU price across all regions
            avg_per_gpu = sum(per_gpu_prices) / len(per_gpu_prices)
            print(f"\n   ✅ Averaged {len(per_gpu_prices)} regional prices → ${avg_per_gpu:.2f}/GPU")
            
            # Return single normalized price
            return {
                'P6-B200 (AWS)': f"${avg_per_gpu:.2f}/hr"
            }
        
        return {}
    
    def save_to_json(self, prices: Dict[str, str], filename: str = "aws_b200_prices.json") -> bool:
        """Save results to a JSON file"""
        try:
            output_data = {
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "provider": self.name,
                "prices": prices,
                "notes": {
                    "instance_type": "P6-B200",
                    "gpu_model": "NVIDIA B200",
                    "gpu_count_per_instance": 8,
                    "pricing_type": "Capacity Blocks (reserved)",
                    "source": "https://aws.amazon.com/ec2/capacityblocks/pricing/"
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
    """Main function to run the AWS P6-B200 scraper"""
    print("🚀 AWS P6-B200 GPU Pricing Scraper")
    print("=" * 80)
    print("Note: AWS offers B200 GPUs in P6-B200 instances (8 x B200)")
    print("=" * 80)
    
    scraper = AWSB200Scraper()
    
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
