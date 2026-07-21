import type { FC, FormEvent } from 'react';
import Button from './ui/Button';
import Input from './ui/Input';
import Textarea from './ui/Textarea';
import Label from './ui/Label';
import Panel from './ui/Panel';

interface CreateStoryFormProps {
  teaser: string;
  content: string;
  onTeaserChange: (value: string) => void;
  onContentChange: (value: string) => void;
  onSubmit: (e: FormEvent) => void;
  onCancel: () => void;
  isPending: boolean;
  submitLabel: string;
  teaserLabel?: string;
  contentLabel?: string;
  contentPlaceholder?: string;
  maxTeaserLength?: number;
  maxContentLength?: number;
}

interface CharCountProps {
  used: number;
  max: number;
}

/** Shows used / max characters; turns downvote-red when over the limit. */
const CharCount: FC<CharCountProps> = ({ used, max }) => {
  const over = used > max;
  return (
    <p
      className={`mt-1 text-sm tabular-nums text-right ${
        over ? 'text-downvote' : 'text-muted'
      }`}
      aria-live="polite"
    >
      {used} / {max}
      {over ? ' — too long for your tier' : ''}
    </p>
  );
};

/** Reusable story/continuation create form. */
const CreateStoryForm: FC<CreateStoryFormProps> = ({
  teaser,
  content,
  onTeaserChange,
  onContentChange,
  onSubmit,
  onCancel,
  isPending,
  submitLabel,
  teaserLabel = 'Teaser',
  contentLabel = 'Story content',
  contentPlaceholder = 'Once upon a time...',
  maxTeaserLength = 512,
  maxContentLength = 2048,
}) => {
  const teaserOver = teaser.length > maxTeaserLength;
  const contentOver = content.length > maxContentLength;
  const canSubmit =
    teaser.trim().length > 0 &&
    content.trim().length > 0 &&
    !teaserOver &&
    !contentOver &&
    !isPending;

  return (
    <Panel className="p-6">
      <form onSubmit={onSubmit} className="space-y-4">
        <div>
          <Label htmlFor="teaser">{teaserLabel}</Label>
          <Input
            id="teaser"
            type="text"
            value={teaser}
            onChange={(e) => onTeaserChange(e.target.value)}
            placeholder="Write a catchy teaser..."
            required
            aria-invalid={teaserOver}
            className={teaserOver ? 'border-downvote focus:border-downvote focus:ring-downvote/40' : ''}
          />
          <CharCount used={teaser.length} max={maxTeaserLength} />
        </div>
        <div>
          <Label htmlFor="content">{contentLabel}</Label>
          <Textarea
            id="content"
            value={content}
            onChange={(e) => onContentChange(e.target.value)}
            rows={6}
            placeholder={contentPlaceholder}
            required
            aria-invalid={contentOver}
            className={contentOver ? 'border-downvote focus:border-downvote focus:ring-downvote/40' : ''}
          />
          <CharCount used={content.length} max={maxContentLength} />
        </div>
        <div className="flex gap-3">
          <Button type="submit" variant="primary" disabled={!canSubmit} className="flex-1">
            {isPending ? 'Publishing...' : submitLabel}
          </Button>
          <Button type="button" variant="secondary" onClick={onCancel}>
            Cancel
          </Button>
        </div>
      </form>
    </Panel>
  );
};

export default CreateStoryForm;
