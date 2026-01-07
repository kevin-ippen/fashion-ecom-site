"""
Neighborhood-Based Pattern Application Service

Applies outfit patterns from similar anchor products by:
1. Finding 2-3 similar anchors for a target product
2. Finding each anchor's "neighborhood" of similar products
3. Applying anchor patterns within those neighborhoods
4. Generating natural outfit variations
"""

import logging
from typing import List, Dict, Any, Optional
from collections import defaultdict
import random

logger = logging.getLogger(__name__)


class NeighborhoodPatternService:
    """Service for applying patterns using anchor neighborhoods"""

    def __init__(self):
        self.anchors = None
        self.patterns_by_anchor = None
        logger.info("🎨 NeighborhoodPatternService initialized")

    def load_patterns(self, patterns: List[Dict[str, Any]]):
        """Load patterns and organize by anchor"""
        self.patterns_by_anchor = defaultdict(list)

        for pattern in patterns:
            anchor_id = pattern.get('anchor_id')
            if anchor_id:
                self.patterns_by_anchor[anchor_id].append(pattern)

        logger.info(f"Loaded {len(patterns)} patterns for {len(self.patterns_by_anchor)} anchors")

    def load_anchors(self, anchors: List[Dict[str, Any]]):
        """Load anchor products"""
        self.anchors = {a['product_id']: a for a in anchors}
        logger.info(f"Loaded {len(self.anchors)} anchor products")

    def find_similar_anchors(
        self,
        target_product: Dict[str, Any],
        top_k: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Find most similar anchor products using metadata similarity

        Args:
            target_product: Target product dict
            top_k: Number of similar anchors to return

        Returns:
            List of (anchor, similarity_score) tuples
        """
        if not self.anchors:
            logger.warning("No anchors loaded")
            return []

        # Calculate similarity scores
        scores = []

        target_category = target_product.get('master_category')
        target_subcat = target_product.get('sub_category')
        target_gender = target_product.get('gender')
        target_usage = target_product.get('usage', 'Casual')
        target_season = target_product.get('season', 'All-Season')

        # Normalize color to color_family
        target_color = target_product.get('base_color', '')
        if target_color in ['Black', 'White', 'Grey', 'Navy', 'Beige', 'Cream']:
            target_color_family = 'Neutral'
        elif target_color in ['Red', 'Orange', 'Yellow', 'Pink']:
            target_color_family = 'Warm'
        elif target_color in ['Blue', 'Green', 'Purple']:
            target_color_family = 'Cool'
        else:
            target_color_family = 'Bright'

        for anchor_id, anchor in self.anchors.items():
            score = 0.0

            # Category match (most important)
            if anchor.get('master_category') == target_category:
                score += 30

            if anchor.get('sub_category') == target_subcat:
                score += 20

            # Gender match
            if anchor.get('gender') == target_gender:
                score += 15

            # Color family match
            if anchor.get('color_family') == target_color_family:
                score += 10

            # Usage match
            if anchor.get('usage') == target_usage:
                score += 10

            # Season match
            if anchor.get('season') == target_season:
                score += 5

            # Must have at least category match
            if score >= 30:
                scores.append((anchor, score))

        # Sort by score and take top k
        scores.sort(key=lambda x: x[1], reverse=True)

        similar_anchors = [(a, s/100.0) for a, s in scores[:top_k]]

        logger.debug(f"Found {len(similar_anchors)} similar anchors for {target_product.get('product_id')}")

        return similar_anchors

    async def find_anchor_neighborhood(
        self,
        anchor: Dict[str, Any],
        vector_search_service,
        neighborhood_size: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Find products similar to an anchor (anchor's "neighborhood")

        Uses vector search to find visually and semantically similar products

        Args:
            anchor: Anchor product dict
            vector_search_service: Vector search service instance
            neighborhood_size: Number of neighbors to find

        Returns:
            List of neighbor products
        """
        try:
            # Get anchor's embedding from vector search index
            from databricks.sdk import WorkspaceClient
            w = WorkspaceClient()

            # Query to get anchor's embedding
            embedding_query = f"""
            SELECT embedding
            FROM main.fashion_sota.product_embeddings
            WHERE product_id = {anchor['product_id']}
            """

            execution = w.statement_execution.execute_statement(
                statement=embedding_query,
                warehouse_id="148ccb90800933a1"
            )
            result = execution.result

            if not result or not result.data_array:
                logger.warning(f"No embedding found for anchor {anchor['product_id']}")
                return []

            # Get embedding
            embedding_data = result.data_array[0][0]
            if isinstance(embedding_data, str):
                import json
                embedding_data = json.loads(embedding_data)

            import numpy as np
            anchor_embedding = np.array(embedding_data, dtype=np.float32)

            # Normalize
            norm = np.linalg.norm(anchor_embedding)
            if norm > 0:
                anchor_embedding = anchor_embedding / norm

            # Search for similar products (neighborhood)
            neighbors = await vector_search_service.search(
                query_vector=anchor_embedding,
                index_name=vector_search_service.index_name,
                num_results=neighborhood_size,
                filters=None
            )

            logger.debug(f"Found {len(neighbors)} neighbors for anchor {anchor['product_id']}")

            return neighbors

        except Exception as e:
            logger.error(f"Error finding neighborhood: {e}")
            return []

    def apply_pattern_in_neighborhood(
        self,
        target_product: Dict[str, Any],
        pattern: Dict[str, Any],
        neighborhood: List[Dict[str, Any]],
        lakebase_repo
    ) -> List[Dict[str, Any]]:
        """
        Apply a pattern to find matches within a neighborhood

        Args:
            target_product: Target product
            pattern: Pattern to apply
            neighborhood: List of neighbor products
            lakebase_repo: Repository for full product data

        Returns:
            List of recommended products
        """
        recommendations = []
        target_gender = target_product.get('gender')

        for item_spec in pattern.get('items', []):
            role = item_spec.get('role')
            required = item_spec.get('required', True)

            if not required and random.random() > 0.5:
                continue  # Skip optional items randomly

            # Filter neighborhood by item specifications
            matches = []

            for neighbor in neighborhood:
                # Skip target product itself
                if neighbor.get('product_id') == target_product.get('product_id'):
                    continue

                # Check category match
                neighbor_category = neighbor.get('master_category', '')
                neighbor_subcat = neighbor.get('sub_category', '')

                # Match categories
                categories = item_spec.get('categories', [])
                subcategories = item_spec.get('subcategories', [])

                category_match = False
                for cat in categories:
                    if '/' in cat:
                        # Format: "Apparel/Topwear"
                        cat_parts = cat.split('/')
                        if len(cat_parts) == 2:
                            if neighbor_category == cat_parts[0]:
                                category_match = True
                    elif cat == neighbor_category:
                        category_match = True

                if not category_match:
                    continue

                # Subcategory match (if specified)
                if subcategories:
                    if neighbor_subcat not in subcategories:
                        continue

                # Gender match
                if target_gender and neighbor.get('gender') != target_gender:
                    continue

                # Color compatibility
                colors = item_spec.get('colors', [])
                if colors:
                    neighbor_color = neighbor.get('base_color', '')
                    if neighbor_color not in colors:
                        # Allow neutral colors always
                        if neighbor_color not in ['Black', 'White', 'Grey', 'Navy', 'Beige']:
                            continue

                matches.append(neighbor)

            # Pick best match from filtered neighbors
            if matches:
                # Add some randomness for diversity
                if len(matches) > 3:
                    selected = random.choice(matches[:5])
                else:
                    selected = matches[0]

                recommendations.append(selected)

        return recommendations

    async def generate_recommendations(
        self,
        target_product: Dict[str, Any],
        vector_search_service,
        lakebase_repo,
        limit: int = 4
    ) -> List[Dict[str, Any]]:
        """
        Generate outfit recommendations for a target product

        Uses neighborhood-based pattern application:
        1. Find similar anchors
        2. Get each anchor's neighborhood
        3. Apply anchor patterns within neighborhoods
        4. Diversify and return top recommendations

        Args:
            target_product: Target product dict
            vector_search_service: Vector search service
            lakebase_repo: Lakebase repository
            limit: Number of recommendations

        Returns:
            List of recommended products
        """
        try:
            logger.info(f"Generating recommendations for {target_product.get('product_id')}")

            # Step 1: Find similar anchors
            similar_anchors = self.find_similar_anchors(target_product, top_k=2)

            if not similar_anchors:
                logger.warning(f"No similar anchors found for {target_product.get('product_id')}")
                return []

            logger.info(f"Found {len(similar_anchors)} similar anchors")

            # Step 2 & 3: For each anchor, find neighborhood and apply patterns
            all_recommendations = []

            for anchor, similarity in similar_anchors:
                anchor_id = anchor['product_id']

                # Get patterns for this anchor
                patterns = self.patterns_by_anchor.get(anchor_id, [])
                if not patterns:
                    logger.debug(f"No patterns for anchor {anchor_id}")
                    continue

                logger.info(f"Anchor {anchor_id} has {len(patterns)} patterns")

                # Find anchor's neighborhood
                neighborhood = await self.find_anchor_neighborhood(
                    anchor,
                    vector_search_service,
                    neighborhood_size=50
                )

                if not neighborhood:
                    logger.warning(f"No neighborhood found for anchor {anchor_id}")
                    continue

                logger.info(f"Anchor {anchor_id} neighborhood: {len(neighborhood)} products")

                # Apply each pattern in the neighborhood
                for pattern in patterns[:2]:  # Use top 2 patterns per anchor
                    recs = self.apply_pattern_in_neighborhood(
                        target_product,
                        pattern,
                        neighborhood,
                        lakebase_repo
                    )

                    if recs:
                        # Add pattern context
                        for rec in recs:
                            rec['pattern_name'] = pattern.get('name')
                            rec['anchor_similarity'] = similarity

                        all_recommendations.extend(recs)

            # Step 4: Diversify and return top recommendations
            if not all_recommendations:
                logger.warning(f"No recommendations generated for {target_product.get('product_id')}")
                return []

            # Deduplicate
            seen_ids = set()
            unique_recs = []
            for rec in all_recommendations:
                rec_id = rec.get('product_id')
                if rec_id not in seen_ids:
                    seen_ids.add(rec_id)
                    unique_recs.append(rec)

            # Diversify by category
            from services.outfit_compatibility_service import outfit_compatibility_service
            diversified = outfit_compatibility_service.diversify_by_category(
                unique_recs,
                limit=limit
            )

            logger.info(f"✅ Generated {len(diversified)} recommendations")

            return diversified[:limit]

        except Exception as e:
            logger.error(f"Error generating recommendations: {e}")
            import traceback
            traceback.print_exc()
            return []


# Singleton instance
neighborhood_pattern_service = NeighborhoodPatternService()
