import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { storiesApi } from '../api/stories';
import StoryCard from '../components/StoryCard';
import Header from '../components/Header';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';

const Home: React.FC = () => {
  const navigate = useNavigate();
  const { isAuthenticated } = useAuth();
  const queryClient = useQueryClient();
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [newTeaser, setNewTeaser] = useState('');
  const [newContent, setNewContent] = useState('');
  
  const { data: stories, isLoading, error } = useQuery({
    queryKey: ['stories'],
    queryFn: () => storiesApi.listRootStories(0, 50),
  });

  const createMutation = useMutation({
    mutationFn: (data: { teaser: string; content: string }) =>
      storiesApi.createRootStory(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['stories'] });
      setShowCreateForm(false);
      setNewTeaser('');
      setNewContent('');
    },
  });

  const handleStoryClick = (storyId: string) => {
    navigate(`/story/${storyId}`);
  };

  const handleCreateStory = (e: React.FormEvent) => {
    e.preventDefault();
    if (newTeaser.trim() && newContent.trim()) {
      createMutation.mutate({ teaser: newTeaser, content: newContent });
    }
  };

  if (isLoading) {
    return (
      <div className="flex justify-center items-center h-screen">
        <div className="text-xl text-gray-600">Loading stories...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex justify-center items-center h-screen">
        <div className="text-xl text-red-600">Error loading stories</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <Header />
      
      <main className="max-w-6xl mx-auto px-4 py-8">
        {isAuthenticated && (
          <div className="bg-white rounded-lg shadow-md p-6 mb-8">
            <button
              onClick={() => setShowCreateForm(!showCreateForm)}
              className="w-full px-4 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors font-semibold"
            >
              {showCreateForm ? 'Cancel' : 'Start a New Story'}
            </button>

            {showCreateForm && (
              <form onSubmit={handleCreateStory} className="mt-4 space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Teaser (max 512 characters)
                  </label>
                  <input
                    type="text"
                    value={newTeaser}
                    onChange={(e) => setNewTeaser(e.target.value)}
                    maxLength={512}
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    placeholder="Write a catchy teaser for your story..."
                    required
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Story Beginning (max 2048 characters)
                  </label>
                  <textarea
                    value={newContent}
                    onChange={(e) => setNewContent(e.target.value)}
                    maxLength={2048}
                    rows={6}
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    placeholder="Once upon a time..."
                    required
                  />
                </div>
                <button
                  type="submit"
                  disabled={createMutation.isPending}
                  className="w-full px-4 py-3 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors font-semibold disabled:opacity-50"
                >
                  {createMutation.isPending ? 'Publishing...' : 'Publish Story'}
                </button>
              </form>
            )}
          </div>
        )}

        {stories && stories.length > 0 ? (
          <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
            {stories.map((story) => (
              <StoryCard
                key={story.id}
                story={story}
                onClick={() => handleStoryClick(story.id)}
              />
            ))}
          </div>
        ) : (
          <div className="text-center py-12">
            <p className="text-xl text-gray-600">No stories yet. Be the first to create one!</p>
          </div>
        )}
      </main>
    </div>
  );
};

export default Home;
