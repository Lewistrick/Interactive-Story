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
  teaserLabel,
  contentLabel,
  contentPlaceholder = 'Once upon a time...',
  maxTeaserLength = 512,
  maxContentLength = 2048,
}) => {
  const resolvedTeaserLabel = teaserLabel ?? `Teaser (max ${maxTeaserLength} characters)`;
  const resolvedContentLabel = contentLabel ?? `Story content (max ${maxContentLength} characters)`;

  return (
    <Panel className="p-6">
      <form onSubmit={onSubmit} className="space-y-4">
        <div>
          <Label htmlFor="teaser">{resolvedTeaserLabel}</Label>
          <Input
            id="teaser"
            type="text"
            value={teaser}
            onChange={(e) => onTeaserChange(e.target.value)}
            maxLength={maxTeaserLength}
            placeholder="Write a catchy teaser..."
            required
          />
        </div>
        <div>
          <Label htmlFor="content">{resolvedContentLabel}</Label>
          <Textarea
            id="content"
            value={content}
            onChange={(e) => onContentChange(e.target.value)}
            maxLength={maxContentLength}
            rows={6}
            placeholder={contentPlaceholder}
            required
          />
        </div>
        <div className="flex gap-3">
          <Button type="submit" variant="primary" disabled={isPending} className="flex-1">
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
