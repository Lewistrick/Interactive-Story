import { useId, useState, type FC, type FormEvent } from 'react';
import Button from './ui/Button';
import Input from './ui/Input';
import Label from './ui/Label';
import Textarea from './ui/Textarea';

export type ModerationReasonMode = 'warn' | 'block';

interface ModerationReasonFormProps {
  mode: ModerationReasonMode;
  pending?: boolean;
  /** Called with trimmed reason; duration only for warn (hours, or undefined for server default). */
  onSubmit: (reason: string, durationHours?: number) => void;
  onCancel: () => void;
}

/**
 * Inline warn/block reason form (replaces ``window.prompt``).
 *
 * Warn requires a message; block reason is optional. Uses Archive Parchment inputs.
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

  const isWarn = mode === 'warn';
  const title = isWarn ? 'Warn user' : 'Block user';
  const submitLabel = isWarn ? 'Send warning' : 'Block user';

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    const trimmed = reason.trim();
    if (isWarn && !trimmed) {
      setError('A warning message is required.');
      return;
    }
    setError('');
    let hours: number | undefined;
    if (isWarn && durationHours.trim()) {
      const parsed = Number(durationHours);
      if (!Number.isFinite(parsed) || parsed <= 0) {
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
        <Label htmlFor={reasonId}>
          {isWarn ? 'Warning message' : 'Block reason (optional)'}
        </Label>
        <Textarea
          id={reasonId}
          rows={3}
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          placeholder={isWarn ? 'Explain what needs to change…' : 'Optional note for the audit log…'}
          required={isWarn}
          disabled={pending}
        />
      </div>
      {isWarn ? (
        <div>
          <Label htmlFor={durationId}>Duration (hours, optional)</Label>
          <Input
            id={durationId}
            type="number"
            min={0.1}
            step="any"
            value={durationHours}
            onChange={(e) => setDurationHours(e.target.value)}
            placeholder="Default from server (usually 24)"
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
