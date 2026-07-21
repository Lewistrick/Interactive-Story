import { useState, type FC, type FormEvent } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useParams, useNavigate } from 'react-router-dom';
import { storiesApi } from '../api/stories';
import { useAuth } from '../contexts/AuthContext';
import PageShell from '../components/PageShell';
import StoryMapPanel from '../components/StoryMapPanel';
import BranchCard from '../components/BranchCard';
import CreateStoryForm from '../components/CreateStoryForm';
import VotingButtons from '../components/VotingButtons';
import Button from '../components/ui/Button';
import Panel from '../components/ui/Panel';

/** Walk parent links until the root story part is found. */
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
  const { isAuthenticated, user } = useAuth();
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [showMapDrawer, setShowMapDrawer] = useState(false);
  const [newTeaser, setNewTeaser] = useState('');
  const [newContent, setNewContent] = useState('');

  const maxTeaserLength = user?.max_teaser_length ?? 512;
  const maxContentLength = user?.max_content_length ?? 2048;
  const canVote = user?.can_vote ?? false;

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
    if (isAuthenticated && canVote) {
      voteMutation.mutate(voteType);
    }
  };

  if (storyLoading || childrenLoading) {
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

  const mapPanel =
    tree && (
      <StoryMapPanel tree={tree} currentStoryId={storyId} className="sticky top-4" />
    );

  return (
    <PageShell
      headerAction={
        <Button
          variant="secondary"
          className="lg:hidden"
          onClick={() => setShowMapDrawer(true)}
        >
          Map
        </Button>
      }
    >
      {/* Mobile story map drawer */}
      {showMapDrawer && tree && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <button
            type="button"
            className="absolute inset-0 bg-text/30"
            aria-label="Close story map"
            onClick={() => setShowMapDrawer(false)}
          />
          <div className="absolute left-0 top-0 bottom-0 w-72 p-4 bg-page overflow-y-auto">
            <StoryMapPanel tree={tree} currentStoryId={storyId} />
          </div>
        </div>
      )}

      <div className="max-w-6xl mx-auto px-4 py-6 flex gap-6">
        {/* Desktop sidebar */}
        <aside className="hidden lg:block w-56 shrink-0">{mapPanel}</aside>

        <main className="flex-1 min-w-0">
          <button
            type="button"
            onClick={() => {
              if (story.parent_part_id) {
                navigate(`/story/${story.parent_part_id}`);
              } else {
                navigate('/');
              }
            }}
            className="text-sm text-accent hover:text-accent-hover mb-4"
          >
            {story.parent_part_id ? '← Previous part' : '← Back to stories'}
          </button>

          <Panel className="p-8 mb-6">
            <h1 className="text-2xl font-semibold text-text mb-2">{story.teaser}</h1>
            <p className="text-sm text-muted mb-6">
              {story.author_username || 'Unknown'} · depth {story.depth_level}
            </p>
            <p className="font-serif text-lg leading-relaxed text-text whitespace-pre-wrap">
              {story.content}
            </p>
            <div className="mt-6 pt-6 border-t border-border">
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
              {showCreateForm ? (
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
                  contentLabel={`Your story part (max ${maxContentLength} characters)`}
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
                <p className="text-downvote text-sm mt-2">
                  Failed to publish continuation.
                </p>
              )}
            </div>
          )}

          <section>
            <h2 className="text-sm font-semibold uppercase tracking-wide text-muted mb-4">
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
      </div>
    </PageShell>
  );
};

export default StoryView;
