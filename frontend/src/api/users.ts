import apiClient from './client';

export interface UserProfile {
  id: string;
  username: string;
  reputation_score: number;
  created_at: string;
  authored_count: number;
  is_quarantined?: boolean | null;
  quarantine_reason?: string | null;
  quarantine_until?: string | null;
  is_blocked?: boolean | null;
  is_moderator?: boolean | null;
  quarantined_parts_count?: number | null;
  votes_cast_count?: number | null;
  votes_up_count?: number | null;
  votes_down_count?: number | null;
}

export type PartSortField = 'age' | 'vote_score' | 'recursive_score';

export interface UserPart {
  id: string;
  teaser: string;
  vote_score: number;
  recursive_score: number;
  depth_level: number;
  is_quarantined: boolean;
  parent_part_id: string | null;
  created_at: string;
  children_count: number;
}

export const usersApi = {
  getProfile: async (userId: string): Promise<UserProfile> => {
    const response = await apiClient.get<UserProfile>(`/users/${userId}`);
    return response.data;
  },

  getParts: async (
    userId: string,
    params: {
      sort?: PartSortField;
      order?: 'asc' | 'desc';
      skip?: number;
      limit?: number;
      include_quarantined?: boolean;
    } = {},
  ): Promise<UserPart[]> => {
    const response = await apiClient.get<UserPart[]>(`/users/${userId}/parts`, {
      params: {
        sort: params.sort ?? 'age',
        order: params.order ?? 'desc',
        skip: params.skip ?? 0,
        limit: params.limit ?? 20,
        include_quarantined: params.include_quarantined ?? false,
      },
    });
    return response.data;
  },
};
