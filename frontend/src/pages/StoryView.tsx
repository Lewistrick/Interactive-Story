import { useState, type FC, type FormEvent } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useParams, useNavigate } from 'react-router-dom';
import { storiesApi, type StoryPart } from '../api/stories';
import { useAuth } from '../contexts/useAuth';
import PageShell from '../components/PageShell';
import StoryPathSpine from '../components/StoryPathSpine';
import BranchCard from '../components/BranchCard';
import CreateStoryForm from '../components/CreateStoryForm';
import DailyLimitNotice from '../components/DailyLimitNotice';
import VotingButtons from '../components/VotingButtons';
import Button from '../components/ui/Button';
import Panel from '../components/ui/Panel';

/** Fetch root → … → current (inclusive), root first. */
async function fetchStoryPath(storyId: string): Promise<StoryPart[]> {
  const chain: StoryPart[] = [];
  let current = await storiesApi.getStoryPart(storyId);
  chain.push(current);
  while (current.parent_part_id) {
    current = await storiesApi.getStoryPart(current.parent_part_id);
    chain.push(current);
  }
  return chain.reverse();
}

const StoryView: FC = () => {
  const { storyId } = useParams<{ storyId: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { isAuthenticated, user, refreshUser } = useAuth();
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [newTeaser, setNewTeaser] = useState('');
  const [newContent, setNewContent] = useState('');

  const maxTeaserLength = user?.max_teaser_length ?? 512;
  const maxContentLength = user?.max_content_length ?? 2048;
  const canVote = user?.can_vote ?? false;
  const dailyPartLimit = user?.daily_part_limit ?? 2;
  const partsWrittenToday = user?.parts_written_today ?? 0;
  const atDailyLimit = isAuthenticated && partsWrittenToday >= dailyPartLimit;

  const { data: path, isLoading: pathLoading } = useQuery({
    queryKey: ['story-path', storyId],
    queryFn: () => fetchStoryPath(storyId!),
    enabled: !!storyId,
  });

  const story = path && path.length > 0 ? path[path.length - 1] : undefined;
  const ancestors = path && path.length > 1 ? path.slice(0, -1) : [];

  const { data: children, isLoading: childrenLoading } = useQuery({
    queryKey: ['story-children', storyId],
    queryFn: () => storiesApi.getStoryChildren(storyId!),
    enabled: !!storyId,
  });

  const createMutation = useMutation({
    mutationFn: (data: { teaser: string; content: string }) =>
      storiesApi.continueStory(storyId!, data),
    onSuccess: async (created) => {
      queryClient.invalidateQueries({ queryKey: ['story-children', storyId] });
      queryClient.invalidateQueries({ queryKey: ['story-path'] });
      setShowCreateForm(false);
      setNewTeaser('');
      setNewContent('');
      await refreshUser();
      navigate(`/story/${created.id}`);
    },
  });

  const voteMutation = useMutation({
    mutationFn: (voteType: 'UP' | 'DOWN') =>
      storiesApi.voteOnStory(storyId!, { vote_type: voteType }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['story-path', storyId] });
      queryClient.invalidateQueries({ queryKey: ['story-children', storyId] });
    },
  });

  const handleCreateContinuation = (e: FormEvent) => {
    e.preventDefault();
    if (newTeaser.trim() && newContent.trim()) {
      createMutation.mutate({ teaser: newTeaser, content: newContent });
    }
  };

  const handleVote = (voteType: 'UP' | 'DOWN') => {
    if (isAuthenticated && canVote) {
      voteMutation.mutate(voteType);
    }
  };

  if (pathLoading || childrenLoading) {
    return (
      <PageShell>
        <div className="flex justify-center items-center py-24 text-muted">
          Loading story...
        </div>
      </PageShell>
    );
  }

  if (!story) {
    return (
      <PageShell>
        <div className="flex justify-center items-center py-24 text-muted">
          Story not found
        </div>
      </PageShell>
    );
  }

  return (
    <PageShell>
      <main className="mx-auto max-w-3xl px-4 py-6">
        <button
          type="button"
          onClick={() => {
            if (story.parent_part_id) {
              navigate(`/story/${story.parent_part_id}`);
            } else {
              navigate('/');
            }
          }}
          className="mb-4 text-sm text-accent hover:text-accent-hover"
        >
          {story.parent_part_id ? '← Previous part' : '← Back to stories'}
        </button>

        <StoryPathSpine
          ancestors={ancestors}
          onSelect={(id) => navigate(`/story/${id}`)}
        />

        <Panel className="mb-6 p-8">
          <h1 className="mb-2 text-2xl font-semibold text-text">{story.teaser}</h1>
          <p className="mb-6 text-sm text-muted">
            {story.author_username || 'Unknown'} · depth {story.depth_level}
          </p>
          <p className="font-serif text-lg leading-relaxed whitespace-pre-wrap text-text">
            {story.content}
          </p>
          <div className="mt-6 border-t border-border pt-6">
            {isAuthenticated ? (
              <VotingButtons
                voteScore={story.vote_score}
                userVote={story.user_vote}
                disabled={voteMutation.isPending}
                canVote={canVote}
                onVote={handleVote}
              />
            ) : (
              <span className="text-sm text-muted">Login to vote</span>
            )}
          </div>
        </Panel>

        {isAuthenticated && (
          <div className="mb-6">
            {atDailyLimit ? (
              <DailyLimitNotice dailyPartLimit={dailyPartLimit} />
            ) : showCreateForm ? (
              <CreateStoryForm
                teaser={newTeaser}
                content={newContent}
                onTeaserChange={setNewTeaser}
                onContentChange={setNewContent}
                onSubmit={handleCreateContinuation}
                onCancel={() => setShowCreateForm(false)}
                isPending={createMutation.isPending}
                submitLabel="Publish continuation"
                maxTeaserLength={maxTeaserLength}
                maxContentLength={maxContentLength}
                contentLabel="Your story part"
                contentPlaceholder="Continue the story..."
              />
            ) : (
              <Button
                variant="primary"
                className="w-full"
                onClick={() => setShowCreateForm(true)}
              >
                Write a continuation
              </Button>
            )}
            {createMutation.isError && (
              <p className="mt-2 text-sm text-downvote">Failed to publish continuation.</p>
            )}
          </div>
        )}

        <section>
          <h2 className="mb-4 text-sm font-semibold tracking-wide text-muted uppercase">
            Choose your path ({children?.length || 0})
          </h2>
          {children && children.length > 0 ? (
            <div className="grid gap-4 sm:grid-cols-2">
              {children.map((child) => (
                <BranchCard
                  key={child.id}
                  story={child}
                  onClick={() => navigate(`/story/${child.id}`)}
                />
              ))}
            </div>
          ) : (
            <Panel className="p-8 text-center text-muted">
              No continuations yet. Be the first!
            </Panel>
          )}
        </section>
      </main>
    </PageShell>
  );
};

export default StoryView;
