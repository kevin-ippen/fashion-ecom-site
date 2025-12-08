%md
# ============================================================================
# SECRET PERMISSIONS & PAT TOKEN VERIFICATION
# ============================================================================

import os
from databricks.sdk import WorkspaceClient
import requests

print("="*80)
print("VERIFYING SECRET PERMISSIONS AND PAT TOKEN")
print("="*80)
print()

# Initialize Workspace Client
w = WorkspaceClient()

# ============================================================================
# STEP 1: Check Secret Scope Permissions
# ============================================================================

print("[1] CHECKING SECRET SCOPE PERMISSIONS")
print("-" * 80)

try:
    # List all secret scopes
    scopes = w.secrets.list_scopes()
    print(f"✓ Found {len(list(scopes))} secret scope(s)")
    print()
    
    # Check if redditscope exists
    scopes = w.secrets.list_scopes()
    reddit_scope_found = False
    
    for scope in scopes:
        if scope.name == "redditscope":
            reddit_scope_found = True
            print(f"✓ Found scope: {scope.name}")
            print(f"  Backend Type: {scope.backend_type}")
            break
    
    if not reddit_scope_found:
        print("❌ ERROR: 'redditscope' not found!")
        print("   Available scopes:")
        scopes = w.secrets.list_scopes()
        for scope in scopes:
            print(f"   - {scope.name}")
    
    print()
    
except Exception as e:
    print(f"❌ ERROR listing scopes: {e}")
    print()

# ============================================================================
# STEP 2: Check Secret Exists
# ============================================================================

print("[2] CHECKING SECRET EXISTS")
print("-" * 80)

try:
    # List secrets in redditscope
    secrets = w.secrets.list_secrets(scope="redditscope")
    secret_list = list(secrets)
    
    print(f"✓ Found {len(secret_list)} secret(s) in 'redditscope'")
    
    reddit_key_found = False
    for secret in secret_list:
        print(f"  - {secret.key}")
        if secret.key == "redditkey":
            reddit_key_found = True
    
    if reddit_key_found:
        print(f"\n✓ Secret 'redditkey' exists in 'redditscope'")
    else:
        print(f"\n❌ ERROR: Secret 'redditkey' NOT found in 'redditscope'!")
    
    print()
    
except Exception as e:
    print(f"❌ ERROR listing secrets: {e}")
    print()

# ============================================================================
# STEP 3: Get and Validate PAT Token
# ============================================================================

print("[3] RETRIEVING PAT TOKEN")
print("-" * 80)

try:
    # Get the secret value
    token = dbutils.secrets.get(scope="redditscope", key="redditkey")
    
    print(f"✓ Successfully retrieved secret")
    print(f"  Token starts with: {token[:8]}...")
    print(f"  Token length: {len(token)} characters")
    
    # Validate format
    if token.startswith('dapi'):
        print(f"✓ Token format is correct (PAT token)")
    else:
        print(f"⚠️  WARNING: Token doesn't start with 'dapi'")
        print(f"   First 8 chars: {token[:8]}")
        print(f"   This might not be a valid PAT token!")
    
    print()
    
except Exception as e:
    print(f"❌ ERROR retrieving secret: {e}")
    print(f"   This means you don't have permission to read the secret")
    print()
    token = None

# ============================================================================
# STEP 4: Test PAT Token with Databricks API
# ============================================================================

if token:
    print("[4] TESTING PAT TOKEN WITH DATABRICKS API")
    print("-" * 80)
    
    try:
        # Get workspace URL
        workspace_url = spark.conf.get("spark.databricks.workspaceUrl")
        api_url = f"https://{workspace_url}/api/2.0/clusters/list"
        
        print(f"Testing token against: {api_url}")
        
        # Test API call
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        response = requests.get(api_url, headers=headers)
        
        if response.status_code == 200:
            print(f"✓ PAT token is VALID for Databricks API")
            print(f"  Status: {response.status_code}")
            clusters = response.json().get('clusters', [])
            print(f"  Can access {len(clusters)} cluster(s)")
        elif response.status_code == 401:
            print(f"❌ PAT token is INVALID or EXPIRED")
            print(f"  Status: {response.status_code}")
            print(f"  Response: {response.text[:200]}")
        elif response.status_code == 403:
            print(f"⚠️  PAT token is valid but lacks permissions")
            print(f"  Status: {response.status_code}")
            print(f"  Response: {response.text[:200]}")
        else:
            print(f"⚠️  Unexpected response")
            print(f"  Status: {response.status_code}")
            print(f"  Response: {response.text[:200]}")
        
        print()
        
    except Exception as e:
        print(f"❌ ERROR testing token: {e}")
        print()

