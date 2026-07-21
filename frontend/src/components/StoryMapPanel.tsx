import type { FC } from 'react';
import { useNavigate } from 'react-router-dom';
import type { StoryPartTree } from '../api/stories';

interface StoryMapPanelProps {
  tree: StoryPartTree;
  currentStoryId?: string;
  className?: string;
}

const StoryMapNode: FC<{
  node: StoryPartTree;
  currentStoryId?: string;
  depth: number;
}> = ({ node, currentStoryId, depth }) => {
  const navigate = useNavigate();
  const isCurrent = node.id === currentStoryId;
  const indent = depth * 12 + 8;

  return (
    <li className="list-none">
      <button
        type="button"
        onClick={() => navigate(`/story/${node.id}`)}
        className={`w-full text-left py-1.5 pr-2 rounded transition-colors text-sm ${
          isCurrent
            ? 'text-accent font-semibold bg-accent-soft/50'
            : 'text-text hover:bg-chrome/80'
        }`}
        style={{ paddingLeft: `${indent}px` }}
      >
        <span className="text-muted mr-1">{depth > 0 ? '—' : '▼'}</span>
        <span className="truncate">{isCurrent ? '● ' : '○ '}{node.teaser}</span>
      </button>
      {node.children.length > 0 && (
        <ul>
          {node.children.map((child) => (
            <StoryMapNode
              key={child.id}
              node={child}
              currentStoryId={currentStoryId}
              depth={depth + 1}
            />
          ))}
        </ul>
      )}
    </li>
  );
};

/** Persistent left sidebar story tree (Wireframe C). */
const StoryMapPanel: FC<StoryMapPanelProps> = ({ tree, currentStoryId, className = '' }) => (
  <nav
    aria-label="Story map"
    className={`bg-chrome border border-border rounded-lg p-4 ${className}`}
  >
    <h2 className="text-xs font-semibold uppercase tracking-wide text-muted mb-3">
      Story map
    </h2>
    <ul>
      <StoryMapNode node={tree} currentStoryId={currentStoryId} depth={0} />
    </ul>
  </nav>
);

export default StoryMapPanel;
