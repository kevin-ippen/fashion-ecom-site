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
        # Use PostgreSQL schema.table format (not UC format)
        # When querying through Lakebase PostgreSQL, use schema.table, not catalog.schema.table
        self.schema = settings.LAKEBASE_SCHEMA  # fashion_sota
        self.products_table = f"{self.schema}.{settings.LAKEBASE_PRODUCTS_TABLE}"  # fashion_sota.products_lakebase
        self.embeddings_table = f"{self.schema}.product_embeddings"  # fashion_sota.product_embeddings (if synced)
        self.users_table = f"{self.schema}.{settings.LAKEBASE_USERS_TABLE}"  # fashion_sota.users_lakebase (taste_embedding as JSON string)

    def _get_base_product_filter(self) -> str:
        """
        Get base WHERE clause to filter product categories for the storefront.

        Excludes certain subcategories and article types that are outside
        the target product assortment for this demo application.
        """
        return """
            master_category IN ('Apparel', 'Accessories', 'Footwear')
            AND sub_category NOT IN (
                'Innerwear', 'Loungewear and Nightwear', 'Free Gifts', 'Fragrance', 'Skin Care',
                'Saree', 'Kurta', 'Kurtas', 'Dupatta', 'Churidar', 'Salwar', 'Lehenga Choli',
                'Kameez', 'Dhoti', 'Patiala', 'Kurta Sets', 'Sarees', 'Salwar and Dupatta', 'Lehenga'
            )
            AND article_type NOT IN (
                'Swimwear', 'Free Gifts', 'Perfume and Body Mist', 'Mens Grooming Kit',
                'Saree', 'Sarees', 'Kurta', 'Kurtas', 'Dupatta', 'Churidar', 'Salwar',
                'Lehenga Choli', 'Kameez', 'Dhoti', 'Patiala'
            )
        """

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
        where_clauses = [f"({self._get_base_product_filter()})"]  # Always apply base filter
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

            if filters.get("min_year"):
                where_clauses.append("year >= :min_year")
                params["min_year"] = filters["min_year"]

            if filters.get("max_year"):
                where_clauses.append("year <= :max_year")
                params["max_year"] = filters["max_year"]

            # Keyword filtering with OR logic (matches sub_category, article_type, or product name)
            if filters.get("keywords"):
                keywords = filters["keywords"]
                keyword_conditions = []
                for i, keyword in enumerate(keywords):
                    param_name = f"keyword_{i}"
                    keyword_conditions.append(
                        f"(sub_category ILIKE :{param_name} OR article_type ILIKE :{param_name} OR product_display_name ILIKE :{param_name})"
                    )
                    params[param_name] = f"%{keyword}%"
                where_clauses.append(f"({' OR '.join(keyword_conditions)})")

        where_clause = f"WHERE {' AND '.join(where_clauses)}"

        # Add limit and offset to params
        params["limit"] = limit
        params["offset"] = offset

        # Use RANDOM() for sort_by="RANDOM" to get true SQL-level randomization
        if sort_by == "RANDOM":
            order_clause = "ORDER BY RANDOM()"
        else:
            order_clause = f"ORDER BY {sort_by} {sort_order}"

        query = f"""
            SELECT *
            FROM {self.products_table}
            {where_clause}
            {order_clause}
            LIMIT :limit OFFSET :offset
        """

        results = await self._execute_query(query, params)
        return [self._parse_jsonb_columns(r) for r in results]

    async def get_product_count(self, filters: Optional[Dict[str, Any]] = None) -> int:
        """Get total count of products matching filters"""
        where_clauses = [f"({self._get_base_product_filter()})"]  # Always apply base filter
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

            # Keyword filtering with OR logic (same as get_products)
            if filters.get("keywords"):
                keywords = filters["keywords"]
                keyword_conditions = []
                for i, keyword in enumerate(keywords):
                    param_name = f"keyword_{i}"
                    keyword_conditions.append(
                        f"(sub_category ILIKE :{param_name} OR article_type ILIKE :{param_name} OR product_display_name ILIKE :{param_name})"
                    )
                    params[param_name] = f"%{keyword}%"
                where_clauses.append(f"({' OR '.join(keyword_conditions)})")

        where_clause = f"WHERE {' AND '.join(where_clauses)}"

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
                AND ({self._get_base_product_filter()})
        """
        results = await self._execute_query(query, {"product_id": product_id})
        if results:
            return self._parse_jsonb_columns(results[0])
        return None

    async def get_products_by_ids(
        self,
        product_ids: List[int],
        preserve_order: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Get multiple products by IDs efficiently (batch lookup).

        Args:
            product_ids: List of product IDs to fetch
            preserve_order: If True, returns products in same order as input IDs

        Returns:
            List of product dictionaries
        """
        if not product_ids:
            return []

        # Use ANY for efficient batch lookup
        ids_array = list(set(product_ids))  # Dedupe
        query = f"""
            SELECT *
            FROM {self.products_table}
            WHERE product_id = ANY(:ids)
                AND ({self._get_base_product_filter()})
        """
        results = await self._execute_query(query, {"ids": ids_array})

        # Parse JSONB columns
        parsed_results = [self._parse_jsonb_columns(r) for r in results]

        if preserve_order and results:
            # Create lookup map for O(1) access
            products_map = {p["product_id"]: p for p in parsed_results}
            # Return in original order, skipping missing products
            return [products_map[pid] for pid in product_ids if pid in products_map]

        return parsed_results

    def _parse_jsonb_columns(self, product: Dict[str, Any]) -> Dict[str, Any]:
        """Parse JSONB columns from string to Python objects if needed"""
        import json

        def parse_id_list(val):
            """Parse JSON string to list of integers"""
            if val is None:
                return []
            if isinstance(val, str):
                try:
                    parsed = json.loads(val)
                    # Convert string IDs to integers
                    return [int(x) for x in parsed if x]
                except (json.JSONDecodeError, TypeError, ValueError):
                    return []
            if isinstance(val, list):
                # Already a list, but might contain strings
                return [int(x) for x in val if x]
            return []

        # Handle similar_product_ids
        if "similar_product_ids" in product:
            product["similar_product_ids"] = parse_id_list(product["similar_product_ids"])

        # Handle complete_the_set_ids
        if "complete_the_set_ids" in product:
            product["complete_the_set_ids"] = parse_id_list(product["complete_the_set_ids"])

        return product

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
        """
        Get user with taste embedding (backwards compatibility method)
        Note: taste_embedding is now in the users table itself
        """
        # Just return the user record - it includes taste_embedding
        return await self.get_user_by_id(user_id)

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
            WHERE ({self._get_base_product_filter()})
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

    async def get_products_category_balanced(
        self,
        limit: int = 24,
        offset: int = 0,
        filters: Optional[Dict[str, Any]] = None,
        category_weights: Optional[Dict[str, float]] = None
    ) -> List[Dict[str, Any]]:
        """
        Get products with category-balanced sampling for better diversity.

        Instead of pure random sampling (which can skew toward dominant categories),
        this samples products per category based on weights, then interleaves them.

        Args:
            limit: Total number of products to return
            offset: Pagination offset
            filters: Optional filters (price, color, etc.)
            category_weights: Dict of {master_category: weight}, e.g. {"Apparel": 0.5, "Footwear": 0.3, "Accessories": 0.2}
                             If not provided, uses equal weighting across categories.

        Returns:
            List of products with category diversity
        """
        # Default weights if not specified
        if not category_weights:
            category_weights = {"Apparel": 0.50, "Footwear": 0.25, "Accessories": 0.25}

        # Build base where clause
        where_clauses = [f"({self._get_base_product_filter()})"]
        params = {}

        if filters:
            if filters.get("gender"):
                where_clauses.append("gender = :gender")
                params["gender"] = filters["gender"]

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

            # Note: master_category is handled per-category below
            # Keyword filtering
            if filters.get("keywords"):
                keywords = filters["keywords"]
                keyword_conditions = []
                for i, keyword in enumerate(keywords):
                    param_name = f"keyword_{i}"
                    keyword_conditions.append(
                        f"(sub_category ILIKE :{param_name} OR article_type ILIKE :{param_name} OR product_display_name ILIKE :{param_name})"
                    )
                    params[param_name] = f"%{keyword}%"
                where_clauses.append(f"({' OR '.join(keyword_conditions)})")

        base_where = f"WHERE {' AND '.join(where_clauses)}"

        # Sample products per category
        all_products = []
        for category, weight in category_weights.items():
            cat_limit = max(1, int(limit * weight * 2))  # Sample 2x for pagination

            cat_query = f"""
                SELECT *
                FROM {self.products_table}
                {base_where}
                    AND master_category = :cat_{category}
                ORDER BY RANDOM()
                LIMIT :cat_limit_{category}
            """
            params[f"cat_{category}"] = category
            params[f"cat_limit_{category}"] = cat_limit

            try:
                cat_products = await self._execute_query(cat_query, params)
                all_products.extend([self._parse_jsonb_columns(p) for p in cat_products])
                logger.debug(f"Category {category}: sampled {len(cat_products)} products")
            except Exception as e:
                logger.warning(f"Error sampling {category}: {e}")

        # Interleave products from different categories for diversity
        # Group by category
        by_category = {}
        for p in all_products:
            cat = p.get("master_category", "Other")
            if cat not in by_category:
                by_category[cat] = []
            by_category[cat].append(p)

        # Round-robin interleave
        interleaved = []
        category_lists = list(by_category.values())
        max_len = max(len(lst) for lst in category_lists) if category_lists else 0

        for i in range(max_len):
            for cat_list in category_lists:
                if i < len(cat_list):
                    interleaved.append(cat_list[i])

        # Apply offset and limit
        result = interleaved[offset:offset + limit]
        logger.info(f"Category-balanced sampling: {len(result)} products ({dict((k, len(v)) for k, v in by_category.items())})")

        return result

    async def search_products_by_text(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Search products by text query with NULL handling"""

        # Log the search query for debugging
        logger.info(f"Text search: '{query}' in {self.products_table}")

        sql_query = f"""
            SELECT *
            FROM {self.products_table}
            WHERE
                ({self._get_base_product_filter()})
                AND (
                    (product_display_name IS NOT NULL AND LOWER(product_display_name) ILIKE :query)
                    OR (article_type IS NOT NULL AND LOWER(article_type) ILIKE :query)
                    OR (sub_category IS NOT NULL AND LOWER(sub_category) ILIKE :query)
                    OR (master_category IS NOT NULL AND LOWER(master_category) ILIKE :query)
                    OR (usage IS NOT NULL AND LOWER(usage) ILIKE :query)
                )
            LIMIT :limit
        """

        results = await self._execute_query(sql_query, {"query": f"%{query.lower()}%", "limit": limit})

        # Log results count for debugging
        logger.info(f"Text search returned {len(results)} results")

        return [self._parse_jsonb_columns(r) for r in results]