# ============================================================================
# STEP 5: Test PAT Token with Lakebase PostgreSQL
# ============================================================================

if token:
    print("[5] TESTING PAT TOKEN WITH LAKEBASE POSTGRESQL")
    print("-" * 80)
    
    try:
        import psycopg2
        
        print(f"Attempting connection to Lakebase...")
        print(f"  Host: instance-e2ff35b5-a3fc-44f3-9d65-7cba8332db7c.database.azuredatabricks.net")
        print(f"  User: kevin.ippen@databricks.com")
        print(f"  Database: main")
        print()
        
        # Try to connect
        conn = psycopg2.connect(
            host="instance-e2ff35b5-a3fc-44f3-9d65-7cba8332db7c.database.azuredatabricks.net",
            port=5432,
            database="main",
            user="kevin.ippen@databricks.com",
            password=token,
            sslmode="require",
            connect_timeout=10
        )
        
        print("✓ CONNECTION SUCCESSFUL!")
        print()
        
        # Test query
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM main.fashion_demo.productsdb")
        count = cursor.fetchone()[0]
        
        print(f"✓ Query successful!")
        print(f"  Product count: {count:,}")
        print()
        
        conn.close()
        
        print("✅ PAT TOKEN IS VALID FOR LAKEBASE!")
        print("   The token works - the issue must be elsewhere.")
        print()
        
    except Exception as e:
        error_msg = str(e)
        print(f"❌ CONNECTION FAILED")
        print(f"   Error: {error_msg}")
        print()
        
        if "Failed to decode token" in error_msg:
            print("❌ TOKEN IS INVALID OR EXPIRED FOR LAKEBASE!")
            print()
            print("   Even though the token:")
            print(f"   - Starts with 'dapi' (correct format)")
            print(f"   - Works with Databricks API (if Step 4 passed)")
            print(f"   - Doesn't expire until January")
            print()
            print("   Possible causes:")
            print("   1. Token doesn't have Lakebase access permissions")
            print("   2. Token is for a different workspace")
            print("   3. Lakebase instance requires different authentication")
            print("   4. Token was regenerated but secret not updated")
            print()
            print("   SOLUTION: Generate a NEW PAT token and update the secret")
            print()
        elif "timeout" in error_msg.lower():
            print("⚠️  CONNECTION TIMEOUT")
            print("   Network issue or Lakebase instance not accessible")
            print()
        else:
            print("⚠️  OTHER CONNECTION ERROR")
            print("   Check network, firewall, or Lakebase configuration")
            print()

# ============================================================================
# STEP 6: Check ACLs on Secret Scope
# ============================================================================

print("[6] CHECKING SECRET SCOPE ACLs")
print("-" * 80)

try:
    # Get ACLs for redditscope
    acls = w.secrets.list_acls(scope="redditscope")
    acl_list = list(acls)
    
    print(f"✓ Found {len(acl_list)} ACL(s) on 'redditscope'")
    print()
    
    if len(acl_list) == 0:
        print("⚠️  No ACLs found - scope might be using default permissions")
    else:
        print("ACLs:")
        for acl in acl_list:
            print(f"  - Principal: {acl.principal}")
            print(f"    Permission: {acl.permission}")
            print()
    
except Exception as e:
    print(f"⚠️  Cannot list ACLs: {e}")
    print("   This is normal if you're not the scope owner")
    print()

# ============================================================================
# SUMMARY
# ============================================================================

print("="*80)
print("SUMMARY")
print("="*80)
print()
print("Next steps based on results above:")
print()
print("IF Step 5 shows 'Failed to decode token':")
print("  → Generate NEW PAT token (User Settings > Access Tokens)")
print("  → Update secret: databricks secrets put-secret --scope redditscope --key redditkey")
print("  → Restart your app")
print()
print("IF Step 5 shows 'CONNECTION SUCCESSFUL':")
print("  → Token is valid! Issue is with app configuration")
print("  → Check if app resource is configured in Apps UI")
print("  → Verify app.yaml uses 'valueFrom: lakebase-token'")
print("  → Restart app after adding resource")
print()
print("IF Step 3 fails (cannot retrieve secret):")
print("  → You don't have permission to read the secret")
print("  → Ask workspace admin to grant you READ access to redditscope")
print()
print("="*80)