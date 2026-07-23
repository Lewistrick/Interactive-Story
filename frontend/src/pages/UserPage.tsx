import { useEffect, useState, type FC } from 'react';
import { Link, Navigate, useParams } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { moderatorApi, type ModeratorUserVote } from '../api/moderation';
import { storiesApi } from '../api/stories';
import { usersApi, type PartSortField, type PartSortOrder, type UserPart } from '../api/users';
import { useAuth } from '../contexts/useAuth';
import CollapsibleSection from '../components/CollapsibleSection';
import ModerationReasonForm from '../components/ModerationReasonForm';
import PageShell from '../components/PageShell';
import ScoreBadge from '../components/ScoreBadge';
import Button from '../components/ui/Button';
import Panel from '../components/ui/Panel';

const PREVIEW_LIMIT = 5;
const PAGE_SIZE = 20;

type SortOption =
  | 'age'
  | 'vote_score_desc'
  | 'vote_score_asc'
  | 'recursive_score_desc'
  | 'recursive_score_asc';

function parseSortOption(option: SortOption): { sort: PartSortField; order: PartSortOrder } {
  switch (option) {
    case 'vote_score_asc':
      return { sort: 'vote_score', order: 'asc' };
    case 'vote_score_desc':
      return { sort: 'vote_score', order: 'desc' };
    case 'recursive_score_asc':
      return { sort: 'recursive_score', order: 'asc' };
    case 'recursive_score_desc':
      return { sort: 'recursive_score', order: 'desc' };
    default:
      return { sort: 'age', order: 'desc' };
  }
}

/** Dense authored-part row. */
const PartRow: FC<{
  part: UserPart;
  isOwner: boolean;
  isModerator: boolean;
  onQuarantine: (id: string) => void;
  onDelete: (id: string) => void;
  actionPending: boolean;
}> = ({ part, isOwner, isModerator, onQuarantine, onDelete, actionPending }) => (
  <li className="flex flex-wrap items-center justify-between gap-3 border-b border-border px-4 py-3 last:border-b-0">
    <div className="min-w-0 flex-1">
      <p className="truncate font-medium text-text">{part.teaser}</p>
      <p className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted">
        <ScoreBadge score={part.vote_score} />
        <span className="tabular-nums">rec {part.recursive_score}</span>
        <span>depth {part.depth_level}</span>
        <span>{part.children_count} branches</span>
        <span>{new Date(part.created_at).toLocaleString()}</span>
        {part.is_quarantined ? (
          <span className="uppercase tracking-wide text-downvote">quarantined</span>
        ) : null}
      </p>
    </div>
    <div className="flex shrink-0 flex-wrap gap-2">
      <a
        href={`/story/${part.id}`}
        target="_blank"
        rel="noreferrer"
        className="inline-flex items-center rounded-lg px-3 py-1.5 text-sm text-accent hover:text-accent-hover"
      >
        Open
      </a>
      {isOwner && part.children_count === 0 ? (
        <Button
          variant="ghost"
          className="!px-3 !py-1.5 text-sm"
          onClick={() => onDelete(part.id)}
          disabled={actionPending}
        >
          Delete
        </Button>
      ) : null}
      {isModerator && !part.is_quarantined ? (
        <Button
          variant="ghost"
          className="!px-3 !py-1.5 text-sm"
          onClick={() => onQuarantine(part.id)}
          disabled={actionPending}
        >
          Quarantine
        </Button>
      ) : null}
    </div>
  </li>
);

/** Dense vote row (moderators only). */
const VoteRow: FC<{ vote: ModeratorUserVote }> = ({ vote }) => {
  const up = vote.vote_type === 'UP';
  return (
    <li className="flex flex-wrap items-center justify-between gap-3 border-b border-border px-4 py-3 last:border-b-0">
      <div className="min-w-0 flex-1">
        <p className="truncate font-medium text-text">{vote.teaser}</p>
        <p className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted">
          <span className={up ? 'font-medium text-upvote' : 'font-medium text-downvote'}>
            {up ? '▲ UP' : '▼ DOWN'}
          </span>
          <ScoreBadge score={vote.vote_score} />
          {vote.author_username ? <span>by {vote.author_username}</span> : null}
          <span>{new Date(vote.voted_at).toLocaleString()}</span>
          {vote.is_quarantined ? (
            <span className="uppercase tracking-wide text-downvote">quarantined</span>
          ) : null}
        </p>
      </div>
      <a
        href={`/story/${vote.story_part_id}`}
        target="_blank"
        rel="noreferrer"
        className="inline-flex items-center rounded-lg px-3 py-1.5 text-sm text-accent hover:text-accent-hover"
      >
        Open
      </a>
    </li>
  );
};

