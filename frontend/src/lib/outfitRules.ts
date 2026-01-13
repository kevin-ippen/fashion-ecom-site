/**
 * Outfit category rules for deterministic pairing validation
 *
 * Mirrors the backend OutfitCompatibilityService rules to enable
 * frontend validation of outfit combinations.
 */

import type { Product } from '@/types';

// Product category types for rule matching
export type ProductCategory =
  | 'tops'
  | 'bottoms'
  | 'dress'
  | 'outerwear'
  | 'footwear'
  | 'accessories'
  | 'innerwear'
  | 'sleepwear'
  | 'swimwear'
  | 'unknown';

// Outerwear article types (layering pieces)
const OUTERWEAR_TYPES = new Set([
  'Jackets', 'Blazers', 'Sweaters', 'Sweatshirts', 'Rain Jacket',
  'Nehru Jackets', 'Shrug', 'Coats', 'Cardigans'
]);

// Light outerwear that can layer
const LIGHT_OUTERWEAR = new Set(['Cardigans', 'Shrug']);

// Swimwear types
const SWIMWEAR_TYPES = new Set(['Swimwear']);

// Category pairs that are ALWAYS compatible
const COMPATIBLE_PAIRS = new Set([
  'tops-bottoms', 'tops-outerwear', 'tops-footwear', 'tops-accessories',
  'bottoms-tops', 'bottoms-outerwear', 'bottoms-footwear', 'bottoms-accessories',
  'dress-outerwear', 'dress-footwear', 'dress-accessories',
  'outerwear-tops', 'outerwear-bottoms', 'outerwear-dress', 'outerwear-footwear', 'outerwear-accessories',
  'footwear-tops', 'footwear-bottoms', 'footwear-dress', 'footwear-outerwear', 'footwear-accessories',
  'accessories-tops', 'accessories-bottoms', 'accessories-dress', 'accessories-outerwear', 'accessories-footwear',
]);

/**
 * Categorize a product into a conceptual category for rule matching
 */
export function categorizeProduct(product: Product): ProductCategory {
  const masterCat = product.master_category || '';
  const subCat = product.sub_category || '';
  const articleType = product.article_type || '';

  // Check isolated categories first (highest priority)
  if (subCat === 'Innerwear') {
    return 'innerwear';
  }
  if (subCat === 'Loungewear and Nightwear') {
    return 'sleepwear';
  }
  if (SWIMWEAR_TYPES.has(articleType)) {
    return 'swimwear';
  }

  // Check structural categories
  if (masterCat === 'Footwear') {
    return 'footwear';
  }
  if (masterCat === 'Accessories') {
    return 'accessories';
  }

  // Apparel subcategories
  if (subCat === 'Dress' || subCat === 'Saree') {
    // Sarees and dresses are complete outfits - shouldn't pair with tops/bottoms
    return 'dress';
  }
  if (subCat === 'Bottomwear') {
    return 'bottoms';
  }
  if (subCat === 'Socks' && masterCat === 'Apparel') {
    // Baby booties/socks under Apparel are accessories
    return 'accessories';
  }
  if (subCat === 'Apparel Set') {
    // Clothing sets are complete outfits - treat like dress
    return 'dress';
  }

  // Outerwear vs regular tops
  if (subCat === 'Topwear') {
    if (OUTERWEAR_TYPES.has(articleType)) {
      return 'outerwear';
    }
    return 'tops';
  }

  // Default to accessories for unknown apparel items
  if (masterCat === 'Apparel') {
    return 'accessories';
  }

  return 'unknown';
}

/**
 * Check if two products have compatible genders for outfit pairing
 */
export function isGenderCompatible(source: Product, target: Product): boolean {
  const sourceGender = source.gender || '';
  const targetGender = target.gender || '';

  const adultGenders = new Set(['Men', 'Women', 'Unisex']);
  const kidsGenders = new Set(['Boys', 'Girls']);

  const sourceIsAdult = adultGenders.has(sourceGender);
  const sourceIsKids = kidsGenders.has(sourceGender);
  const targetIsAdult = adultGenders.has(targetGender);
  const targetIsKids = kidsGenders.has(targetGender);

  // NEVER: Adult with kids
  if ((sourceIsAdult && targetIsKids) || (sourceIsKids && targetIsAdult)) {
    return false;
  }

  // Unisex works with any adult gender
  if (sourceGender === 'Unisex' || targetGender === 'Unisex') {
    return true;
  }

  // Same gender always works
  if (sourceGender === targetGender) {
    return true;
  }

  // Men and Women don't mix
  if (sourceGender === 'Men' && targetGender === 'Women') {
    return false;
  }
  if (sourceGender === 'Women' && targetGender === 'Men') {
    return false;
  }

  // Boys and Girls don't mix
  if (sourceGender === 'Boys' && targetGender === 'Girls') {
    return false;
  }
  if (sourceGender === 'Girls' && targetGender === 'Boys') {
    return false;
  }

  return true;
}

