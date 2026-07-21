import apiClient from './client';

export interface LoginCredentials {
  username: string;
  password: string;
}

export interface RegisterCredentials {
  username: string;
  password: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
}

export interface User {
  id: string;
  username: string;
  reputation_score: number;
  is_quarantined: boolean;
  quarantine_reason?: string | null;
  quarantine_until?: string | null;
  is_moderator: boolean;
  is_blocked: boolean;
  created_at: string;
  updated_at: string;
  tier_name?: string | null;
  max_teaser_length?: number | null;
  max_content_length?: number | null;
  daily_part_limit?: number | null;
  min_parts_between_own?: number | null;
  can_vote?: boolean | null;
  parts_written_today?: number | null;
  can_create_root?: boolean | null;
  min_reputation_create_root?: number | null;
  open_root_trees?: number | null;
  max_concurrent_open_trees?: number | null;
}

export const authApi = {
  login: async (credentials: LoginCredentials): Promise<AuthResponse> => {
    const response = await apiClient.post<AuthResponse>('/auth/login', credentials);
    localStorage.setItem('token', response.data.access_token);
    return response.data;
  },

  register: async (credentials: RegisterCredentials): Promise<User> => {
    const response = await apiClient.post<User>('/auth/register', credentials);
    return response.data;
  },

  getCurrentUser: async (): Promise<User> => {
    const response = await apiClient.get<User>('/auth/me');
    return response.data;
  },

  logout: () => {
    localStorage.removeItem('token');
  },
};
