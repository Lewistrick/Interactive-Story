import apiClient from './client';

export interface StoryPart {
  id: string;
  teaser: string;
  content: string;
  parent_part_id: string | null;
  author_id: string;
  vote_score: number;
  recursive_score: number;
  is_quarantined: boolean;
  quarantine_reason?: string | null;
  depth_level: number;
  created_at: string;
  updated_at: string;
  author_username: string | null;
  children_count: number;
  user_vote?: 'UP' | 'DOWN' | null;
}

export interface StoryPartTree extends StoryPart {
  children: StoryPartTree[];
}

export interface StoryList {
  id: string;
  teaser: string;
  author_id: string;
  vote_score: number;
  recursive_score: number;
  created_at: string;
  author_username: string | null;
  children_count: number;
}

export interface StoryPartCreate {
  teaser: string;
  content: string;
  parent_part_id?: string;
}

export interface VoteCreate {
  vote_type: 'UP' | 'DOWN';
}

export interface VoteActionResponse {
  id?: string;
  user_id?: string;
  story_part_id: string;
  vote_type?: 'UP' | 'DOWN' | null;
  created_at?: string;
  removed: boolean;
  vote_score: number;
}

export type RootSort = 'latest' | 'popular' | 'popular_now';

export const storiesApi = {
  listRootStories: async (
    skip: number = 0,
    limit: number = 50,
    sort: RootSort = 'latest',
  ): Promise<StoryList[]> => {
    // Trailing slash matches FastAPI route and avoids 307 redirects behind nginx.
    const response = await apiClient.get<StoryList[]>('/stories/', {
      params: { skip, limit, sort },
    });
    return response.data;
  },

  searchStories: async (
    q: string,
    skip: number = 0,
    limit: number = 50,
  ): Promise<StoryList[]> => {
    const response = await apiClient.get<StoryList[]>('/stories/search', {
      params: { q, skip, limit },
    });
    return response.data;
  },

  getStoryPart: async (storyId: string): Promise<StoryPart> => {
    const response = await apiClient.get<StoryPart>(`/stories/${storyId}`);
    return response.data;
  },

  getStoryChildren: async (storyId: string): Promise<StoryPart[]> => {
    const response = await apiClient.get<StoryPart[]>(`/stories/${storyId}/children`);
    return response.data;
  },

  getStoryTree: async (storyId: string): Promise<StoryPartTree> => {
    const response = await apiClient.get<StoryPartTree>(`/stories/${storyId}/tree`);
    return response.data;
  },

  createRootStory: async (story: StoryPartCreate): Promise<StoryPart> => {
    const response = await apiClient.post<StoryPart>('/stories/', story);
    return response.data;
  },

  continueStory: async (storyId: string, story: StoryPartCreate): Promise<StoryPart> => {
    const response = await apiClient.post<StoryPart>(`/stories/${storyId}/continue`, story);
    return response.data;
  },

  voteOnStory: async (storyId: string, vote: VoteCreate): Promise<VoteActionResponse> => {
    const response = await apiClient.post<VoteActionResponse>(`/stories/${storyId}/vote`, vote);
    return response.data;
  },

  removeVote: async (storyId: string): Promise<VoteActionResponse> => {
    const response = await apiClient.delete<VoteActionResponse>(`/stories/${storyId}/vote`);
    return response.data;
  },

  deleteStoryPart: async (storyId: string): Promise<void> => {
    await apiClient.delete(`/stories/${storyId}`);
  },
};
