#!/usr/bin/env python3
"""
Push B200 Weighted Index to Supabase

This script reads the B200 weighted index from b200_weighted_index.json
and pushes it to the Supabase b200_index_prices table.

Usage:
    python push_to_supabase.py

Environment Variables Required (set in .env file):
    SUPABASE_URL - Your Supabase project URL
    SUPABASE_SERVICE_KEY - Your Supabase service role key (for write access)
"""

import json
import os
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()


def load_index_data(filepath: str = "b200_weighted_index.json") -> Optional[Dict]:
    """Load B200 weighted index data from JSON file"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"❌ Error: {filepath} not found!")
        print(f"   Please run calculate_b200_index.py first to generate the index.")
        return None
    except json.JSONDecodeError as e:
        print(f"❌ Error parsing JSON: {e}")
        return None


def push_to_supabase(index_data: Dict) -> bool:
    """Push B200 index data to Supabase"""
    
    # Get Supabase credentials from environment
    supabase_url = os.getenv('SUPABASE_URL')
    supabase_key = os.getenv('SUPABASE_SERVICE_KEY')
    
    if not supabase_url or not supabase_key:
        print("❌ Error: Supabase credentials not found!")
        print("   Please set SUPABASE_URL and SUPABASE_SERVICE_KEY environment variables.")
        print("\n   Example:")
        print("   export SUPABASE_URL='https://your-project.supabase.co'")
        print("   export SUPABASE_SERVICE_KEY='your-service-role-key'")
        return False
    
    try:
        from supabase import create_client, Client
    except ImportError:
        print("❌ Error: supabase-py library not installed!")
        print("   Install it with: pip install supabase")
        return False
    
    try:
        # Initialize Supabase client
        supabase: Client = create_client(supabase_url, supabase_key)
        
        # Prepare data for insertion
        insert_data = {
            "timestamp": index_data.get("timestamp"),
            "index_price": index_data.get("final_index_price"),
            "hyperscaler_component": index_data.get("hyperscaler_component"),
            "non_hyperscaler_component": index_data.get("non_hyperscaler_component"),
            "metadata": {
                "weights": index_data.get("weights", {}),
                "hyperscaler_details": index_data.get("hyperscaler_details", []),
                "non_hyperscaler_details": index_data.get("non_hyperscaler_details", []),
                "provider_count": len(index_data.get("all_provider_data", {}))
            }
        }
        
        print(f"\n📤 Pushing B200 Index to Supabase...")
        print(f"   Index Price: ${insert_data['index_price']:.2f}/hr")
        print(f"   Timestamp: {insert_data['timestamp']}")
        
        # Insert into Supabase
        response = supabase.table('b200_index_prices').insert(insert_data).execute()
        
        if response.data:
            print(f"\n✅ Successfully pushed to Supabase!")
            print(f"   Record ID: {response.data[0]['id']}")
            return True
        else:
            print(f"\n❌ Error: No data returned from Supabase")
            return False
            
    except Exception as e:
        print(f"\n❌ Error pushing to Supabase: {e}")
        import traceback
        traceback.print_exc()
        return False


def verify_push(supabase_url: str, supabase_key: str) -> bool:
    """Verify the most recent entry in Supabase"""
    try:
        from supabase import create_client
        
        supabase = create_client(supabase_url, supabase_key)
        
        # Get the most recent entry
        response = supabase.table('b200_index_prices')\
            .select('*')\
            .order('created_at', desc=True)\
            .limit(1)\
            .execute()
        
        if response.data:
            latest = response.data[0]
            print(f"\n📊 Latest Entry in Supabase:")
            print(f"   ID: {latest['id']}")
            print(f"   Index Price: ${latest['index_price']}/hr")
            print(f"   Timestamp: {latest['timestamp']}")
            print(f"   Created At: {latest['created_at']}")
            return True
        else:
            print(f"\n⚠️  No entries found in b200_index_prices table")
            return False
            
    except Exception as e:
        print(f"\n⚠️  Could not verify: {e}")
        return False


def main():
    """Main function"""
    print("🚀 B200 Index → Supabase Uploader")
    print("=" * 60)
    
    # Load index data
    print("\n📂 Loading B200 weighted index data...")
    index_data = load_index_data()
    
    if not index_data:
        sys.exit(1)
    
    print(f"   ✓ Loaded index: ${index_data['final_index_price']:.2f}/hr")
    
    # Push to Supabase
    success = push_to_supabase(index_data)
    
    if not success:
        sys.exit(1)
    
    # Verify
    supabase_url = os.getenv('SUPABASE_URL')
    supabase_key = os.getenv('SUPABASE_SERVICE_KEY')
    
    if supabase_url and supabase_key:
        verify_push(supabase_url, supabase_key)
    
    print("\n✅ B200 index successfully uploaded to Supabase!")


if __name__ == "__main__":
    main()
