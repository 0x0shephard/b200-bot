#!/usr/bin/env python3
"""
B200 GPU Weighted Index Calculator

Calculates a weighted B200 GPU index price based on:
1. Hyperscalers (AWS, Oracle, Google Cloud, CoreWeave) with static discounts
   - AWS: 33% (Savings Plans), Oracle: 25% (volume), Google: 25% (CUDs), CoreWeave: 50% (take-or-pay)
   - These providers sell 80% at discounted rates, 20% at full price
   - Weights based on quarterly B200 revenue from research
2. Non-hyperscalers at full price (weighted by revenue)
3. Weighting: 65% hyperscalers, 35% non-hyperscalers

Revenue Source: B200 Revenue Research (Q3 2025)
- AWS: $1,300M quarterly B200 revenue
- Oracle: $730M quarterly B200 revenue
- CoreWeave: $300M quarterly B200 revenue
- Google Cloud: Estimated $500M (major hyperscaler, no public B200-specific data)
- Nebius: $73M, Crusoe: $45M, HPC-AI: $5.1M, Vultr: $4.5M, etc.
"""

import json
from pathlib import Path
from typing import Dict, List, Tuple


class B200IndexCalculator:
    """Calculate weighted B200 GPU index price based on revenue"""
    
    def __init__(self, b200_dir: str = "."):
        self.b200_dir = Path(b200_dir)
        
        # Define hyperscalers (4 major cloud providers - Civo moved to non-hyperscaler)
        # Based on B200 Revenue Research: AWS, Oracle, Google Cloud, CoreWeave
        self.hyperscalers = ["AWS", "Oracle", "Google Cloud", "CoreWeave"]
        
        # Static hyperscaler discounts aligned with H100 index methodology
        # From gpu_index_calculator.py - keeping consistency across GPU indexes:
        # - AWS: 44% discount (100% of enterprise buyers get discount via Savings Plans)
        # - Oracle: 25% discount (volume/commitment deals - no H100 equivalent, using B200 research)
        # - Google Cloud: 65% discount (65% of buyers get discount via CUDs)
        # - CoreWeave: 50% discount (80% of buyers get discount via take-or-pay)
        self.hyperscaler_discounts = {
            "AWS": 0.44,           # 44% discount (matching H100 Savings Plans)
            "Oracle": 0.25,        # 25% discount (volume/commitment deals)
            "Google Cloud": 0.65,  # 65% discount (matching H100 CUDs)
            "CoreWeave": 0.50,     # 50% discount (matching H100 take-or-pay)
        }
        
        # Total weight distribution
        self.hyperscaler_total_weight = 0.65  # 65%
        self.non_hyperscaler_total_weight = 0.35  # 35%
        
        # Hyperscaler individual weights based on B200 revenue (must sum to 1.0)
        # Revenue from B200 Revenue Research (Q3 2025 quarterly):
        # - AWS: $1,300M
        # - Oracle: $730M
        # - Google Cloud: $500M (estimated - no public B200 specific data)
        # - CoreWeave: $300M
        # Total hyperscaler revenue: $2,830M
        self.hyperscaler_weights = {
            "AWS": 0.46,           # $1300M / $2830M ≈ 46% of hyperscaler weight
            "Oracle": 0.26,        # $730M / $2830M ≈ 26% of hyperscaler weight
            "Google Cloud": 0.18,  # $500M / $2830M ≈ 18% of hyperscaler weight
            "CoreWeave": 0.10,     # $300M / $2830M ≈ 10% of hyperscaler weight
        }
        
        # Non-hyperscaler weights based on B200 revenue (must sum to 1.0)
        # Revenue data from research + web estimates (Q3 2025 quarterly B200 revenue):
        # - Lambda Labs: ~$130M quarterly (from $520M annual, ~25% B200 share) 
        # - Nebius: $73M quarterly B200 revenue
        # - Crusoe: $45M quarterly B200 revenue  
        # - RunPod: ~$30M quarterly (from $120M ARR, ~25% B200)
        # - Vast.ai: ~$10M quarterly (marketplace, B200 growing)
        # - HPC-AI: $5.1M quarterly
        # - Vultr: $4.5M quarterly
        # - Verda: $3.75M quarterly
        # - Sesterce: ~$2M quarterly (est. EU provider)
        # - Cirrascale: $0.56M quarterly
        # - Civo: $0.4M quarterly
        # - GreenAI Cloud: $0.47M quarterly
        # - Packet.ai: ~$1M quarterly (est. new provider)
        # - ComputePrices: ~$0.1M (aggregator)
        # Total: ~$305.88M quarterly
        self.non_hyperscaler_weights = {
            "Lambda Labs": 0.425,    # $130M / $305.88M ≈ 42.5%
            "Nebius": 0.239,         # $73M / $305.88M ≈ 23.9%
            "Crusoe": 0.147,         # $45M / $305.88M ≈ 14.7%
            "RunPod": 0.098,         # $30M / $305.88M ≈ 9.8%
            "Vast.ai": 0.033,        # $10M / $305.88M ≈ 3.3%
            "HPC-AI": 0.017,         # $5.1M / $305.88M ≈ 1.7%
            "Vultr": 0.015,          # $4.5M / $305.88M ≈ 1.5%
            "Verda": 0.012,          # $3.75M / $305.88M ≈ 1.2%
            "Sesterce": 0.007,       # $2M / $305.88M ≈ 0.7%
            "Cirrascale": 0.002,     # $0.56M / $305.88M ≈ 0.2%
            "Civo": 0.001,           # $0.4M / $305.88M ≈ 0.1%
            "GreenAI Cloud": 0.002,  # $0.47M / $305.88M ≈ 0.15%
            "Packet.ai": 0.003,      # $1M / $305.88M ≈ 0.3%
            "ComputePrices": 0.0003, # ~$0.1M (aggregator)
        }
    
    def load_all_prices(self) -> Dict[str, float]:
        """Load all B200 prices from JSON files and average with GetDeploying data"""
        prices = {}
        
        # First, load prices from dedicated provider scrapers
        json_files = list(self.b200_dir.glob("*_b200_prices.json"))
        # Exclude getdeploying from dedicated scrapers (we'll handle it separately)
        json_files = [f for f in json_files if 'getdeploying' not in f.name.lower()]
        
        print(f"📂 Found {len(json_files)} dedicated B200 price files\n")
        
        dedicated_prices = {}
        for json_file in json_files:
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    provider = data.get("provider", json_file.stem.replace("_b200_prices", ""))
                    
                    # Normalize provider names
                    provider = self._normalize_provider_name(provider)
                    
                    # Extract price value
                    price = self._extract_price_from_data(data)
                    
                    if price and price > 0:
                        dedicated_prices[provider] = price
                        print(f"   ✓ {provider:20s} ${price:.2f}/hr (dedicated scraper)")
            except Exception as e:
                print(f"   ✗ Error loading {json_file}: {e}")
        
        # Now load GetDeploying prices
        getdeploying_prices = self._load_getdeploying_prices()
        
        # Average prices for providers that appear in both sources
        print(f"\n📊 Averaging prices from both sources...\n")
        
        all_providers = set(dedicated_prices.keys()) | set(getdeploying_prices.keys())
        
        for provider in all_providers:
            dedicated_price = dedicated_prices.get(provider)
            getdeploying_price = getdeploying_prices.get(provider)
            
            if dedicated_price and getdeploying_price:
                # Average both prices
                avg_price = (dedicated_price + getdeploying_price) / 2
                prices[provider] = avg_price
                print(f"   ⚖️  {provider:20s} ${avg_price:.2f}/hr (avg of ${dedicated_price:.2f} + ${getdeploying_price:.2f})")
            elif dedicated_price:
                # Only dedicated scraper price
                prices[provider] = dedicated_price
                print(f"   📋 {provider:20s} ${dedicated_price:.2f}/hr (dedicated only)")
            elif getdeploying_price:
                # Only GetDeploying price
                prices[provider] = getdeploying_price
                print(f"   🌐 {provider:20s} ${getdeploying_price:.2f}/hr (getdeploying only)")

        return self._filter_implausible_prices(prices)

    def _filter_implausible_prices(self, prices: Dict[str, float]) -> Dict[str, float]:
        """
        Defensive sanity guard: drop any provider whose per-GPU price is
        physically implausible for a single B200 before it reaches the weighted
        index. This protects the index from a single bad scrape (e.g. an
        un-normalized multi-GPU node price) poisoning the final number.

        The band is intentionally wide so it is a no-op in normal operation and
        only fires on values no single B200 could legitimately have. It does not
        change provider weights or the provider set — it just skips a poisoned
        reading for the current run.
        """
        MIN_PER_GPU, MAX_PER_GPU = 0.50, 25.0
        sane_prices = {}
        for provider, price in prices.items():
            if MIN_PER_GPU <= price <= MAX_PER_GPU:
                sane_prices[provider] = price
            else:
                print(f"   🚫 Skipping {provider}: ${price:.2f}/hr is outside the plausible "
                      f"per-GPU range (${MIN_PER_GPU:.2f}-${MAX_PER_GPU:.2f}) — likely a scrape error")
        return sane_prices
    
    def _load_getdeploying_prices(self) -> Dict[str, float]:
        """Load prices from GetDeploying aggregator"""
        getdeploying_file = self.b200_dir / "getdeploying_b200_prices.json"
        prices = {}
        
        if not getdeploying_file.exists():
            print("   ⚠️  GetDeploying price file not found")
            return prices
        
        try:
            with open(getdeploying_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            provider_prices = data.get("prices", {})
            print(f"\n📂 Found {len(provider_prices)} providers in GetDeploying data\n")
            
            for provider, price_data in provider_prices.items():
                # Normalize provider name
                provider = self._normalize_provider_name(provider)
                
                # Extract price_per_gpu
                if isinstance(price_data, dict):
                    price = price_data.get("price_per_gpu", 0)
                else:
                    price = float(price_data)
                
                if price and price > 0:
                    prices[provider] = price
                    print(f"   ✓ {provider:20s} ${price:.2f}/hr (getdeploying)")
                    
        except Exception as e:
            print(f"   ✗ Error loading GetDeploying data: {e}")
        
        return prices
    
    def _normalize_provider_name(self, name: str) -> str:
        """Normalize provider names to match across sources"""
        name_map = {
            "aws": "AWS",
            "oracle": "Oracle",
            "oracle cloud": "Oracle",
            "google cloud": "Google Cloud",
            "gcp": "Google Cloud",
            "google_cloud": "Google Cloud",
            "coreweave": "CoreWeave",
            "nebius": "Nebius",
            "crusoe": "Crusoe",
            "hpc-ai": "HPC-AI",
            "hpcai": "HPC-AI",
            "vultr": "Vultr",
            "civo": "Civo",
            "runpod": "RunPod",
            "cirrascale": "Cirrascale",
            "greenai": "GreenAI Cloud",
            "greenai cloud": "GreenAI Cloud",
            "green ai cloud": "GreenAI Cloud",
            "computeprices": "ComputePrices",
            "vast.ai": "Vast.ai",
            "lambda labs": "Lambda Labs",
            "sesterce": "Sesterce",
            "packet.ai": "Packet.ai",
            "verda": "Verda",
        }
        return name_map.get(name.lower(), name)
    
    def _extract_price_from_data(self, data: Dict) -> float:
        """Extract price value from provider data"""
        import re
        
        # Try standard "prices" structure
        provider_prices = data.get("prices", {})
        if provider_prices:
            for variant, price_str in provider_prices.items():
                match = re.search(r'([0-9.]+)', str(price_str).replace(',', '.'))
                if match:
                    return float(match.group(1))
        
        # Try RunPod's nested structure
        if "providers" in data:
            nested_providers = data.get("providers", {})
            for nested_provider_name, nested_data in nested_providers.items():
                variants = nested_data.get("variants", {})
                for variant_name, variant_data in variants.items():
                    if isinstance(variant_data, dict) and "price_per_hour" in variant_data:
                        return float(variant_data["price_per_hour"])
        
        return 0.0
    
    def apply_hyperscaler_discounts(self, prices: Dict[str, float]) -> Dict[str, Dict]:
        """Apply static discounts to hyperscalers based on revenue research"""
        discounted_prices = {}
        
        print("\n" + "=" * 80)
        print("💰 HYPERSCALER DISCOUNT APPLICATION")
        print("=" * 80)
        print("Static discounts based on B200 Revenue Research:")
        print("  AWS: 33% (Savings Plans), Oracle: 25% (volume), Google: 25% (CUDs), CoreWeave: 50% (take-or-pay)")
        print("Hyperscalers sell 80% at discounted rates, 20% at full price\n")
        
        for provider, original_price in prices.items():
            if provider in self.hyperscalers:
                # Get static discount for this provider
                discount_rate = self.hyperscaler_discounts.get(provider, 0.30)  # Default 30% if not found
                
                # Calculate effective price: 80% at discounted rate + 20% at full rate
                discounted_portion = original_price * (1 - discount_rate) * 0.80
                full_price_portion = original_price * 0.20
                effective_price = discounted_portion + full_price_portion
                
                discounted_prices[provider] = {
                    "original_price": original_price,
                    "discount_rate": discount_rate,
                    "discounted_price": original_price * (1 - discount_rate),
                    "effective_price": effective_price,
                    "is_hyperscaler": True
                }
                
                print(f"🏢 {provider:20s}")
                print(f"   Original Price:     ${original_price:.2f}/hr")
                print(f"   Discount Applied:   {discount_rate*100:.0f}%")
                print(f"   Discounted Price:   ${original_price * (1 - discount_rate):.2f}/hr")
                print(f"   Effective Price:    ${effective_price:.2f}/hr (80% discounted + 20% full)")
                print()
            else:
                # Non-hyperscalers use full price
                discounted_prices[provider] = {
                    "original_price": original_price,
                    "discount_rate": 0.0,
                    "discounted_price": original_price,
                    "effective_price": original_price,
                    "is_hyperscaler": False
                }
        
        return discounted_prices
    
    def calculate_weighted_index(self, discounted_prices: Dict[str, Dict]) -> Dict:
        """Calculate weighted index price"""
        
        # Separate hyperscalers and non-hyperscalers
        hyperscaler_prices = {k: v for k, v in discounted_prices.items() if v["is_hyperscaler"]}
        non_hyperscaler_prices = {k: v for k, v in discounted_prices.items() if not v["is_hyperscaler"]}
        
        print("=" * 80)
        print("⚖️  WEIGHTED INDEX CALCULATION")
        print("=" * 80)
        
        # Calculate hyperscaler weighted price
        print(f"\n📊 HYPERSCALERS (Total Weight: {self.hyperscaler_total_weight*100:.0f}%)")
        print("-" * 80)
        
        hyperscaler_weighted_sum = 0
        hyperscaler_details = []
        
        for provider, data in hyperscaler_prices.items():
            if provider in self.hyperscaler_weights:
                individual_weight = self.hyperscaler_weights[provider]
                absolute_weight = individual_weight * self.hyperscaler_total_weight
                weighted_price = data["effective_price"] * absolute_weight
                
                hyperscaler_weighted_sum += weighted_price
                hyperscaler_details.append({
                    "provider": provider,
                    "effective_price": data["effective_price"],
                    "relative_weight": individual_weight,
                    "absolute_weight": absolute_weight,
                    "weighted_contribution": weighted_price
                })
                
                print(f"{provider:20s} ${data['effective_price']:6.2f}/hr × {absolute_weight*100:5.1f}% = ${weighted_price:.4f}")
        
        print(f"{'':20s} {'':11s} {'':7s}   {'─'*20}")
        print(f"{'Hyperscaler Subtotal':20s} {'':11s} {'':7s}   ${hyperscaler_weighted_sum:.4f}")
        
        # Calculate non-hyperscaler weighted price
        print(f"\n📊 NON-HYPERSCALERS (Total Weight: {self.non_hyperscaler_total_weight*100:.0f}%)")
        print("-" * 80)
        
        non_hyperscaler_weighted_sum = 0
        non_hyperscaler_details = []
        
        if non_hyperscaler_prices:
            # Use revenue-based weights for non-hyperscalers
            for provider, data in non_hyperscaler_prices.items():
                # Get weight from revenue-based weights, default to 0.01 if not defined
                individual_weight = self.non_hyperscaler_weights.get(provider, 0.01)
                absolute_weight = individual_weight * self.non_hyperscaler_total_weight
                weighted_price = data["effective_price"] * absolute_weight
                
                non_hyperscaler_weighted_sum += weighted_price
                non_hyperscaler_details.append({
                    "provider": provider,
                    "effective_price": data["effective_price"],
                    "relative_weight": individual_weight,
                    "absolute_weight": absolute_weight,
                    "weighted_contribution": weighted_price
                })
                
                print(f"{provider:20s} ${data['effective_price']:6.2f}/hr × {absolute_weight*100:5.2f}% = ${weighted_price:.4f}")
            
            print(f"{'':20s} {'':11s} {'':7s}   {'─'*20}")
            print(f"{'Non-Hyperscaler Subtotal':20s} {'':11s} {'':7s}   ${non_hyperscaler_weighted_sum:.4f}")
        
        # Calculate final index
        final_index = hyperscaler_weighted_sum + non_hyperscaler_weighted_sum
        
        print("\n" + "=" * 80)
        print("🎯 FINAL B200 INDEX PRICE")
        print("=" * 80)
        print(f"\nHyperscaler Component:     ${hyperscaler_weighted_sum:.4f} ({self.hyperscaler_total_weight*100:.0f}%)")
        print(f"Non-Hyperscaler Component: ${non_hyperscaler_weighted_sum:.4f} ({self.non_hyperscaler_total_weight*100:.0f}%)")
        print(f"{'─'*50}")
        print(f"B200 Weighted Index:       ${final_index:.2f}/hr")
        print("=" * 80)
        
        return {
            "timestamp": __import__('time').strftime("%Y-%m-%d %H:%M:%S"),
            "final_index_price": round(final_index, 2),
            "hyperscaler_component": round(hyperscaler_weighted_sum, 4),
            "non_hyperscaler_component": round(non_hyperscaler_weighted_sum, 4),
            "hyperscaler_details": hyperscaler_details,
            "non_hyperscaler_details": non_hyperscaler_details,
            "weights": {
                "hyperscaler_total": self.hyperscaler_total_weight,
                "non_hyperscaler_total": self.non_hyperscaler_total_weight,
                "hyperscaler_individual": self.hyperscaler_weights
            },
            "all_provider_data": discounted_prices
        }
    
    def save_index_report(self, index_data: Dict):
        """Save index calculation report to JSON"""
        output_file = self.b200_dir / "b200_weighted_index.json"
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(index_data, f, indent=2, ensure_ascii=False)
        
        print(f"\n💾 Index report saved to: {output_file}")


def main():
    """Main function to calculate B200 weighted index"""
    print("🚀 B200 GPU Weighted Index Calculator")
    print("=" * 80)
    print("Calculating weighted B200 index with hyperscaler discounts...")
    print()
    
    # Set random seed for reproducibility (optional - remove for different results each run)
    # random.seed(42)
    
    # Initialize calculator
    calculator = B200IndexCalculator()
    
    # Load all prices
    prices = calculator.load_all_prices()
    
    if not prices:
        print("\n❌ No B200 price files found!")
        return
    
    # Apply hyperscaler discounts
    discounted_prices = calculator.apply_hyperscaler_discounts(prices)
    
    # Calculate weighted index
    index_data = calculator.calculate_weighted_index(discounted_prices)
    
    # Save report
    calculator.save_index_report(index_data)
    
    print("\n✅ Index calculation complete!")
    print(f"\n🎯 Final B200 Weighted Index Price: ${index_data['final_index_price']:.2f}/hr")


if __name__ == "__main__":
    main()
