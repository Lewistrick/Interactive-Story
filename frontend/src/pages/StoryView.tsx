import { useState, type FC, type FormEvent } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useParams, useNavigate } from 'react-router-dom';
import { storiesApi, type StoryPart } from '../api/stories';
import { moderatorApi, reportStoryPart } from '../api/moderation';
import { getApiErrorMessage } from '../api/errors';
import { useAuth } from '../contexts/useAuth';
import AuthorLink from '../components/AuthorLink';
import PageShell from '../components/PageShell';
import StoryPathSpine from '../components/StoryPathSpine';
import BranchCard from '../components/BranchCard';
import CreateStoryForm from '../components/CreateStoryForm';
import DailyLimitNotice from '../components/DailyLimitNotice';
import QuarantineBanner from '../components/QuarantineBanner';
import VotingButtons from '../components/VotingButtons';
import Button from '../components/ui/Button';
import Panel from '../components/ui/Panel';

interface StoryPathResult {
  path: StoryPart[];
  incomplete: boolean;
}

/** Fetch root → … → current (inclusive), root first. Stop if an ancestor is missing. */
async function fetchStoryPath(storyId: string): Promise<StoryPathResult> {
  const chain: StoryPart[] = [];
  let current = await storiesApi.getStoryPart(storyId);
  chain.push(current);
  let incomplete = false;
  while (current.parent_part_id) {
    try {
      current = await storiesApi.getStoryPart(current.parent_part_id);
      chain.push(current);
    } catch {
      incomplete = true;
      break;
    }
  }
  return { path: chain.reverse(), incomplete };
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
  const isModerator = Boolean(isAuthenticated && user?.is_moderator);
  const dailyPartLimit = user?.daily_part_limit ?? 2;
  const partsWrittenToday = user?.parts_written_today ?? 0;
  const atDailyLimit = isAuthenticated && partsWrittenToday >= dailyPartLimit;

  const { data: pathResult, isLoading: pathLoading, isError: pathError } = useQuery({
    queryKey: ['story-path', storyId],
    queryFn: () => fetchStoryPath(storyId!),
    enabled: !!storyId,
    retry: false,
  });

  const path = pathResult?.path;
  const pathIncomplete = pathResult?.incomplete ?? false;
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

  const reportMutation = useMutation({
    mutationFn: () => reportStoryPart(storyId!),
  });

  const invalidateStory = () => {
    queryClient.invalidateQueries({ queryKey: ['story-path', storyId] });
    queryClient.invalidateQueries({ queryKey: ['story-children', storyId] });
    queryClient.invalidateQueries({ queryKey: ['moderator-queue'] });
  };

  const quarantineMutation = useMutation({
    mutationFn: () => moderatorApi.quarantineStory(storyId!),
    onSuccess: invalidateStory,
  });

  const allowMutation = useMutation({
    mutationFn: () => moderatorApi.allow('STORY_PART', storyId!),
    onSuccess: invalidateStory,
  });

  const removeMutation = useMutation({
    mutationFn: () => moderatorApi.remove('STORY_PART', storyId!),
    onSuccess: invalidateStory,
  });

  const handleCreateContinuation = (e: FormEvent) => {
    e.preventDefault();
    if (newTeaser.trim() && newContent.trim()) {
      createMutation.mutate({ teaser: newTeaser, content: newContent });
    }
  };

  const handleVote = (voteType: 'UP' | 'DOWN') => {
    if (isAuthenticated && canVote && user?.id !== story?.author_id) {
      voteMutation.mutate(voteType);
    }
  };

  const modActionPending =
    quarantineMutation.isPending || allowMutation.isPending || removeMutation.isPending;
  const modActionError =
    quarantineMutation.error || allowMutation.error || removeMutation.error;

  if (pathLoading || childrenLoading) {
    return (
      <PageShell>
        <div className="flex justify-center items-center py-24 text-muted">
          Loading story...
        </div>
      </PageShell>
    );
  }

  if (pathError || !story) {
    return (
      <PageShell>
        <div className="flex justify-center items-center py-24 text-muted">
          Story not found
        </div>
      </PageShell>
    );
  }

  const previousVisible =
    ancestors.length > 0 ? ancestors[ancestors.length - 1] : null;
  const isOwnPart = Boolean(user?.id && user.id === story.author_id);
  const mayVote = canVote && !isOwnPart;

  return (
    <PageShell>
      <main className="mx-auto max-w-3xl px-4 py-6">
        <button
          type="button"
          onClick={() => {
            if (previousVisible) {
              navigate(`/story/${previousVisible.id}`);
            } else {
              navigate('/');
            }
          }}
          className="mb-4 text-sm text-accent hover:text-accent-hover"
        >
          {previousVisible ? '← Previous part' : '← Back to stories'}
        </button>

        <StoryPathSpine
          ancestors={ancestors}
          pathIncomplete={pathIncomplete}
          onSelect={(id) => navigate(`/story/${id}`)}
        />

        <Panel className="mb-6 p-8">
          {isModerator && story.is_quarantined ? (
            <QuarantineBanner reason={story.quarantine_reason} />
          ) : null}
          <h1 className="mb-2 text-2xl font-semibold text-text">{story.teaser}</h1>
          <p className="mb-6 text-sm text-muted">
            <AuthorLink userId={story.author_id} username={story.author_username} /> · depth{' '}
            {story.depth_level}
          </p>
          <p className="font-serif text-lg leading-relaxed whitespace-pre-wrap text-text">
            {story.content}
          </p>
          <div className="mt-6 border-t border-border pt-6 space-y-3">
            {isAuthenticated ? (
              <VotingButtons
                voteScore={story.vote_score}
                userVote={story.user_vote}
                disabled={voteMutation.isPending}
                canVote={mayVote}
                disabledReason={
                  isOwnPart ? 'You cannot vote on your own story parts.' : undefined
                }
                onVote={handleVote}
              />
            ) : (
              <span className="text-sm text-muted">Login to vote</span>
            )}
            {isAuthenticated && !user?.is_quarantined ? (
              <div>
                <Button
                  variant="ghost"
                  onClick={() => reportMutation.mutate()}
                  disabled={reportMutation.isPending || reportMutation.isSuccess}
                >
                  {reportMutation.isSuccess ? 'Reported' : 'Report this part'}
                </Button>
                {reportMutation.isError ? (
                  <p className="mt-1 text-sm text-downvote">
                    {getApiErrorMessage(
                      reportMutation.error,
                      'Could not submit report (you may have already reported this).',
                    )}
                  </p>
                ) : null}
                {reportMutation.isSuccess && reportMutation.data?.quarantined ? (
                  <p className="mt-1 text-sm text-muted">
                    Enough reports received — this part is now under review.
                  </p>
                ) : null}
              </div>
            ) : null}
            {isModerator ? (
              <div className="space-y-2 border-t border-border pt-3">
                <p className="text-xs font-semibold uppercase tracking-wide text-muted">
                  Moderate this part
                </p>
                <div className="flex flex-wrap gap-2">
                  {!story.is_quarantined ? (
                    <Button
                      variant="ghost"
                      onClick={() => quarantineMutation.mutate()}
                      disabled={modActionPending}
                    >
                      Quarantine
                    </Button>
                  ) : (
                    <Button
                      variant="primary"
                      onClick={() => allowMutation.mutate()}
                      disabled={modActionPending}
                    >
                      Allow
                    </Button>
                  )}
                  <Button
                    variant="ghost"
                    className="text-downvote"
                    onClick={() => {
                      if (
                        window.confirm(
                          'Permanently hide this story part from the public? Continuations are not deleted.',
                        )
                      ) {
                        removeMutation.mutate();
                      }
                    }}
                    disabled={modActionPending}
                  >
                    Remove
                  </Button>
                </div>
                {modActionError ? (
                  <p className="text-sm text-downvote">
                    {getApiErrorMessage(modActionError, 'Moderation action failed.')}
                  </p>
                ) : null}
              </div>
            ) : null}
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
              <p className="mt-2 text-sm text-downvote">
                {getApiErrorMessage(createMutation.error, 'Failed to publish continuation.')}
              </p>
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