/**
 * Public user profile: authored parts (newest / highest scores).
 *
 * Owners can delete leaf parts. Moderators see quarantine status, votes cast,
 * and warn/block/unblock controls.
 */
const UserPage: FC = () => {
  const { userId } = useParams<{ userId: string }>();
  const { user, isAuthenticated } = useAuth();
  const queryClient = useQueryClient();

  const isModerator = Boolean(isAuthenticated && user?.is_moderator);
  const isOwner = Boolean(isAuthenticated && userId && user?.id === userId);

  const [authoredOpen, setAuthoredOpen] = useState(true);
  const [votesOpen, setVotesOpen] = useState(false);
  const [authoredExpanded, setAuthoredExpanded] = useState(false);
  const [votesExpanded, setVotesExpanded] = useState(false);
  const [sortOption, setSortOption] = useState<SortOption>('age');
  const { sort, order } = parseSortOption(sortOption);
  const [authoredItems, setAuthoredItems] = useState<UserPart[]>([]);
  const [voteItems, setVoteItems] = useState<ModeratorUserVote[]>([]);
  const [loadingMoreParts, setLoadingMoreParts] = useState(false);
  const [loadingMoreVotes, setLoadingMoreVotes] = useState(false);
  const [reasonMode, setReasonMode] = useState<'warn' | 'block' | 'unblock' | null>(null);

  const profileQuery = useQuery({
    queryKey: ['user-profile', userId, isModerator],
    queryFn: () => usersApi.getProfile(userId!),
    enabled: !!userId,
  });

  const partsQuery = useQuery({
    queryKey: ['user-parts-preview', userId, sortOption, isModerator],
    queryFn: () =>
      usersApi.getParts(userId!, {
        sort,
        order,
        skip: 0,
        limit: PREVIEW_LIMIT,
        include_quarantined: isModerator,
      }),
    enabled: !!userId && authoredOpen,
  });

  const votesQuery = useQuery({
    queryKey: ['user-votes-preview', userId],
    queryFn: () =>
      moderatorApi.getUserVotes(userId!, {
        skip: 0,
        limit: PREVIEW_LIMIT,
      }),
    enabled: isModerator && !!userId && votesOpen,
  });

  useEffect(() => {
    setAuthoredExpanded(false);
    setAuthoredItems([]);
  }, [sortOption, userId]);

  useEffect(() => {
    setVotesExpanded(false);
    setVoteItems([]);
  }, [userId]);

  const invalidateUser = () => {
    queryClient.invalidateQueries({ queryKey: ['user-profile', userId] });
    queryClient.invalidateQueries({ queryKey: ['user-parts-preview', userId] });
    queryClient.invalidateQueries({ queryKey: ['user-votes-preview', userId] });
    queryClient.invalidateQueries({ queryKey: ['moderator-queue'] });
    queryClient.invalidateQueries({ queryKey: ['moderator-patterns'] });
    setAuthoredExpanded(false);
    setVotesExpanded(false);
    setAuthoredItems([]);
    setVoteItems([]);
    setReasonMode(null);
  };

  const warnMutation = useMutation({
    mutationFn: ({ reason, durationHours }: { reason: string; durationHours?: number }) =>
      moderatorApi.warnUser(userId!, reason, durationHours),
    onSuccess: invalidateUser,
  });

  const blockMutation = useMutation({
    mutationFn: (reason: string) => moderatorApi.blockUser(userId!, reason || undefined),
    onSuccess: invalidateUser,
  });

  const unblockMutation = useMutation({
    mutationFn: (reason: string) => moderatorApi.unblockUser(userId!, reason || undefined),
    onSuccess: invalidateUser,
  });

  const quarantineMutation = useMutation({
    mutationFn: (partId: string) => moderatorApi.remove('STORY_PART', partId),
    onSuccess: invalidateUser,
  });

  const deleteMutation = useMutation({
    mutationFn: (partId: string) => storiesApi.deleteStoryPart(partId),
    onSuccess: invalidateUser,
  });

  if (!userId) {
    return <Navigate to="/" replace />;
  }

  const profile = profileQuery.data;
  const previewParts = partsQuery.data ?? [];
  const previewVotes = votesQuery.data ?? [];
  const displayedParts = authoredExpanded ? authoredItems : previewParts;
  const displayedVotes = votesExpanded ? voteItems : previewVotes;
  const actionPending =
    quarantineMutation.isPending ||
    deleteMutation.isPending ||
    warnMutation.isPending ||
    blockMutation.isPending ||
    unblockMutation.isPending;

  const showAllAuthored = async () => {
    setLoadingMoreParts(true);
    try {
      const first = await usersApi.getParts(userId, {
        sort,
        order,
        skip: 0,
        limit: PAGE_SIZE,
        include_quarantined: isModerator,
      });
      setAuthoredItems(first);
      setAuthoredExpanded(true);
    } finally {
      setLoadingMoreParts(false);
    }
  };

  const loadMoreAuthored = async () => {
    setLoadingMoreParts(true);
    try {
      const more = await usersApi.getParts(userId, {
        sort,
        order,
        skip: authoredItems.length,
        limit: PAGE_SIZE,
        include_quarantined: isModerator,
      });
      setAuthoredItems((prev) => {
        const ids = new Set(prev.map((p) => p.id));
        return [...prev, ...more.filter((p) => !ids.has(p.id))];
      });
    } finally {
      setLoadingMoreParts(false);
    }
  };

  const showAllVotes = async () => {
    setLoadingMoreVotes(true);
    try {
      const first = await moderatorApi.getUserVotes(userId, {
        skip: 0,
        limit: PAGE_SIZE,
      });
      setVoteItems(first);
      setVotesExpanded(true);
    } finally {
      setLoadingMoreVotes(false);
    }
  };

  const loadMoreVotes = async () => {
    setLoadingMoreVotes(true);
    try {
      const more = await moderatorApi.getUserVotes(userId, {
        skip: voteItems.length,
        limit: PAGE_SIZE,
      });
      setVoteItems((prev) => {
        const ids = new Set(prev.map((v) => v.vote_id));
        return [...prev, ...more.filter((v) => !ids.has(v.vote_id))];
      });
    } finally {
      setLoadingMoreVotes(false);
    }
  };

  return (
    <PageShell>
      <main className="mx-auto max-w-3xl space-y-6 px-4 py-8">
        <p className="text-sm text-muted">
          {isModerator ? (
            <Link to="/moderator" className="text-accent hover:text-accent-hover">
              ← Back to moderation
            </Link>
          ) : (
            <Link to="/" className="text-accent hover:text-accent-hover">
              ← Back to stories
            </Link>
          )}
        </p>

        {profileQuery.isLoading ? (
          <p className="text-muted">Loading user…</p>
        ) : profileQuery.isError || !profile ? (
          <Panel className="p-8 text-center text-muted">User not found.</Panel>
        ) : (
          <>
            <Panel className="p-4">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div className="min-w-0 space-y-2">
                  <h1 className="text-2xl font-semibold text-text">@{profile.username}</h1>
                  <p className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-muted">
                    <ScoreBadge score={profile.reputation_score} label="Rep " />
                    {profile.is_blocked ? (
                      <span className="uppercase tracking-wide text-downvote">blocked</span>
                    ) : null}
                    {profile.is_quarantined ? (
                      <span className="uppercase tracking-wide text-downvote">quarantined</span>
                    ) : null}
                    {profile.is_moderator ? (
                      <span className="uppercase tracking-wide text-accent">moderator</span>
                    ) : null}
                  </p>
                  {isModerator && profile.is_quarantined && profile.quarantine_reason ? (
                    <p className="font-serif text-sm text-text">{profile.quarantine_reason}</p>
                  ) : null}
                  <p className="text-sm text-muted">
                    <span className="tabular-nums">{profile.authored_count}</span> authored
                    {isModerator && profile.votes_cast_count != null ? (
                      <>
                        <span className="mx-2 text-border">·</span>
                        <span className="tabular-nums">{profile.votes_cast_count}</span> votes
                      </>
                    ) : null}
                    {isModerator && profile.quarantined_parts_count != null ? (
                      <>
                        <span className="mx-2 text-border">·</span>
                        <span className="tabular-nums">{profile.quarantined_parts_count}</span>{' '}
                        parts quarantined
                      </>
                    ) : null}
                  </p>
                  <p className="text-xs text-muted">
                    Joined {new Date(profile.created_at).toLocaleDateString()}
                    {isModerator && profile.quarantine_until
                      ? ` · quarantine until ${new Date(profile.quarantine_until).toLocaleString()}`
                      : ''}
                  </p>
                </div>
                {isModerator ? (
                  <div className="flex flex-wrap gap-2">
                    {profile.is_blocked ? (
                      <Button
                        variant="secondary"
                        onClick={() => setReasonMode('unblock')}
                        disabled={unblockMutation.isPending}
                      >
                        Unblock…
                      </Button>
                    ) : (
                      <>
                        <Button
                          variant="secondary"
                          onClick={() => setReasonMode('warn')}
                          disabled={warnMutation.isPending}
                        >
                          Warn…
                        </Button>
                        <Button
                          variant="ghost"
                          onClick={() => setReasonMode('block')}
                          disabled={blockMutation.isPending}
                        >
                          Block…
                        </Button>
                      </>
                    )}
                  </div>
                ) : null}
              </div>
              {isModerator && reasonMode ? (
                <ModerationReasonForm
                  mode={reasonMode}
                  pending={
                    warnMutation.isPending ||
                    blockMutation.isPending ||
                    unblockMutation.isPending
                  }
                  onCancel={() => setReasonMode(null)}
                  onSubmit={(reason, durationHours) => {
                    if (reasonMode === 'warn') {
                      warnMutation.mutate({ reason, durationHours });
                    } else if (reasonMode === 'block') {
                      blockMutation.mutate(reason);
                    } else {
                      unblockMutation.mutate(reason);
                    }
                  }}
                />
              ) : null}
            </Panel>

            <CollapsibleSection
              title="Authored parts"
              count={profile.authored_count}
              open={authoredOpen}
              onToggle={() => setAuthoredOpen((o) => !o)}
              toolbar={
                <label className="flex items-center gap-2 text-sm text-muted">
                  Sort
                  <select
                    className="rounded-lg border border-border bg-surface px-2 py-1 text-text"
                    value={sortOption}
                    onChange={(e) => setSortOption(e.target.value as SortOption)}
                  >
                    <option value="age">Newest</option>
                    <option value="vote_score_desc">Highest vote score</option>
                    <option value="recursive_score_desc">Highest recursive score</option>
                    {isModerator ? (
                      <>
                        <option value="vote_score_asc">Lowest vote score</option>
                        <option value="recursive_score_asc">Lowest recursive score</option>
                      </>
                    ) : null}
                  </select>
                </label>
              }
            >
              {partsQuery.isLoading ? (
                <p className="px-4 py-6 text-sm text-muted">Loading parts…</p>
              ) : displayedParts.length === 0 ? (
                <p className="px-4 py-6 text-sm text-muted">No authored parts.</p>
              ) : (
                <>
                  <ul className="m-0 list-none p-0">
                    {displayedParts.map((part) => (
                      <PartRow
                        key={part.id}
                        part={part}
                        isOwner={isOwner}
                        isModerator={isModerator}
                        onQuarantine={(id) => quarantineMutation.mutate(id)}
                        onDelete={(id) => deleteMutation.mutate(id)}
                        actionPending={actionPending}
                      />
                    ))}
                  </ul>
                  {profile.authored_count > displayedParts.length ? (
                    <div className="border-t border-border px-4 py-3">
                      <Button
                        variant="ghost"
                        className="!px-0"
                        disabled={loadingMoreParts}
                        onClick={() =>
                          void (authoredExpanded ? loadMoreAuthored() : showAllAuthored())
                        }
                      >
                        {authoredExpanded
                          ? 'Load more authored →'
                          : `Show all authored (${profile.authored_count}) →`}
                      </Button>
                    </div>
                  ) : null}
                </>
              )}
            </CollapsibleSection>

            {isModerator ? (
              <CollapsibleSection
                title="Votes cast"
                count={profile.votes_cast_count ?? 0}
                meta={
                  <span className="tabular-nums">
                    <span className="text-upvote">▲ {profile.votes_up_count ?? 0}</span>
                    {' · '}
                    <span className="text-downvote">▼ {profile.votes_down_count ?? 0}</span>
                  </span>
                }
                open={votesOpen}
                onToggle={() => setVotesOpen((o) => !o)}
              >
                {votesQuery.isLoading ? (
                  <p className="px-4 py-6 text-sm text-muted">Loading votes…</p>
                ) : displayedVotes.length === 0 ? (
                  <p className="px-4 py-6 text-sm text-muted">No votes cast.</p>
                ) : (
                  <>
                    <ul className="m-0 list-none p-0">
                      {displayedVotes.map((vote) => (
                        <VoteRow key={vote.vote_id} vote={vote} />
                      ))}
                    </ul>
                    {(profile.votes_cast_count ?? 0) > displayedVotes.length ? (
                      <div className="border-t border-border px-4 py-3">
                        <Button
                          variant="ghost"
                          className="!px-0"
                          disabled={loadingMoreVotes}
                          onClick={() => void (votesExpanded ? loadMoreVotes() : showAllVotes())}
                        >
                          {votesExpanded
                            ? 'Load more votes →'
                            : `Show all votes (${profile.votes_cast_count}) →`}
                        </Button>
                      </div>
                    ) : null}
                  </>
                )}
              </CollapsibleSection>
            ) : null}
          </>
        )}
      </main>
    </PageShell>
  );
};

export default UserPage;
