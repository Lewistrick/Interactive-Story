import { useEffect, useState, type FC } from 'react';
import { Link, Navigate, useParams } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  moderatorApi,
  type ModeratorUserPart,
  type ModeratorUserVote,
  type PartSortField,
} from '../api/moderation';
import { useAuth } from '../contexts/useAuth';
import CollapsibleSection from '../components/CollapsibleSection';
import PageShell from '../components/PageShell';
import ScoreBadge from '../components/ScoreBadge';
import Button from '../components/ui/Button';
import Panel from '../components/ui/Panel';

const PREVIEW_LIMIT = 5;
const PAGE_SIZE = 20;

/** Dense authored-part row with open / quarantine actions. */
const PartRow: FC<{
  part: ModeratorUserPart;
  onQuarantine: (id: string) => void;
  quarantinePending: boolean;
}> = ({ part, onQuarantine, quarantinePending }) => (
  <li className="flex flex-wrap items-center justify-between gap-3 border-b border-border px-4 py-3 last:border-b-0">
    <div className="min-w-0 flex-1">
      <p className="truncate font-medium text-text">{part.teaser}</p>
      <p className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted">
        <ScoreBadge score={part.vote_score} />
        <span className="tabular-nums">rec {part.recursive_score}</span>
        <span>depth {part.depth_level}</span>
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
      {!part.is_quarantined ? (
        <Button
          variant="ghost"
          className="!px-3 !py-1.5 text-sm"
          onClick={() => onQuarantine(part.id)}
          disabled={quarantinePending}
        >
          Quarantine
        </Button>
      ) : null}
    </div>
  </li>
);

/** Dense vote row showing UP/DOWN and target part. */
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
 * Moderator user history page (Wireframe C).
 *
 * Summary strip + collapsible authored / votes sections so long lists stay scannable.
 */
