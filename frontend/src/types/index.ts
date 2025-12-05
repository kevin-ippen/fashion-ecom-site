export interface Product {
  product_id: string;
  gender: string;
  master_category: string;
  sub_category: string;
  article_type: string;
  base_color: string;
  season: string;
  year: number;
  usage: string;
  product_display_name: string;
  price: number;
  image_path: string;
  ingested_at: string;
  image_url?: string;
  similarity_score?: number;
  personalization_reason?: string;
}

export interface ProductListResponse {
  products: Product[];
  total: number;
  page: number;
  page_size: number;
  has_more: boolean;
}

export interface FilterOptions {
  genders: string[];
  master_categories: string[];
  sub_categories: string[];
  article_types: string[];
  colors: string[];
  seasons: string[];
  price_range: {
    min: number;
    max: number;
  };
}

export interface ProductFilters {
  gender?: string;
  master_category?: string;
  sub_category?: string;
  base_color?: string;
  season?: string;
  min_price?: number;
  max_price?: number;
}

export interface UserPersona {
  user_id: string;
  name: string;
  description: string;
  segment: string;
  avg_price_point: number;
  preferred_categories: string[];
  color_prefs: string[];
  brand_prefs: string[];
  min_price: number;
  max_price: number;
  avg_price: number;
  p25_price: number;
  p75_price: number;
  num_interactions: number;
  style_tags: string[];
}

export interface UserProfile {
  user_id: string;
  segment: string;
  avg_price_point: number;
  preferred_categories: string[];
  color_prefs: string[];
  price_range: {
    min: number;
    max: number;
    avg: number;
  };
  num_interactions: number;
  purchase_history: Product[];
}

export interface SearchResponse {
  products: Product[];
  query?: string;
  search_type: string;
  user_id?: string;
}

export interface CartItem {
  product_id: string;
  quantity: number;
  product?: Product;
}

export interface Cart {
  items: CartItem[];
  total: number;
  item_count: number;
}