/**
 * Check if two products' categories are compatible for an outfit
 *
 * Core rules:
 * - NO duplicate categories (2 tops, 2 bottoms, 2 footwear, etc.)
 * - NO dress with tops/bottoms (dress is complete)
 * - NO innerwear/sleepwear/swimwear with regular apparel
 * - Gender must be compatible
 */
export function isCategoryCompatible(source: Product, target: Product): boolean {
  const sourceCat = categorizeProduct(source);
  const targetCat = categorizeProduct(target);

  // NEVER: Unknown categories (miscategorized products)
  if (sourceCat === 'unknown' || targetCat === 'unknown') {
    return false;
  }

  // NEVER: Isolated categories with anything
  const isolatedCategories = new Set(['innerwear', 'sleepwear', 'swimwear']);
  if (isolatedCategories.has(sourceCat) || isolatedCategories.has(targetCat)) {
    return false;
  }

  // NEVER: Gender incompatibility
  if (!isGenderCompatible(source, target)) {
    return false;
  }

  // NEVER: Same category duplicates (except outerwear layering)
  if (sourceCat === targetCat) {
    // Special case: outerwear layering allowed for different article types
    if (sourceCat === 'outerwear') {
      const sourceArticle = source.article_type || '';
      const targetArticle = target.article_type || '';
      if (sourceArticle !== targetArticle) {
        // Allow light outerwear combinations
        if (LIGHT_OUTERWEAR.has(sourceArticle) || LIGHT_OUTERWEAR.has(targetArticle)) {
          return true;
        }
      }
    }
    return false;
  }

  // NEVER: Dress with tops or bottoms (dress is complete)
  if (sourceCat === 'dress' && (targetCat === 'tops' || targetCat === 'bottoms')) {
    return false;
  }
  if (targetCat === 'dress' && (sourceCat === 'tops' || sourceCat === 'bottoms')) {
    return false;
  }

  // Check against compatible pairs
  const pairKey = `${sourceCat}-${targetCat}`;
  if (COMPATIBLE_PAIRS.has(pairKey)) {
    return true;
  }

  // Default: allow if not explicitly blocked
  return true;
}

/**
 * Filter outfit recommendations to remove incompatible pairings
 *
 * @param sourceProduct The product being viewed
 * @param candidates List of candidate products for "Complete the Look"
 * @returns Filtered list with only compatible products
 */
export function filterCompatibleOutfitItems(
  sourceProduct: Product,
  candidates: Product[]
): Product[] {
  const sourceId = sourceProduct.product_id;
  const seen = new Set<string>([sourceId]);

  return candidates.filter(candidate => {
    // Skip duplicates
    if (seen.has(candidate.product_id)) {
      return false;
    }
    seen.add(candidate.product_id);

    // Check compatibility
    return isCategoryCompatible(sourceProduct, candidate);
  });
}

/**
 * Ensure outfit recommendations have category diversity
 * Prevents all items being from the same category (e.g., all accessories)
 *
 * @param sourceProduct The product being viewed
 * @param candidates List of candidate products
 * @param maxPerCategory Maximum items per category (default 2)
 * @returns Diversified list
 */
export function diversifyByCategory(
  candidates: Product[],
  maxPerCategory: number = 2
): Product[] {
  const categoryCounts = new Map<ProductCategory, number>();

  return candidates.filter(product => {
    const cat = categorizeProduct(product);
    const count = categoryCounts.get(cat) || 0;

    if (count >= maxPerCategory) {
      return false;
    }

    categoryCounts.set(cat, count + 1);
    return true;
  });
}

/**
 * Get a human-readable description of why two items are incompatible
 */
export function getIncompatibilityReason(source: Product, target: Product): string | null {
  const sourceCat = categorizeProduct(source);
  const targetCat = categorizeProduct(target);

  // Same category
  if (sourceCat === targetCat && sourceCat !== 'outerwear') {
    const categoryNames: Record<ProductCategory, string> = {
      tops: 'tops',
      bottoms: 'bottoms',
      dress: 'dresses',
      outerwear: 'outerwear',
      footwear: 'footwear',
      accessories: 'accessories',
      innerwear: 'innerwear',
      sleepwear: 'sleepwear',
      swimwear: 'swimwear',
      unknown: 'items',
    };
    return `Cannot pair two ${categoryNames[sourceCat]} together`;
  }

  // Dress with tops/bottoms
  if (sourceCat === 'dress' && (targetCat === 'tops' || targetCat === 'bottoms')) {
    return 'Dresses are complete outfits - no additional tops or bottoms needed';
  }
  if (targetCat === 'dress' && (sourceCat === 'tops' || sourceCat === 'bottoms')) {
    return 'Dresses are complete outfits - no additional tops or bottoms needed';
  }

  // Gender mismatch
  if (!isGenderCompatible(source, target)) {
    return `${source.gender} items cannot be paired with ${target.gender} items`;
  }

  // Isolated categories
  const isolatedCategories = new Set(['innerwear', 'sleepwear', 'swimwear']);
  if (isolatedCategories.has(sourceCat)) {
    return `${source.sub_category} items are not typically shown in outfit pairings`;
  }
  if (isolatedCategories.has(targetCat)) {
    return `${target.sub_category} items are not typically shown in outfit pairings`;
  }

  return null;
}
