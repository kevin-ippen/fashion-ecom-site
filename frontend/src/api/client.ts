import axios from 'axios';
import type {
  ProductListResponse,
  Product,
  FilterOptions,
  UserPersona,
  UserProfile,
  SearchResponse,
  ProductFilters,
} from '@/types';

const API_BASE = '/api/v1';

const apiClient = axios.create({
  baseURL: API_BASE,
  headers: {
    'Content-Type': 'application/json',
  },
});

export const productsApi = {
  list: async (params: {
    page?: number;
    page_size?: number;
    sort_by?: string;
    sort_order?: 'ASC' | 'DESC';
  } & ProductFilters): Promise<ProductListResponse> => {
    const response = await apiClient.get('/products', { params });
    return response.data;
  },

  getById: async (productId: string): Promise<Product> => {
    const response = await apiClient.get(`/products/${productId}`);
    return response.data;
  },

  getFilterOptions: async (): Promise<FilterOptions> => {
    const response = await apiClient.get('/products/filters/options');
    return response.data;
  },

  getSimilar: async (productId: string, limit = 6): Promise<ProductListResponse> => {
    const response = await apiClient.get(`/products/${productId}/similar`, {
      params: { limit },
    });
    return response.data;
  },

  getCompleteTheLook: async (productId: string, limit = 4): Promise<ProductListResponse> => {
    const response = await apiClient.get(`/products/${productId}/complete-the-look`, {
      params: { limit },
    });
    return response.data;
  },
};

export const usersApi = {
  listPersonas: async (): Promise<UserPersona[]> => {
    const response = await apiClient.get('/users');
    return response.data;
  },

  getPersona: async (userId: string): Promise<UserPersona> => {
    const response = await apiClient.get(`/users/${userId}`);
    return response.data;
  },

  getProfile: async (userId: string): Promise<UserProfile> => {
    const response = await apiClient.get(`/users/${userId}/profile`);
    return response.data;
  },
};

export const searchApi = {
  searchByText: async (params: {
    query: string;
    user_id?: string;
    limit?: number;
  }): Promise<SearchResponse> => {
    const response = await apiClient.post('/search/text', params);
    return response.data;
  },

  searchByImage: async (params: {
    image: File;
    user_id?: string;
    limit?: number;
  }): Promise<SearchResponse> => {
    const formData = new FormData();
    formData.append('image', params.image);
    if (params.user_id) {
      formData.append('user_id', params.user_id);
    }
    if (params.limit) {
      formData.append('limit', params.limit.toString());
    }

    const response = await apiClient.post('/search/image', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  },

  getRecommendations: async (userId: string, limit = 20): Promise<SearchResponse> => {
    const response = await apiClient.get(`/search/recommendations/${userId}`, {
      params: { limit },
    });
    return response.data;
  },
};

export default apiClient;
