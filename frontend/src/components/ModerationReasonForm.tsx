import { useId, useState, type FC, type FormEvent } from 'react';
import Button from './ui/Button';
import Input from './ui/Input';
import Label from './ui/Label';
import Textarea from './ui/Textarea';

export type ModerationReasonMode = 'warn' | 'block' | 'dismiss' | 'unblock';

interface ModerationReasonFormProps {
  mode: ModerationReasonMode;
  pending?: boolean;
  /**
   * Called with trimmed reason.
   * - warn: durationHours optional (server default if omitted)
   * - dismiss: durationHours undefined = server default; 0 = never expires
   * - block / unblock: duration unused
   */
  onSubmit: (reason: string, durationHours?: number) => void;
  onCancel: () => void;
}

/**
 * Inline moderation reason form (warn / block / dismiss pattern / unblock).
 *
 * Warn requires a message; other modes treat reason as optional.
 */
const ModerationReasonForm: FC<ModerationReasonFormProps> = ({
  mode,
  pending = false,
  onSubmit,
  onCancel,
}) => {
  const reasonId = useId();
  const durationId = useId();
  const [reason, setReason] = useState('');
  const [durationHours, setDurationHours] = useState('');
  const [error, setError] = useState('');

  const titles: Record<ModerationReasonMode, string> = {
    warn: 'Warn user',
    block: 'Block user',
    dismiss: 'Allow this pattern',
    unblock: 'Unblock user',
  };
  const submitLabels: Record<ModerationReasonMode, string> = {
    warn: 'Send warning',
    block: 'Block user',
    dismiss: 'Allow pattern',
    unblock: 'Unblock',
  };
  const reasonLabels: Record<ModerationReasonMode, string> = {
    warn: 'Warning message',
    block: 'Block reason (optional)',
    dismiss: 'Note (optional)',
    unblock: 'Unblock reason (optional)',
  };

  const title = titles[mode];
  const submitLabel = submitLabels[mode];
  const showDuration = mode === 'warn' || mode === 'dismiss';

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    const trimmed = reason.trim();
    if (mode === 'warn' && !trimmed) {
      setError('A warning message is required.');
      return;
    }
    setError('');
    let hours: number | undefined;
    if (showDuration && durationHours.trim()) {
      const parsed = Number(durationHours);
      if (!Number.isFinite(parsed) || parsed < 0) {
        setError('Duration must be zero or a positive number of hours.');
        return;
      }
      if (mode === 'warn' && parsed <= 0) {
        setError('Duration must be a positive number of hours.');
        return;
      }
      hours = parsed;
    }
    onSubmit(trimmed, hours);
  };

  return (
    <form
      onSubmit={handleSubmit}
      className="mt-3 space-y-3 rounded-lg border border-border bg-chrome/40 p-3"
    >
      <p className="text-sm font-semibold text-text">{title}</p>
      <div>
        <Label htmlFor={reasonId}>{reasonLabels[mode]}</Label>
        <Textarea
          id={reasonId}
          rows={3}
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          placeholder={
            mode === 'warn'
              ? 'Explain what needs to change…'
              : mode === 'dismiss'
                ? 'Optional note (e.g. low-volume vote-only account)…'
                : 'Optional note for the audit log…'
          }
          required={mode === 'warn'}
          disabled={pending}
        />
      </div>
      {showDuration ? (
        <div>
          <Label htmlFor={durationId}>
            {mode === 'dismiss'
              ? 'Hide for (hours; blank = 7 days, 0 = forever)'
              : 'Duration (hours, optional)'}
          </Label>
          <Input
            id={durationId}
            type="number"
            min={mode === 'dismiss' ? 0 : 0.1}
            step="any"
            value={durationHours}
            onChange={(e) => setDurationHours(e.target.value)}
            placeholder={
              mode === 'dismiss'
                ? 'Default 168 (7 days); 0 = never expires'
                : 'Default from server (usually 24)'
            }
            disabled={pending}
          />
        </div>
      ) : null}
      {error ? <p className="text-sm text-downvote">{error}</p> : null}
      <div className="flex flex-wrap gap-2">
        <Button type="submit" variant="primary" disabled={pending}>
          {pending ? 'Saving…' : submitLabel}
        </Button>
        <Button type="button" variant="ghost" onClick={onCancel} disabled={pending}>
          Cancel
        </Button>
      </div>
    </form>
  );
};

export default ModerationReasonForm;