const ModeratorUserPage: FC = () => {
  const { userId } = useParams<{ userId: string }>();
  const { user, isAuthenticated } = useAuth();
  const queryClient = useQueryClient();

  const [authoredOpen, setAuthoredOpen] = useState(true);
  const [votesOpen, setVotesOpen] = useState(false);
  const [authoredExpanded, setAuthoredExpanded] = useState(false);
  const [votesExpanded, setVotesExpanded] = useState(false);
  const [sort, setSort] = useState<PartSortField>('age');
  const [authoredItems, setAuthoredItems] = useState<ModeratorUserPart[]>([]);
  const [voteItems, setVoteItems] = useState<ModeratorUserVote[]>([]);
  const [loadingMoreParts, setLoadingMoreParts] = useState(false);
  const [loadingMoreVotes, setLoadingMoreVotes] = useState(false);

  const profileQuery = useQuery({
    queryKey: ['moderator-user', userId],
    queryFn: () => moderatorApi.getUserProfile(userId!),
    enabled: isAuthenticated && !!user?.is_moderator && !!userId,
  });

  const partsQuery = useQuery({
    queryKey: ['moderator-user-parts-preview', userId, sort],
    queryFn: () =>
      moderatorApi.getUserParts(userId!, {
        sort,
        order: 'desc',
        skip: 0,
        limit: PREVIEW_LIMIT,
      }),
    enabled: isAuthenticated && !!user?.is_moderator && !!userId && authoredOpen,
  });

  const votesQuery = useQuery({
    queryKey: ['moderator-user-votes-preview', userId],
    queryFn: () =>
      moderatorApi.getUserVotes(userId!, {
        skip: 0,
        limit: PREVIEW_LIMIT,
      }),
    enabled: isAuthenticated && !!user?.is_moderator && !!userId && votesOpen,
  });

  useEffect(() => {
    setAuthoredExpanded(false);
    setAuthoredItems([]);
  }, [sort, userId]);

  useEffect(() => {
    setVotesExpanded(false);
    setVoteItems([]);
  }, [userId]);

  const invalidateUser = () => {
    queryClient.invalidateQueries({ queryKey: ['moderator-user', userId] });
    queryClient.invalidateQueries({ queryKey: ['moderator-user-parts-preview', userId] });
    queryClient.invalidateQueries({ queryKey: ['moderator-user-votes-preview', userId] });
    queryClient.invalidateQueries({ queryKey: ['moderator-queue'] });
    setAuthoredExpanded(false);
    setVotesExpanded(false);
    setAuthoredItems([]);
    setVoteItems([]);
  };

  const warnMutation = useMutation({
    mutationFn: () => {
      const reason = window.prompt('Warning message for the user:');
      if (!reason?.trim()) {
        return Promise.reject(new Error('cancelled'));
      }
      return moderatorApi.warnUser(userId!, reason.trim());
    },
    onSuccess: invalidateUser,
  });

  const blockMutation = useMutation({
    mutationFn: () => {
      const reason = window.prompt('Block reason (optional):') ?? undefined;
      return moderatorApi.blockUser(userId!, reason?.trim() || undefined);
    },
    onSuccess: invalidateUser,
  });

  const quarantineMutation = useMutation({
    mutationFn: (partId: string) => moderatorApi.remove('STORY_PART', partId),
    onSuccess: invalidateUser,
  });

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }
  if (!user?.is_moderator) {
    return (
      <PageShell>
        <main className="mx-auto max-w-3xl px-4 py-16 text-center text-muted">
          Moderator access required.
        </main>
      </PageShell>
    );
  }
  if (!userId) {
    return <Navigate to="/moderator" replace />;
  }

  const profile = profileQuery.data;
  const previewParts = partsQuery.data ?? [];
  const previewVotes = votesQuery.data ?? [];
  const displayedParts = authoredExpanded ? authoredItems : previewParts;
  const displayedVotes = votesExpanded ? voteItems : previewVotes;

  const showAllAuthored = async () => {
    setLoadingMoreParts(true);
    try {
      const first = await moderatorApi.getUserParts(userId, {
        sort,
        order: 'desc',
        skip: 0,
        limit: PAGE_SIZE,
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
      const more = await moderatorApi.getUserParts(userId, {
        sort,
        order: 'desc',
        skip: authoredItems.length,
        limit: PAGE_SIZE,
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
          <Link to="/moderator" className="text-accent hover:text-accent-hover">
            ← Back to moderation
          </Link>
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
                  {profile.is_quarantined && profile.quarantine_reason ? (
                    <p className="font-serif text-sm text-text">{profile.quarantine_reason}</p>
                  ) : null}
                  <p className="text-sm text-muted">
                    <span className="tabular-nums">{profile.authored_count}</span> authored
                    <span className="mx-2 text-border">·</span>
                    <span className="tabular-nums">{profile.votes_cast_count}</span> votes
                    <span className="mx-2 text-border">·</span>
                    <span className="tabular-nums">{profile.quarantined_parts_count}</span> parts
                    quarantined
                  </p>
                  <p className="text-xs text-muted">
                    Joined {new Date(profile.created_at).toLocaleDateString()}
                    {profile.quarantine_until
                      ? ` · quarantine until ${new Date(profile.quarantine_until).toLocaleString()}`
                      : ''}
                  </p>
                </div>
                <div className="flex flex-wrap gap-2">
                  <Button
                    variant="secondary"
                    onClick={() => warnMutation.mutate()}
                    disabled={warnMutation.isPending || profile.is_blocked}
                  >
                    Warn…
                  </Button>
                  <Button
                    variant="ghost"
                    onClick={() => blockMutation.mutate()}
                    disabled={blockMutation.isPending || profile.is_blocked}
                  >
                    Block…
                  </Button>
                </div>
              </div>
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
                    value={sort}
                    onChange={(e) => setSort(e.target.value as PartSortField)}
                  >
                    <option value="age">Age</option>
                    <option value="vote_score">Vote score</option>
                    <option value="recursive_score">Recursive score</option>
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
                        onQuarantine={(id) => quarantineMutation.mutate(id)}
                        quarantinePending={quarantineMutation.isPending}
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

            <CollapsibleSection
              title="Votes cast"
              count={profile.votes_cast_count}
              meta={
                <span className="tabular-nums">
                  <span className="text-upvote">▲ {profile.votes_up_count}</span>
                  {' · '}
                  <span className="text-downvote">▼ {profile.votes_down_count}</span>
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
                  {profile.votes_cast_count > displayedVotes.length ? (
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
          </>
        )}
      </main>
    </PageShell>
  );
};

export default ModeratorUserPage;
