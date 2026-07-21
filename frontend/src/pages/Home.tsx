import { useState, type FC, type FormEvent } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { storiesApi } from '../api/stories';
import { useAuth } from '../contexts/AuthContext';
import PageShell from '../components/PageShell';
import StoryListRow from '../components/StoryListRow';
import CreateStoryForm from '../components/CreateStoryForm';
import Button from '../components/ui/Button';
import Panel from '../components/ui/Panel';

const Home: FC = () => {
  const navigate = useNavigate();
  const { isAuthenticated, user } = useAuth();
  const queryClient = useQueryClient();
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [newTeaser, setNewTeaser] = useState('');
  const [newContent, setNewContent] = useState('');

  const maxTeaserLength = user?.max_teaser_length ?? 512;
  const maxContentLength = user?.max_content_length ?? 2048;

  const { data: stories, isLoading, error } = useQuery({
    queryKey: ['stories'],
    queryFn: () => storiesApi.listRootStories(0, 50),
  });

  const createMutation = useMutation({
    mutationFn: (data: { teaser: string; content: string }) =>
      storiesApi.createRootStory(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['stories'] });
      setShowCreateForm(false);
      setNewTeaser('');
      setNewContent('');
    },
  });

  const handleCreateStory = (e: FormEvent) => {
    e.preventDefault();
    if (newTeaser.trim() && newContent.trim()) {
      createMutation.mutate({ teaser: newTeaser, content: newContent });
    }
  };

  const headerAction =
    isAuthenticated && !showCreateForm ? (
      <Button variant="primary" onClick={() => setShowCreateForm(true)}>
        New story
      </Button>
    ) : null;

  if (isLoading) {
    return (
      <PageShell>
        <div className="flex justify-center items-center py-24 text-muted">
          Loading stories...
        </div>
      </PageShell>
    );
  }

  if (error) {
    return (
      <PageShell>
        <div className="flex justify-center items-center py-24 text-downvote">
          Error loading stories
        </div>
      </PageShell>
    );
  }

  return (
    <PageShell headerAction={headerAction}>
      <main className="max-w-3xl mx-auto px-4 py-8">
        {showCreateForm && isAuthenticated && (
          <div className="mb-8">
            <CreateStoryForm
              teaser={newTeaser}
              content={newContent}
              onTeaserChange={setNewTeaser}
              onContentChange={setNewContent}
              onSubmit={handleCreateStory}
              onCancel={() => setShowCreateForm(false)}
              isPending={createMutation.isPending}
              submitLabel="Publish story"
              maxTeaserLength={maxTeaserLength}
              maxContentLength={maxContentLength}
              contentLabel={`Story beginning (max ${maxContentLength} characters)`}
            />
          </div>
        )}

        <div className="flex items-center justify-between mb-4">
          <h1 className="text-lg font-semibold text-text">Discover</h1>
          <span className="text-sm text-muted">Sort: Newest</span>
        </div>

        {stories && stories.length > 0 ? (
          <Panel className="overflow-hidden">
            {stories.map((story) => (
              <StoryListRow
                key={story.id}
                story={story}
                onClick={() => navigate(`/story/${story.id}`)}
              />
            ))}
          </Panel>
        ) : (
          <Panel className="p-12 text-center text-muted">
            No stories yet. Be the first to create one!
          </Panel>
        )}
      </main>
    </PageShell>
  );
};

export default Home;
