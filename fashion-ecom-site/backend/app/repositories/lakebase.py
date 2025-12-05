"""
Lakebase repository for Unity Catalog data access
"""
from typing import List, Optional, Dict, Any
from databricks import sql
from databricks.sdk import WorkspaceClient
from app.core.config import settings
import json


class LakebaseRepository:
    """Repository for accessing Unity Catalog tables via Lakebase"""

    def __init__(self):
        self.catalog = settings.CATALOG
        self.schema = settings.SCHEMA
        self.connection = None

    def _get_connection(self):
        """Get or create Databricks SQL connection"""
        if self.connection is None:
            self.connection = sql.connect(
                server_hostname=settings.DATABRICKS_HOST,
                http_path=settings.DATABRICKS_HTTP_PATH,
                access_token=settings.DATABRICKS_TOKEN
            )
        return self.connection

    def _execute_query(self, query: str, params: Optional[Dict] = None) -> List[Dict[str, Any]]:
        """Execute a SQL query and return results as list of dicts"""
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(query, params or {})
            columns = [desc[0] for desc in cursor.description]
            results = []
            for row in cursor.fetchall():
                results.append(dict(zip(columns, row)))
            return results
        finally:
            cursor.close()

    def get_products(
        self,
        limit: int = 24,
        offset: int = 0,
        filters: Optional[Dict[str, Any]] = None,
        sort_by: str = "product_display_name",
        sort_order: str = "ASC"
    ) -> List[Dict[str, Any]]:
        """Get products with optional filtering and pagination"""
        where_clauses = []
        params = {}

        if filters:
            if filters.get("gender"):
                where_clauses.append("gender = :gender")
                params["gender"] = filters["gender"]

            if filters.get("master_category"):
                where_clauses.append("master_category = :master_category")
                params["master_category"] = filters["master_category"]

            if filters.get("sub_category"):
                where_clauses.append("sub_category = :sub_category")
                params["sub_category"] = filters["sub_category"]

            if filters.get("base_color"):
                where_clauses.append("base_color = :base_color")
                params["base_color"] = filters["base_color"]

            if filters.get("season"):
                where_clauses.append("season = :season")
                params["season"] = filters["season"]

            if filters.get("min_price"):
                where_clauses.append("price >= :min_price")
                params["min_price"] = filters["min_price"]

            if filters.get("max_price"):
                where_clauses.append("price <= :max_price")
                params["max_price"] = filters["max_price"]

        where_clause = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

        query = f"""
            SELECT *
            FROM {self.catalog}.{self.schema}.{settings.PRODUCTS_TABLE}
            {where_clause}
            ORDER BY {sort_by} {sort_order}
            LIMIT {limit} OFFSET {offset}
        """

        return self._execute_query(query, params)

    def get_product_count(self, filters: Optional[Dict[str, Any]] = None) -> int:
        """Get total count of products matching filters"""
        where_clauses = []
        params = {}

        if filters:
            if filters.get("gender"):
                where_clauses.append("gender = :gender")
                params["gender"] = filters["gender"]

            if filters.get("master_category"):
                where_clauses.append("master_category = :master_category")
                params["master_category"] = filters["master_category"]

            if filters.get("sub_category"):
                where_clauses.append("sub_category = :sub_category")
                params["sub_category"] = filters["sub_category"]

            if filters.get("base_color"):
                where_clauses.append("base_color = :base_color")
                params["base_color"] = filters["base_color"]

            if filters.get("min_price"):
                where_clauses.append("price >= :min_price")
                params["min_price"] = filters["min_price"]

            if filters.get("max_price"):
                where_clauses.append("price <= :max_price")
                params["max_price"] = filters["max_price"]

        where_clause = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

        query = f"""
            SELECT COUNT(*) as count
            FROM {self.catalog}.{self.schema}.{settings.PRODUCTS_TABLE}
            {where_clause}
        """

        result = self._execute_query(query, params)
        return result[0]["count"] if result else 0

    def get_product_by_id(self, product_id: str) -> Optional[Dict[str, Any]]:
        """Get a single product by ID"""
        query = f"""
            SELECT *
            FROM {self.catalog}.{self.schema}.{settings.PRODUCTS_TABLE}
            WHERE product_id = :product_id
        """
        results = self._execute_query(query, {"product_id": product_id})
        return results[0] if results else None

    def get_product_embeddings(self, product_ids: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Get product embeddings, optionally filtered by product IDs"""
        if product_ids:
            # Convert list to SQL IN clause
            ids_str = ", ".join([f"'{pid}'" for pid in product_ids])
            where_clause = f"WHERE product_id IN ({ids_str})"
        else:
            where_clause = ""

        query = f"""
            SELECT *
            FROM {self.catalog}.{self.schema}.{settings.EMBEDDINGS_TABLE}
            {where_clause}
        """
        return self._execute_query(query)

    def get_users(self) -> List[Dict[str, Any]]:
        """Get all users"""
        query = f"""
            SELECT *
            FROM {self.catalog}.{self.schema}.{settings.USERS_TABLE}
        """
        return self._execute_query(query)

    def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get a single user by ID"""
        query = f"""
            SELECT *
            FROM {self.catalog}.{self.schema}.{settings.USERS_TABLE}
            WHERE user_id = :user_id
        """
        results = self._execute_query(query, {"user_id": user_id})
        return results[0] if results else None

    def get_user_style_features(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user style features by user ID"""
        query = f"""
            SELECT *
            FROM {self.catalog}.{self.schema}.{settings.USER_FEATURES_TABLE}
            WHERE user_id = :user_id
        """
        results = self._execute_query(query, {"user_id": user_id})
        return results[0] if results else None

    def get_filter_options(self) -> Dict[str, List[str]]:
        """Get all available filter options"""
        query = f"""
            SELECT
                COLLECT_SET(gender) as genders,
                COLLECT_SET(master_category) as master_categories,
                COLLECT_SET(sub_category) as sub_categories,
                COLLECT_SET(article_type) as article_types,
                COLLECT_SET(base_color) as colors,
                COLLECT_SET(season) as seasons,
                MIN(price) as min_price,
                MAX(price) as max_price
            FROM {self.catalog}.{self.schema}.{settings.PRODUCTS_TABLE}
        """
        results = self._execute_query(query)
        if results:
            result = results[0]
            return {
                "genders": sorted(result["genders"]) if result["genders"] else [],
                "master_categories": sorted(result["master_categories"]) if result["master_categories"] else [],
                "sub_categories": sorted(result["sub_categories"]) if result["sub_categories"] else [],
                "article_types": sorted(result["article_types"]) if result["article_types"] else [],
                "colors": sorted(result["colors"]) if result["colors"] else [],
                "seasons": sorted(result["seasons"]) if result["seasons"] else [],
                "price_range": {
                    "min": float(result["min_price"]) if result["min_price"] else 0,
                    "max": float(result["max_price"]) if result["max_price"] else 0
                }
            }
        return {}

    def search_products_by_text(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Search products by text query (simple LIKE search for now)"""
        sql_query = f"""
            SELECT *
            FROM {self.catalog}.{self.schema}.{settings.PRODUCTS_TABLE}
            WHERE LOWER(product_display_name) LIKE :query
                OR LOWER(article_type) LIKE :query
                OR LOWER(sub_category) LIKE :query
            LIMIT {limit}
        """
        return self._execute_query(sql_query, {"query": f"%{query.lower()}%"})

    def close(self):
        """Close the database connection"""
        if self.connection:
            self.connection.close()
            self.connection = None


# Global repository instance
lakebase_repo = LakebaseRepository()
