import apiClient from './client';

export interface QuarantineLog {
  id: string;
  entity_type: 'USER' | 'STORY_PART';
  entity_id: string;
  reason: string;
  triggered_by: string;
  automatic: boolean;
  resolved_by_moderator_id: string | null;
  resolution_action: 'ALLOWED' | 'REMOVED' | 'BLOCKED' | 'WARNED' | null;
  resolved_at: string | null;
  created_at: string;
  author_username?: string | null;
  author_id?: string | null;
  teaser?: string | null;
  content_preview?: string | null;
}

export interface ReportResponse {
  id: string;
  story_part_id: string;
  reporter_id: string;
  reason: string | null;
  created_at: string;
  quarantined: boolean;
  report_count: number;
}

export interface VotingPatternFlag {
  user_id: string;
  username: string;
  flag: string;
  detail: string;
  reputation_score: number;
}

export interface ReputationPoint {
  score: number;
  created_at: string;
}

export interface ModeratorUserProfile {
  id: string;
  username: string;
  reputation_score: number;
  is_quarantined: boolean;
  quarantine_reason: string | null;
  quarantine_until: string | null;
  is_blocked: boolean;
  is_moderator: boolean;
  created_at: string;
  authored_count: number;
  quarantined_parts_count: number;
  votes_cast_count: number;
  votes_up_count: number;
  votes_down_count: number;
}

export type PartSortField = 'age' | 'vote_score' | 'recursive_score';

export interface ModeratorUserPart {
  id: string;
  teaser: string;
  vote_score: number;
  recursive_score: number;
  depth_level: number;
  is_quarantined: boolean;
  parent_part_id: string | null;
  created_at: string;
}

export interface ModeratorUserVote {
  vote_id: string;
  vote_type: 'UP' | 'DOWN';
  voted_at: string;
  story_part_id: string;
  teaser: string;
  vote_score: number;
  recursive_score: number;
  is_quarantined: boolean;
  author_username: string | null;
}

export interface BulkModerationResult {
  processed: number;
  failed: number;
  errors: string[];
}

export const moderatorApi = {
  getQueue: async (skip = 0, limit = 50): Promise<QuarantineLog[]> => {
    const response = await apiClient.get<QuarantineLog[]>('/moderator/quarantine-queue', {
      params: { skip, limit },
    });
    return response.data;
  },

  getAuditLog: async (skip = 0, limit = 50): Promise<QuarantineLog[]> => {
    const response = await apiClient.get<QuarantineLog[]>('/moderator/audit-log', {
      params: { skip, limit },
    });
    return response.data;
  },

  getVotingPatterns: async (limit = 20): Promise<VotingPatternFlag[]> => {
    const response = await apiClient.get<VotingPatternFlag[]>('/moderator/voting-patterns', {
      params: { limit },
    });
    return response.data;
  },

  getReputationHistory: async (userId: string, limit = 50): Promise<ReputationPoint[]> => {
    const response = await apiClient.get<ReputationPoint[]>(
      `/moderator/users/${userId}/reputation-history`,
      { params: { limit } },
    );
    return response.data;
  },

  getUserProfile: async (userId: string): Promise<ModeratorUserProfile> => {
    const response = await apiClient.get<ModeratorUserProfile>(`/moderator/users/${userId}`);
    return response.data;
  },

  getUserParts: async (
    userId: string,
    params: {
      sort?: PartSortField;
      order?: 'asc' | 'desc';
      skip?: number;
      limit?: number;
      quarantined_only?: boolean;
    } = {},
  ): Promise<ModeratorUserPart[]> => {
    const response = await apiClient.get<ModeratorUserPart[]>(
      `/moderator/users/${userId}/parts`,
      {
        params: {
          sort: params.sort ?? 'age',
          order: params.order ?? 'desc',
          skip: params.skip ?? 0,
          limit: params.limit ?? 20,
          quarantined_only: params.quarantined_only ?? false,
        },
      },
    );
    return response.data;
  },

  getUserVotes: async (
    userId: string,
    params: { skip?: number; limit?: number; vote_type?: 'UP' | 'DOWN' } = {},
  ): Promise<ModeratorUserVote[]> => {
    const response = await apiClient.get<ModeratorUserVote[]>(
      `/moderator/users/${userId}/votes`,
      {
        params: {
          skip: params.skip ?? 0,
          limit: params.limit ?? 20,
          vote_type: params.vote_type,
        },
      },
    );
    return response.data;
  },

  bulk: async (
    action: 'allow' | 'remove' | 'block',
    items: { entity_type: string; entity_id: string }[],
  ): Promise<BulkModerationResult> => {
    const response = await apiClient.post<BulkModerationResult>('/moderator/bulk', {
      action,
      items,
    });
    return response.data;
  },

  allow: async (entityType: string, entityId: string): Promise<QuarantineLog> => {
    const response = await apiClient.post<QuarantineLog>(
      `/moderator/${entityType}/${entityId}/allow`,
    );
    return response.data;
  },

  remove: async (entityType: string, entityId: string): Promise<QuarantineLog> => {
    const response = await apiClient.post<QuarantineLog>(
      `/moderator/${entityType}/${entityId}/remove`,
    );
    return response.data;
  },

  blockUser: async (userId: string, reason?: string): Promise<QuarantineLog> => {
    const response = await apiClient.post<QuarantineLog>(`/moderator/users/${userId}/block`, {
      reason: reason ?? 'Blocked by moderator',
    });
    return response.data;
  },

  warnUser: async (
    userId: string,
    reason: string,
    durationHours?: number,
  ): Promise<QuarantineLog> => {
    const response = await apiClient.post<QuarantineLog>(`/moderator/users/${userId}/warn`, {
      reason,
      duration_hours: durationHours ?? null,
    });
    return response.data;
  },
};

export const reportStoryPart = async (
  storyId: string,
  reason?: string,
): Promise<ReportResponse> => {
  const response = await apiClient.post<ReportResponse>(`/stories/${storyId}/report`, {
    reason: reason ?? null,
  });
  return response.data;
};
