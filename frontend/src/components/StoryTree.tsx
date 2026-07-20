import type { FC } from 'react';
import { useNavigate } from 'react-router-dom';
import type { StoryPartTree } from '../api/stories';

interface StoryTreeProps {
  tree: StoryPartTree;
  currentStoryId?: string;
}

const StoryTreeNode: FC<{
  node: StoryPartTree;
  currentStoryId?: string;
  depth: number;
}> = ({ node, currentStoryId, depth }) => {
  const navigate = useNavigate();
  const isCurrent = node.id === currentStoryId;

  return (
    <li className="list-none">
      <button
        type="button"
        onClick={() => navigate(`/story/${node.id}`)}
        className={`w-full text-left px-3 py-2 rounded-md transition-colors ${
          isCurrent
            ? 'bg-blue-100 text-blue-900 font-semibold'
            : 'hover:bg-gray-100 text-gray-800'
        }`}
        style={{ paddingLeft: `${depth * 12 + 12}px` }}
      >
        <span className="block truncate">{node.teaser}</span>
        <span className="text-xs text-gray-500">
          {node.author_username || 'Unknown'} · {node.vote_score} votes ·{' '}
          {node.children_count} branches
        </span>
      </button>
      {node.children.length > 0 && (
        <ul className="mt-1 space-y-1">
          {node.children.map((child) => (
            <StoryTreeNode
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

const StoryTree: FC<StoryTreeProps> = ({ tree, currentStoryId }) => {
  return (
    <nav aria-label="Story branch tree" className="bg-white rounded-lg shadow-md p-6">
      <h2 className="text-xl font-bold text-gray-900 mb-4">Story tree</h2>
      <ul className="space-y-1">
        <StoryTreeNode node={tree} currentStoryId={currentStoryId} depth={0} />
      </ul>
    </nav>
  );
};

export default StoryTree;
