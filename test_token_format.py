#!/usr/bin/env python3
"""
Quick script to verify Databricks secret token format
Run locally to check if the token in your secret has the correct format
"""

import sys
from databricks.sdk import WorkspaceClient

def test_token_format():
    """Test that the secret token has the correct format"""
    print("=" * 80)
    print("TESTING DATABRICKS SECRET TOKEN FORMAT")
    print("=" * 80)
    print()

    try:
        print("1. Connecting to Databricks workspace...")
        w = WorkspaceClient()
        print("   ✓ Connected successfully")
        print()

        print("2. Fetching secret from scope 'redditscope', key 'redditkey'...")
        token = w.dbutils.secrets.get(scope="redditscope", key="redditkey")
        print("   ✓ Secret retrieved successfully")
        print()

        print("3. Checking token format...")
        print(f"   Token length: {len(token)} characters")
        print(f"   First 8 characters: {token[:8]}")
        print(f"   Last 3 characters: ...{token[-3:]}")
        print()

        # Check if it's a Databricks PAT
        if token.startswith("dapi"):
            print("   ✅ Token starts with 'dapi' - CORRECT FORMAT (Databricks PAT)")
        else:
            print(f"   ⚠️  Token starts with '{token[:4]}' - UNEXPECTED FORMAT")
            print("   Expected: Databricks Personal Access Token (starts with 'dapi')")
        print()

        # Check for common issues
        print("4. Checking for common issues...")
        issues = []

        if "\n" in token or "\r" in token:
            issues.append("Token contains newline characters")
        if token.startswith(" ") or token.endswith(" "):
            issues.append("Token has leading/trailing spaces")
        if len(token) < 20:
            issues.append(f"Token is unusually short ({len(token)} chars)")
        if len(token) > 200:
            issues.append(f"Token is unusually long ({len(token)} chars)")

        if issues:
            print("   ⚠️  Issues found:")
            for issue in issues:
                print(f"      - {issue}")
        else:
            print("   ✓ No obvious issues found")
        print()

        print("=" * 80)
        print("SUMMARY")
        print("=" * 80)
        if token.startswith("dapi") and not issues:
            print("✅ Token looks good! Should work for Lakebase authentication.")
        else:
            print("⚠️  Token may have issues. Check the warnings above.")
        print()

        return True

    except Exception as e:
        print(f"   ❌ Error: {e}")
        print()
        print("=" * 80)
        print("TROUBLESHOOTING")
        print("=" * 80)
        print("Possible causes:")
        print("1. Secret doesn't exist in scope 'redditscope' with key 'redditkey'")
        print("2. You don't have READ permission on the secret scope")
        print("3. Databricks CLI not configured (run: databricks configure)")
        print()
        print("To check if secret exists:")
        print("  databricks secrets list-secrets --scope redditscope")
        print()
        print("To check your permissions:")
        print("  databricks secrets list-acls --scope redditscope")
        print()
        return False

if __name__ == "__main__":
    success = test_token_format()
    sys.exit(0 if success else 1)
