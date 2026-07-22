import { useMemo, useState, type FC } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import {
  moderatorApi,
  type QuarantineLog,
  type ReputationPoint,
  type VotingPatternFlag,
} from '../api/moderation';
import { useAuth } from '../contexts/useAuth';
import PageShell from '../components/PageShell';
import RequireModerator from '../components/RequireModerator';
import Button from '../components/ui/Button';
import Panel from '../components/ui/Panel';

/** Tiny SVG sparkline from reputation history points. */
const ReputationSparkline: FC<{ points: ReputationPoint[] }> = ({ points }) => {
  if (points.length < 2) {
    return <p className="text-xs text-muted">Not enough history yet.</p>;
  }
  const scores = points.map((p) => p.score);
  const min = Math.min(...scores);
  const max = Math.max(...scores);
  const span = Math.max(max - min, 1);
  const w = 160;
  const h = 36;
  const path = points
    .map((p, i) => {
      const x = (i / (points.length - 1)) * w;
      const y = h - ((p.score - min) / span) * (h - 4) - 2;
      return `${i === 0 ? 'M' : 'L'}${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(' ');
  return (
    <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} aria-hidden className="text-accent">
      <path d={path} fill="none" stroke="currentColor" strokeWidth="1.5" />
    </svg>
  );
};

/** Moderator quarantine queue, voting insights, and bulk actions. */
const ModeratorDashboard: FC = () => {
  const { user, isAuthenticated } = useAuth();
  const queryClient = useQueryClient();
  const [tab, setTab] = useState<'queue' | 'audit' | 'patterns'>('queue');
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [historyUserId, setHistoryUserId] = useState<string | null>(null);

  const queueQuery = useQuery({
    queryKey: ['moderator-queue'],
    queryFn: () => moderatorApi.getQueue(),
    enabled: isAuthenticated && !!user?.is_moderator,
  });

  const auditQuery = useQuery({
    queryKey: ['moderator-audit'],
    queryFn: () => moderatorApi.getAuditLog(),
    enabled: isAuthenticated && !!user?.is_moderator && tab === 'audit',
  });

  const patternsQuery = useQuery({
    queryKey: ['moderator-patterns'],
    queryFn: () => moderatorApi.getVotingPatterns(),
    enabled: isAuthenticated && !!user?.is_moderator && tab === 'patterns',
  });

  const historyQuery = useQuery({
    queryKey: ['moderator-rep-history', historyUserId],
    queryFn: () => moderatorApi.getReputationHistory(historyUserId!),
    enabled: !!historyUserId,
  });

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ['moderator-queue'] });
    queryClient.invalidateQueries({ queryKey: ['moderator-audit'] });
    queryClient.invalidateQueries({ queryKey: ['moderator-patterns'] });
    setSelected(new Set());
  };

  const allowMutation = useMutation({
    mutationFn: (item: QuarantineLog) => moderatorApi.allow(item.entity_type, item.entity_id),
    onSuccess: invalidate,
  });

  const removeMutation = useMutation({
    mutationFn: (item: QuarantineLog) => moderatorApi.remove(item.entity_type, item.entity_id),
    onSuccess: invalidate,
  });

  const blockMutation = useMutation({
    mutationFn: (item: QuarantineLog) => moderatorApi.blockUser(item.entity_id),
    onSuccess: invalidate,
  });

  const warnMutation = useMutation({
    mutationFn: (userId: string) => {
      const reason = window.prompt('Warning message for the user:');
      if (!reason || !reason.trim()) {
        return Promise.reject(new Error('cancelled'));
      }
      return moderatorApi.warnUser(userId, reason.trim());
    },
    onSuccess: invalidate,
  });

  const bulkMutation = useMutation({
    mutationFn: (action: 'allow' | 'remove' | 'block') => {
      const items = (queueQuery.data ?? []).filter((i) => selected.has(i.id));
      return moderatorApi.bulk(
        action,
        items.map((i) => ({ entity_type: i.entity_type, entity_id: i.entity_id })),
      );
    },
    onSuccess: invalidate,
  });

  const toggleSelect = (id: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const queueItems = queueQuery.data ?? [];
  const allSelected = useMemo(
    () => queueItems.length > 0 && queueItems.every((i) => selected.has(i.id)),
    [queueItems, selected],
  );

  const items = tab === 'queue' ? queueQuery.data : tab === 'audit' ? auditQuery.data : undefined;
  const loading =
    tab === 'queue'
      ? queueQuery.isLoading
      : tab === 'audit'
        ? auditQuery.isLoading
        : patternsQuery.isLoading;

  return (
    <RequireModerator>
    <PageShell>
      <main className="mx-auto max-w-3xl px-4 py-8 space-y-6">
        <header>
          <p className="mb-2 text-sm text-muted">
            <Link to="/" className="text-accent hover:text-accent-hover">
              ← Back to stories
            </Link>
          </p>
          <h1 className="text-2xl font-semibold text-text">Moderation</h1>
          <p className="mt-2 font-serif text-muted">
            Review quarantined stories and accounts. Allow restores visibility; Remove hides a
            part permanently without deleting children; Warn pauses posting temporarily; Block
            freezes a user. Use Patterns for voting anomalies and reputation history.
          </p>
        </header>

        <div className="flex flex-wrap gap-2">
          <Button
            variant={tab === 'queue' ? 'primary' : 'ghost'}
            onClick={() => setTab('queue')}
          >
            Queue
          </Button>
          <Button
            variant={tab === 'audit' ? 'primary' : 'ghost'}
            onClick={() => setTab('audit')}
          >
            Audit log
          </Button>
          <Button
            variant={tab === 'patterns' ? 'primary' : 'ghost'}
            onClick={() => setTab('patterns')}
          >
            Patterns
          </Button>
        </div>

        {tab === 'queue' && selected.size > 0 ? (
          <div className="flex flex-wrap items-center gap-2 rounded border border-border bg-surface/60 px-3 py-2">
            <span className="text-sm text-muted">{selected.size} selected</span>
            <Button
              variant="secondary"
              onClick={() => bulkMutation.mutate('allow')}
              disabled={bulkMutation.isPending}
            >
              Bulk allow
            </Button>
            <Button
              variant="ghost"
              onClick={() => bulkMutation.mutate('remove')}
              disabled={bulkMutation.isPending}
            >
              Bulk remove
            </Button>
            <Button
              variant="ghost"
              onClick={() => bulkMutation.mutate('block')}
              disabled={bulkMutation.isPending}
            >
              Bulk block
            </Button>
          </div>
        ) : null}

        {tab === 'patterns' ? (
          loading ? (
            <p className="text-muted">Loading…</p>
          ) : !patternsQuery.data || patternsQuery.data.length === 0 ? (
            <Panel className="p-8 text-center text-muted">No voting-pattern flags.</Panel>
          ) : (
            <ul className="m-0 list-none space-y-3 p-0">
              {patternsQuery.data.map((flag: VotingPatternFlag) => (
                <li key={`${flag.user_id}-${flag.flag}`}>
                  <Panel className="p-4">
                    <div className="flex flex-wrap items-baseline justify-between gap-2">
                      <h2 className="font-semibold text-text">
                        <Link
                          to={`/moderator/users/${flag.user_id}`}
                          className="text-accent hover:text-accent-hover"
                        >
                          {flag.username}
                        </Link>
                      </h2>
                      <span className="text-xs uppercase tracking-wide text-muted">{flag.flag}</span>
                    </div>
                    <p className="mt-1 text-sm text-muted">{flag.detail}</p>
                    <p className="mt-1 text-xs text-muted">
                      Reputation: {flag.reputation_score}
                    </p>
                    <div className="mt-3 flex flex-wrap items-center gap-3">
                      <Link
                        to={`/moderator/users/${flag.user_id}`}
                        className="text-sm text-accent hover:text-accent-hover"
                      >
                        User page
                      </Link>
                      <Button
                        variant="ghost"
                        onClick={() =>
                          setHistoryUserId((id) => (id === flag.user_id ? null : flag.user_id))
                        }
                      >
                        {historyUserId === flag.user_id ? 'Hide history' : 'Reputation history'}
                      </Button>
                      <Button
                        variant="ghost"
                        onClick={() => warnMutation.mutate(flag.user_id)}
                        disabled={warnMutation.isPending}
                      >
                        Warn
                      </Button>
                      <Button
                        variant="ghost"
                        onClick={() =>
                          blockMutation.mutate({
                            id: flag.user_id,
                            entity_type: 'USER',
                            entity_id: flag.user_id,
                          } as QuarantineLog)
                        }
                        disabled={blockMutation.isPending}
                      >
                        Block
                      </Button>
                    </div>
                    {historyUserId === flag.user_id ? (
                      <div className="mt-3">
                        {historyQuery.isLoading ? (
                          <p className="text-xs text-muted">Loading history…</p>
                        ) : (
                          <ReputationSparkline points={historyQuery.data ?? []} />
                        )}
                      </div>
                    ) : null}
                  </Panel>
                </li>
              ))}
            </ul>
          )
        ) : loading ? (
          <p className="text-muted">Loading…</p>
        ) : !items || items.length === 0 ? (
          <Panel className="p-8 text-center text-muted">No items.</Panel>
        ) : (
          <ul className="m-0 list-none space-y-3 p-0">
            {tab === 'queue' ? (
              <li className="px-1">
                <label className="inline-flex items-center gap-2 text-sm text-muted">
                  <input
                    type="checkbox"
                    checked={allSelected}
                    onChange={() => {
                      if (allSelected) setSelected(new Set());
                      else setSelected(new Set(queueItems.map((i) => i.id)));
                    }}
                  />
                  Select all
                </label>
              </li>
            ) : null}
            {items.map((item) => (
              <li key={item.id}>
                <Panel className="p-4">
                  <div className="flex flex-wrap items-baseline justify-between gap-2">
                    <div className="flex items-start gap-2">
                      {tab === 'queue' && !item.resolved_at ? (
                        <input
                          type="checkbox"
                          className="mt-1"
                          checked={selected.has(item.id)}
                          onChange={() => toggleSelect(item.id)}
                          aria-label="Select for bulk action"
                        />
                      ) : null}
                      <h2 className="font-semibold text-text">
                        {item.entity_type === 'STORY_PART' && item.teaser
                          ? item.teaser
                          : item.entity_type === 'USER' && item.author_username
                            ? (
                                <>
                                  User ·{' '}
                                  <Link
                                    to={`/moderator/users/${item.entity_id}`}
                                    className="text-accent hover:text-accent-hover"
                                  >
                                    {item.author_username}
                                  </Link>
                                </>
                              )
                            : `${item.entity_type} · ${item.entity_id.slice(0, 8)}…`}
                      </h2>
                    </div>
                    <span className="text-xs text-muted tabular-nums">
                      {new Date(item.created_at).toLocaleString()}
                    </span>
                  </div>
                  {item.entity_type === 'STORY_PART' ? (
                    <div className="mt-2 space-y-1">
                      <p className="text-sm text-muted">
                        Author:{' '}
                        {item.author_id && item.author_username ? (
                          <Link
                            to={`/moderator/users/${item.author_id}`}
                            className="text-accent hover:text-accent-hover"
                          >
                            {item.author_username}
                          </Link>
                        ) : (
                          item.author_username || 'Unknown'
                        )}
                      </p>
                      {item.content_preview ? (
                        <p className="font-serif text-sm leading-relaxed text-text">
                          {item.content_preview}
                        </p>
                      ) : null}
                    </div>
                  ) : null}
                  <p className="mt-2 text-sm text-muted">{item.reason}</p>
                  <p className="mt-1 text-xs text-muted">
                    Trigger: {item.triggered_by}
                    {item.automatic ? ' (automatic)' : ''}
                    {item.resolution_action
                      ? ` · Resolved: ${item.resolution_action}`
                      : ''}
                  </p>
                  {(item.author_id || item.entity_type === 'USER') && (
                    <div className="mt-2 flex flex-wrap items-center gap-3">
                      <Link
                        to={`/moderator/users/${
                          item.entity_type === 'USER' ? item.entity_id : item.author_id
                        }`}
                        className="text-sm text-accent hover:text-accent-hover"
                      >
                        User page
                      </Link>
                      <Button
                        variant="ghost"
                        onClick={() => {
                          const uid =
                            item.entity_type === 'USER' ? item.entity_id : item.author_id!;
                          setHistoryUserId((id) => (id === uid ? null : uid));
                        }}
                      >
                        Reputation history
                      </Button>
                      {historyUserId ===
                      (item.entity_type === 'USER' ? item.entity_id : item.author_id) ? (
                        <div className="mt-2 w-full">
                          {historyQuery.isLoading ? (
                            <p className="text-xs text-muted">Loading history…</p>
                          ) : (
                            <ReputationSparkline points={historyQuery.data ?? []} />
                          )}
                        </div>
                      ) : null}
                    </div>
                  )}                  {tab === 'queue' && !item.resolved_at ? (
                    <div className="mt-3 flex flex-wrap gap-2">
                      <Button
                        variant="secondary"
                        onClick={() => allowMutation.mutate(item)}
                        disabled={allowMutation.isPending}
                      >
                        Allow
                      </Button>
                      {item.entity_type === 'STORY_PART' ? (
                        <>
                          <Button
                            variant="ghost"
                            onClick={() => removeMutation.mutate(item)}
                            disabled={removeMutation.isPending}
                          >
                            Remove
                          </Button>
                          {item.author_id ? (
                            <Button
                              variant="ghost"
                              onClick={() => warnMutation.mutate(item.author_id!)}
                              disabled={warnMutation.isPending}
                            >
                              Warn author
                            </Button>
                          ) : null}
                          <Link
                            to={`/story/${item.entity_id}`}
                            className="inline-flex items-center text-sm text-accent hover:text-accent-hover"
                          >
                            View
                          </Link>
                        </>
                      ) : (
                        <>
                          <Button
                            variant="ghost"
                            onClick={() => warnMutation.mutate(item.entity_id)}
                            disabled={warnMutation.isPending}
                          >
                            Warn
                          </Button>
                          <Button
                            variant="ghost"
                            onClick={() => blockMutation.mutate(item)}
                            disabled={blockMutation.isPending}
                          >
                            Block user
                          </Button>
                        </>
                      )}
                    </div>
                  ) : null}
                </Panel>
              </li>
            ))}
          </ul>
        )}
      </main>
    </PageShell>
    </RequireModerator>
  );
};

export default ModeratorDashboard;
