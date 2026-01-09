#!/usr/bin/env python3
"""Check Saree data in database"""
from databricks.sdk import WorkspaceClient

w = WorkspaceClient()

query = """
SELECT DISTINCT article_type, sub_category, master_category, COUNT(*) as count
FROM main.fashion_sota.products_lakebase
WHERE LOWER(article_type) LIKE '%saree%'
   OR LOWER(article_type) LIKE '%sari%'
   OR LOWER(product_display_name) LIKE '%saree%'
   OR LOWER(product_display_name) LIKE '%sari%'
GROUP BY article_type, sub_category, master_category
ORDER BY count DESC
"""

execution = w.statement_execution.execute_statement(
    statement=query,
    warehouse_id="148ccb90800933a1"
)

if execution.result and execution.result.data_array:
    print("Saree/Sari products found:")
    print("-" * 80)
    for row in execution.result.data_array:
        article_type, sub_category, master_category, count = row
        print(f"  Article: {article_type}")
        print(f"  Sub-Category: {sub_category}")
        print(f"  Master Category: {master_category}")
        print(f"  Count: {count}")
        print("-" * 80)
else:
    print("No Saree/Sari products found")
