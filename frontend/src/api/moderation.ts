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
