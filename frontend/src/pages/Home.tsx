import { useDeferredValue, useState, type FC, type FormEvent } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { storiesApi, type RootSort } from '../api/stories';
import { getApiErrorMessage } from '../api/errors';
import { useAuth } from '../contexts/useAuth';
import PageShell from '../components/PageShell';
import StoryListRow from '../components/StoryListRow';
import CreateStoryForm from '../components/CreateStoryForm';
import DailyLimitNotice from '../components/DailyLimitNotice';
import RootCreateGateNotice from '../components/RootCreateGateNotice';
import Button from '../components/ui/Button';
import Input from '../components/ui/Input';
import Panel from '../components/ui/Panel';

const Home: FC = () => {
  const navigate = useNavigate();
  const { isAuthenticated, user, refreshUser } = useAuth();
  const queryClient = useQueryClient();
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [newTeaser, setNewTeaser] = useState('');
  const [newContent, setNewContent] = useState('');
  const [sort, setSort] = useState<RootSort>('latest');
  const [searchInput, setSearchInput] = useState('');
  const deferredSearch = useDeferredValue(searchInput.trim());
  const isSearching = deferredSearch.length > 0;

  const maxTeaserLength = user?.max_teaser_length ?? 512;
  const maxContentLength = user?.max_content_length ?? 2048;
  const dailyPartLimit = user?.daily_part_limit ?? 2;
  const partsWrittenToday = user?.parts_written_today ?? 0;
  const atDailyLimit = isAuthenticated && partsWrittenToday >= dailyPartLimit;
  const canCreateRoot = user?.can_create_root ?? false;
  const minRepRoot = user?.min_reputation_create_root ?? 50;
  const openRoots = user?.open_root_trees ?? 0;
  const maxOpenRoots = user?.max_concurrent_open_trees ?? 3;
  const belowMinRep = (user?.reputation_score ?? 0) < minRepRoot;
  const blockedFromRoot = isAuthenticated && !atDailyLimit && !canCreateRoot;

  const listQuery = useQuery({
    queryKey: ['stories', sort],
    queryFn: () => storiesApi.listRootStories(0, 50, sort),
    enabled: !isSearching,
  });

  const searchQuery = useQuery({
    queryKey: ['stories', 'search', deferredSearch],
    queryFn: () => storiesApi.searchStories(deferredSearch, 0, 50),
    enabled: isSearching,
  });

  const stories = isSearching ? searchQuery.data : listQuery.data;
  const isLoading = isSearching ? searchQuery.isLoading : listQuery.isLoading;
  const error = isSearching ? searchQuery.error : listQuery.error;

  const createMutation = useMutation({
    mutationFn: (data: { teaser: string; content: string }) => storiesApi.createRootStory(data),
    onSuccess: async () => {
      queryClient.invalidateQueries({ queryKey: ['stories'] });
      setShowCreateForm(false);
      setNewTeaser('');
      setNewContent('');
      await refreshUser();
    },
  });

  const handleCreateStory = (e: FormEvent) => {
    e.preventDefault();
    if (newTeaser.trim() && newContent.trim()) {
      createMutation.mutate({ teaser: newTeaser, content: newContent });
    }
  };

  const headerAction =
    isAuthenticated && !showCreateForm && !atDailyLimit && canCreateRoot ? (
      <Button variant="primary" onClick={() => setShowCreateForm(true)}>
        New story
      </Button>
    ) : null;

  return (
    <PageShell headerAction={headerAction}>
      <main className="max-w-3xl mx-auto px-4 py-8">
        {isAuthenticated && atDailyLimit && (
          <div className="mb-8">
            <DailyLimitNotice dailyPartLimit={dailyPartLimit} />
          </div>
        )}

        {blockedFromRoot && (
          <div className="mb-8">
            <RootCreateGateNotice
              belowMinReputation={belowMinRep}
              minReputation={minRepRoot}
              openRootTrees={openRoots}
              maxConcurrentTrees={maxOpenRoots}
            />
          </div>
        )}

        {showCreateForm && isAuthenticated && !atDailyLimit && canCreateRoot && (
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
              contentLabel="Story beginning"
            />
            {createMutation.isError ? (
              <p className="mt-2 text-sm text-downvote">
                {getApiErrorMessage(createMutation.error, 'Failed to publish story.')}
              </p>
            ) : null}
          </div>
        )}

        <div className="mb-4 space-y-3">
          <div className="flex flex-wrap items-end justify-between gap-3">
            <h1 className="text-lg font-semibold text-text">Discover</h1>
            {!isSearching ? (
              <div className="flex items-center gap-1 text-sm" role="group" aria-label="Sort stories">
                <button
                  type="button"
                  onClick={() => setSort('latest')}
                  className={
                    sort === 'latest'
                      ? 'px-2 py-1 font-semibold text-accent'
                      : 'px-2 py-1 text-muted hover:text-text'
                  }
                >
                  Latest
                </button>
                <span className="text-border" aria-hidden>
                  ·
                </span>
                <button
                  type="button"
                  onClick={() => setSort('popular')}
                  className={
                    sort === 'popular'
                      ? 'px-2 py-1 font-semibold text-accent'
                      : 'px-2 py-1 text-muted hover:text-text'
                  }
                >
                  Popular
                </button>
              </div>
            ) : (
              <span className="text-sm text-muted">Search results</span>
            )}
          </div>
          <label className="block">
            <span className="sr-only">Search stories</span>
            <Input
              type="search"
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              placeholder="Search teasers and story text…"
              className="w-full"
            />
          </label>
        </div>

        {isLoading ? (
          <Panel className="p-12 text-center text-muted">Loading stories…</Panel>
        ) : error ? (
          <Panel className="p-12 text-center text-downvote">Error loading stories</Panel>
        ) : stories && stories.length > 0 ? (
          <Panel className="overflow-hidden discover-list-enter">
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
            {isSearching
              ? 'No stories match that search.'
              : sort === 'popular'
                ? 'No popular stories yet.'
                : 'No stories yet. Be the first to create one!'}
          </Panel>
        )}
      </main>
    </PageShell>
  );
};

export default Home;
