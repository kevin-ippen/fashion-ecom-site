"""
Lakebase repository for Unity Catalog data access via PostgreSQL
"""
from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from core.config import settings
import logging

logger = logging.getLogger(__name__)


class LakebaseRepository:
    """
    Repository for accessing Unity Catalog tables
    Note: Tables are now fully qualified UC table names (e.g. main.fashion_sota.products_lakebase)
    """

    def __init__(self, session: AsyncSession):
        self.session = session
        # Use fully qualified UC table names
        self.products_table = settings.PRODUCTS_TABLE  # main.fashion_sota.products_lakebase
        self.embeddings_table = settings.EMBEDDINGS_TABLE  # main.fashion_sota.product_embeddings
        self.users_table = settings.USERS_TABLE  # main.fashion_sota.users
        self.user_features_table = settings.USER_FEATURES_TABLE  # main.fashion_sota.user_preferences

    async def _execute_query(self, query: str, params: Optional[Dict] = None) -> List[Dict[str, Any]]:
        """Execute a SQL query and return results as list of dicts"""
        try:
            result = await self.session.execute(text(query), params or {})
            columns = result.keys()
            rows = result.fetchall()
            return [dict(zip(columns, row)) for row in rows]
        except Exception as e:
            logger.error(f"Query execution error: {e}")
            logger.error(f"Query: {query}")
            logger.error(f"Params: {params}")
            raise

    async def get_products(
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

        # Add limit and offset to params
        params["limit"] = limit
        params["offset"] = offset

        query = f"""
            SELECT *
            FROM {self.products_table}
            {where_clause}
            ORDER BY {sort_by} {sort_order}
            LIMIT :limit OFFSET :offset
        """

        return await self._execute_query(query, params)

    async def get_product_count(self, filters: Optional[Dict[str, Any]] = None) -> int:
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
            FROM {self.products_table}
            {where_clause}
        """

        result = await self._execute_query(query, params)
        return result[0]["count"] if result else 0

    async def get_product_by_id(self, product_id: int) -> Optional[Dict[str, Any]]:
        """Get a single product by ID"""
        query = f"""
            SELECT *
            FROM {self.products_table}
            WHERE product_id = :product_id
        """
        results = await self._execute_query(query, {"product_id": product_id})
        return results[0] if results else None

    async def get_product_embeddings(self, product_ids: Optional[List[int]] = None) -> List[Dict[str, Any]]:
        """Get product embeddings, optionally filtered by product IDs"""
        if product_ids:
            # Convert list to SQL IN clause
            ids_str = ", ".join([str(pid) for pid in product_ids])
            where_clause = f"WHERE product_id IN ({ids_str})"
        else:
            where_clause = ""

        query = f"""
            SELECT *
            FROM {self.embeddings_table}
            {where_clause}
        """
        return await self._execute_query(query)

    async def get_users(self) -> List[Dict[str, Any]]:
        """Get all users"""
        query = f"""
            SELECT *
            FROM {self.users_table}
        """
        return await self._execute_query(query)

    async def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get a single user by ID"""
        query = f"""
            SELECT *
            FROM {self.users_table}
            WHERE user_id = :user_id
        """
        results = await self._execute_query(query, {"user_id": user_id})
        return results[0] if results else None

    async def get_user_style_features(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user style features by user ID"""
        query = f"""
            SELECT *
            FROM {self.user_features_table}
            WHERE user_id = :user_id
        """
        results = await self._execute_query(query, {"user_id": user_id})
        return results[0] if results else None

    async def get_filter_options(self) -> Dict[str, List[str]]:
        """Get all available filter options"""
        # Note: PostgreSQL uses array_agg instead of COLLECT_SET
        query = f"""
            SELECT
                array_agg(DISTINCT gender) as genders,
                array_agg(DISTINCT master_category) as master_categories,
                array_agg(DISTINCT sub_category) as sub_categories,
                array_agg(DISTINCT article_type) as article_types,
                array_agg(DISTINCT base_color) as colors,
                array_agg(DISTINCT season) as seasons,
                MIN(price) as min_price,
                MAX(price) as max_price
            FROM {self.products_table}
        """
        results = await self._execute_query(query)
        if results:
            result = results[0]
            return {
                "genders": sorted([g for g in result["genders"] if g]) if result["genders"] else [],
                "master_categories": sorted([c for c in result["master_categories"] if c]) if result["master_categories"] else [],
                "sub_categories": sorted([c for c in result["sub_categories"] if c]) if result["sub_categories"] else [],
                "article_types": sorted([a for a in result["article_types"] if a]) if result["article_types"] else [],
                "colors": sorted([c for c in result["colors"] if c]) if result["colors"] else [],
                "seasons": sorted([s for s in result["seasons"] if s]) if result["seasons"] else [],
                "price_range": {
                    "min": float(result["min_price"]) if result["min_price"] else 0,
                    "max": float(result["max_price"]) if result["max_price"] else 0
                }
            }
        return {}

    async def search_products_by_text(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Search products by text query with NULL handling"""
        
        # Log the search query for debugging
        logger.info(f"Text search: '{query}' in {self.products_table}")

        sql_query = f"""
            SELECT *
            FROM {self.products_table}
            WHERE
                (product_display_name IS NOT NULL AND LOWER(product_display_name) ILIKE :query)
                OR (article_type IS NOT NULL AND LOWER(article_type) ILIKE :query)
                OR (sub_category IS NOT NULL AND LOWER(sub_category) ILIKE :query)
                OR (master_category IS NOT NULL AND LOWER(master_category) ILIKE :query)
                OR (usage IS NOT NULL AND LOWER(usage) ILIKE :query)
            LIMIT :limit
        """
        
        results = await self._execute_query(sql_query, {"query": f"%{query.lower()}%", "limit": limit})
        
        # Log results count for debugging
        logger.info(f"Text search returned {len(results)} results")
        
        return results