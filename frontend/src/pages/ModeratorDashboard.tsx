import { useState, type FC } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link, Navigate } from 'react-router-dom';
import { moderatorApi, type QuarantineLog } from '../api/moderation';
import { useAuth } from '../contexts/useAuth';
import PageShell from '../components/PageShell';
import Button from '../components/ui/Button';
import Panel from '../components/ui/Panel';

/** Moderator quarantine queue and recent audit entries. */
const ModeratorDashboard: FC = () => {
  const { user, isAuthenticated } = useAuth();
  const queryClient = useQueryClient();
  const [tab, setTab] = useState<'queue' | 'audit'>('queue');

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

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ['moderator-queue'] });
    queryClient.invalidateQueries({ queryKey: ['moderator-audit'] });
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

  const items = tab === 'queue' ? queueQuery.data : auditQuery.data;
  const loading = tab === 'queue' ? queueQuery.isLoading : auditQuery.isLoading;

  return (
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
            part permanently without deleting children; Block freezes a user.
          </p>
        </header>

        <div className="flex gap-2">
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
        </div>

        {loading ? (
          <p className="text-muted">Loading…</p>
        ) : !items || items.length === 0 ? (
          <Panel className="p-8 text-center text-muted">No items.</Panel>
        ) : (
          <ul className="m-0 list-none space-y-3 p-0">
            {items.map((item) => (
              <li key={item.id}>
                <Panel className="p-4">
                  <div className="flex flex-wrap items-baseline justify-between gap-2">
                    <h2 className="font-semibold text-text">
                      {item.entity_type === 'STORY_PART' && item.teaser
                        ? item.teaser
                        : item.entity_type === 'USER' && item.author_username
                          ? `User · ${item.author_username}`
                          : `${item.entity_type} · ${item.entity_id.slice(0, 8)}…`}
                    </h2>
                    <span className="text-xs text-muted tabular-nums">
                      {new Date(item.created_at).toLocaleString()}
                    </span>
                  </div>
                  {item.entity_type === 'STORY_PART' ? (
                    <div className="mt-2 space-y-1">
                      <p className="text-sm text-muted">
                        Author: {item.author_username || 'Unknown'}
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
                  {tab === 'queue' && !item.resolved_at ? (
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
                          <Link
                            to={`/story/${item.entity_id}`}
                            className="inline-flex items-center text-sm text-accent hover:text-accent-hover"
                          >
                            View
                          </Link>
                        </>
                      ) : (
                        <Button
                          variant="ghost"
                          onClick={() => blockMutation.mutate(item)}
                          disabled={blockMutation.isPending}
                        >
                          Block user
                        </Button>
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
  );
};

export default ModeratorDashboard;
