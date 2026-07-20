import { useState, type FC, type FormEvent } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useParams, useNavigate } from 'react-router-dom';
import { storiesApi } from '../api/stories';
import { useAuth } from '../contexts/AuthContext';
import Header from '../components/Header';
import VotingButtons from '../components/VotingButtons';
import StoryTree from '../components/StoryTree';

/**
 * Walk parent links until the root story part is found.
 */
async function findRootStoryId(storyId: string): Promise<string> {
  let current = await storiesApi.getStoryPart(storyId);
  while (current.parent_part_id) {
    current = await storiesApi.getStoryPart(current.parent_part_id);
  }
  return current.id;
}

const StoryView: FC = () => {
  const { storyId } = useParams<{ storyId: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { isAuthenticated } = useAuth();
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [newTeaser, setNewTeaser] = useState('');
  const [newContent, setNewContent] = useState('');

  const { data: story, isLoading: storyLoading } = useQuery({
    queryKey: ['story', storyId],
    queryFn: () => storiesApi.getStoryPart(storyId!),
    enabled: !!storyId,
  });

  const { data: children, isLoading: childrenLoading } = useQuery({
    queryKey: ['story-children', storyId],
    queryFn: () => storiesApi.getStoryChildren(storyId!),
    enabled: !!storyId,
  });

  const { data: rootId } = useQuery({
    queryKey: ['story-root', storyId],
    queryFn: () => findRootStoryId(storyId!),
    enabled: !!storyId,
  });

  const { data: tree } = useQuery({
    queryKey: ['story-tree', rootId],
    queryFn: () => storiesApi.getStoryTree(rootId!),
    enabled: !!rootId,
  });

  const createMutation = useMutation({
    mutationFn: (data: { teaser: string; content: string }) =>
      storiesApi.continueStory(storyId!, data),
    onSuccess: (created) => {
      queryClient.invalidateQueries({ queryKey: ['story-children', storyId] });
      queryClient.invalidateQueries({ queryKey: ['story-tree'] });
      queryClient.invalidateQueries({ queryKey: ['story', storyId] });
      setShowCreateForm(false);
      setNewTeaser('');
      setNewContent('');
      navigate(`/story/${created.id}`);
    },
  });

  const voteMutation = useMutation({
    mutationFn: (voteType: 'UP' | 'DOWN') =>
      storiesApi.voteOnStory(storyId!, { vote_type: voteType }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['story', storyId] });
      queryClient.invalidateQueries({ queryKey: ['story-tree'] });
    },
  });

  const handleCreateContinuation = (e: FormEvent) => {
    e.preventDefault();
    if (newTeaser.trim() && newContent.trim()) {
      createMutation.mutate({ teaser: newTeaser, content: newContent });
    }
  };

  const handleVote = (voteType: 'UP' | 'DOWN') => {
    if (isAuthenticated) {
      voteMutation.mutate(voteType);
    }
  };

  if (storyLoading || childrenLoading) {
    return (
      <div className="flex justify-center items-center h-screen">
        <div className="text-xl text-gray-600">Loading story...</div>
      </div>
    );
  }

  if (!story) {
    return (
      <div className="flex justify-center items-center h-screen">
        <div className="text-xl text-gray-600">Story not found</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <Header />

      <main className="max-w-4xl mx-auto px-4 py-8">
        <button
          type="button"
          onClick={() => {
            if (story.parent_part_id) {
              navigate(`/story/${story.parent_part_id}`);
            } else {
              navigate('/');
            }
          }}
          className="text-blue-600 hover:text-blue-800 mb-4 inline-block"
        >
          {story.parent_part_id ? '← Previous part' : '← Back to stories'}
        </button>

        <div className="bg-white rounded-lg shadow-md p-8 mb-8">
          <h1 className="text-3xl font-bold text-gray-900 mb-2">{story.teaser}</h1>
          <p className="text-gray-600 mb-6">
            By {story.author_username || 'Unknown'} · Depth: {story.depth_level}
          </p>
          <p className="text-lg text-gray-800 leading-relaxed whitespace-pre-wrap">
            {story.content}
          </p>

          <div className="flex items-center gap-4 mt-6 pt-6 border-t">
            {isAuthenticated ? (
              <VotingButtons
                voteScore={story.vote_score}
                userVote={story.user_vote}
                disabled={voteMutation.isPending}
                onVote={handleVote}
              />
            ) : (
              <span className="text-gray-500">Login to vote</span>
            )}
          </div>
        </div>

        {isAuthenticated && (
          <div className="bg-white rounded-lg shadow-md p-6 mb-8">
            <button
              type="button"
              onClick={() => setShowCreateForm(!showCreateForm)}
              className="w-full px-4 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors font-semibold"
            >
              {showCreateForm ? 'Cancel' : 'Write a Continuation'}
            </button>

            {showCreateForm && (
              <form onSubmit={handleCreateContinuation} className="mt-4 space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Teaser (max 512 characters)
                  </label>
                  <input
                    type="text"
                    value={newTeaser}
                    onChange={(e) => setNewTeaser(e.target.value)}
                    maxLength={512}
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    placeholder="Write a catchy teaser for your continuation..."
                    required
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Your Story Part (max 2048 characters)
                  </label>
                  <textarea
                    value={newContent}
                    onChange={(e) => setNewContent(e.target.value)}
                    maxLength={2048}
                    rows={6}
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    placeholder="Continue the story..."
                    required
                  />
                </div>
                <button
                  type="submit"
                  disabled={createMutation.isPending}
                  className="w-full px-4 py-3 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors font-semibold disabled:opacity-50"
                >
                  {createMutation.isPending ? 'Publishing...' : 'Publish Continuation'}
                </button>
                {createMutation.isError && (
                  <p className="text-red-600 text-sm">Failed to publish continuation.</p>
                )}
              </form>
            )}
          </div>
        )}

        <div className="bg-white rounded-lg shadow-md p-6 mb-8">
          <h2 className="text-2xl font-bold text-gray-900 mb-4">
            Continuations ({children?.length || 0})
          </h2>

          {children && children.length > 0 ? (
            <div className="space-y-4">
              {children.map((child) => (
                <button
                  key={child.id}
                  type="button"
                  onClick={() => navigate(`/story/${child.id}`)}
                  className="w-full text-left p-4 border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors"
                >
                  <h3 className="text-lg font-semibold text-gray-800 mb-2">{child.teaser}</h3>
                  <p className="text-gray-600 text-sm line-clamp-2">{child.content}</p>
                  <div className="flex items-center gap-4 mt-3 text-sm text-gray-500">
                    <span>By {child.author_username || 'Unknown'}</span>
                    <span>{child.vote_score} votes</span>
                  </div>
                </button>
              ))}
            </div>
          ) : (
            <p className="text-gray-600 text-center py-8">No continuations yet. Be the first!</p>
          )}
        </div>

        {tree && <StoryTree tree={tree} currentStoryId={storyId} />}
      </main>
    </div>
  );
};

export default StoryView;
