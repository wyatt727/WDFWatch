/**
 * Episode List Component
 * 
 * Displays a list of podcast episodes with their processing status.
 * Integrates with: /api/episodes, SSE events for real-time updates
 */

"use client"

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { useToast } from '@/components/ui/use-toast';
import { 
  CalendarDays, 
  Hash, 
  MessageSquare, 
  BarChart3, 
  PlayCircle,
  RefreshCw,
  CheckCircle2,
  XCircle,
  Clock,
  Trash2
} from 'lucide-react';
import { formatDistanceToNow } from 'date-fns';
import Link from 'next/link';

interface Episode {
  id: string;
  title: string;
  videoUrl: string;
  transcriptLength: number;
  keywordCount: number;
  tweetCount: number;
  draftCount: number;
  postedCount: number;
  processingStatus: 'pending' | 'processing' | 'completed' | 'failed';
  createdAt: string;
  updatedAt: string;
}

interface EpisodeListProps {
  episodes?: Episode[];
}

function getStatusIcon(status: string) {
  switch (status) {
    case 'completed':
      return <CheckCircle2 className="h-4 w-4 text-green-600" />;
    case 'processing':
      return <RefreshCw className="h-4 w-4 text-blue-600 animate-spin" />;
    case 'failed':
      return <XCircle className="h-4 w-4 text-red-600" />;
    default:
      return <Clock className="h-4 w-4 text-gray-600" />;
  }
}

function getStatusVariant(status: string): 'default' | 'secondary' | 'destructive' | 'outline' {
  switch (status) {
    case 'completed':
      return 'default';
    case 'processing':
      return 'secondary';
    case 'failed':
      return 'destructive';
    default:
      return 'outline';
  }
}

export function EpisodeList({ episodes: providedEpisodes }: EpisodeListProps) {
  const [deleteEpisodeId, setDeleteEpisodeId] = useState<string | null>(null);
  const [episodeToDelete, setEpisodeToDelete] = useState<Episode | null>(null);
  const queryClient = useQueryClient();
  const { toast } = useToast();

  const { data: episodes, isLoading } = useQuery<Episode[]>({
    queryKey: ['episodes'],
    queryFn: async () => {
      const response = await fetch('/api/episodes');
      if (!response.ok) throw new Error('Failed to fetch episodes');
      return response.json();
    },
    initialData: providedEpisodes,
    refetchInterval: 5000, // Refetch every 5 seconds for status updates
  });

  const deleteMutation = useMutation({
    mutationFn: async (episodeId: string) => {
      const response = await fetch(`/api/episodes/${episodeId}`, {
        method: 'DELETE',
      });
      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.error || 'Failed to delete episode');
      }
      return response.json();
    },
    onSuccess: (data, episodeId) => {
      queryClient.invalidateQueries({ queryKey: ['episodes'] });
      toast({
        title: 'Episode deleted',
        description: `Episode "${episodeToDelete?.title}" has been deleted successfully.`,
      });
      setDeleteEpisodeId(null);
      setEpisodeToDelete(null);
    },
    onError: (error: Error) => {
      toast({
        title: 'Delete failed',
        description: error.message || 'Failed to delete episode',
        variant: 'destructive',
      });
    },
  });

  const handleDeleteClick = (episode: Episode) => {
    setEpisodeToDelete(episode);
    setDeleteEpisodeId(episode.id);
  };

  const handleDeleteConfirm = () => {
    if (deleteEpisodeId) {
      deleteMutation.mutate(deleteEpisodeId);
    }
  };

  if (isLoading) {
    return (
      <div className="space-y-4">
        {[1, 2, 3].map((i) => (
          <Card key={i}>
            <CardHeader>
              <Skeleton className="h-6 w-3/4" />
              <Skeleton className="h-4 w-1/2" />
            </CardHeader>
            <CardContent>
              <Skeleton className="h-16 w-full" />
            </CardContent>
          </Card>
        ))}
      </div>
    );
  }

  if (!episodes || episodes.length === 0) {
    return (
      <Card>
        <CardContent className="text-center py-8">
          <p className="text-muted-foreground">No episodes uploaded yet</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      {episodes.map((episode) => (
        <Card key={episode.id} className="hover:shadow-lg transition-shadow">
          <CardHeader>
            <div className="flex items-start justify-between">
              <div className="space-y-1 flex-1">
                <CardTitle className="text-lg">{episode.title}</CardTitle>
                <div className="flex items-center gap-4 text-sm text-muted-foreground">
                  <span className="flex items-center gap-1">
                    <CalendarDays className="h-3 w-3" />
                    {formatDistanceToNow(new Date(episode.createdAt), { addSuffix: true })}
                  </span>
                  <Badge variant={getStatusVariant(episode.processingStatus)}>
                    {getStatusIcon(episode.processingStatus)}
                    <span className="ml-1">{episode.processingStatus}</span>
                  </Badge>
                </div>
              </div>
              <div className="flex gap-2">
                {episode.videoUrl && (
                  <Button variant="outline" size="sm" asChild>
                    <Link href={episode.videoUrl} target="_blank" rel="noopener noreferrer">
                      <PlayCircle className="h-4 w-4 mr-1" />
                      Watch
                    </Link>
                  </Button>
                )}
                <Button variant="outline" size="sm" asChild>
                  <Link href={`/episodes/${episode.id}`}>
                    <BarChart3 className="h-4 w-4 mr-1" />
                    Details
                  </Link>
                </Button>
                <Button 
                  variant="outline" 
                  size="sm" 
                  onClick={() => handleDeleteClick(episode)}
                  disabled={episode.processingStatus === 'processing'}
                >
                  <Trash2 className="h-4 w-4 mr-1" />
                  Delete
                </Button>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
              <div>
                <p className="text-muted-foreground">Keywords</p>
                <p className="font-medium flex items-center gap-1">
                  <Hash className="h-3 w-3" />
                  {episode.keywordCount}
                </p>
              </div>
              <div>
                <p className="text-muted-foreground">Tweets Found</p>
                <p className="font-medium flex items-center gap-1">
                  <MessageSquare className="h-3 w-3" />
                  {episode.tweetCount}
                </p>
              </div>
              <div>
                <p className="text-muted-foreground">Drafts Created</p>
                <p className="font-medium flex items-center gap-1">
                  <MessageSquare className="h-3 w-3" />
                  {episode.draftCount}
                </p>
              </div>
              <div>
                <p className="text-muted-foreground">Posted</p>
                <p className="font-medium flex items-center gap-1">
                  <CheckCircle2 className="h-3 w-3" />
                  {episode.postedCount}
                </p>
              </div>
            </div>
            
            {episode.processingStatus === 'processing' && (
              <div className="mt-4">
                <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2">
                  <div 
                    className="bg-blue-600 h-2 rounded-full animate-pulse" 
                    style={{ width: '60%' }}
                  />
                </div>
                <p className="text-xs text-muted-foreground mt-1">
                  Processing pipeline...
                </p>
              </div>
            )}
          </CardContent>
        </Card>
      ))}
      
      <AlertDialog open={!!deleteEpisodeId} onOpenChange={(open) => {
        if (!open) {
          setDeleteEpisodeId(null);
          setEpisodeToDelete(null);
        }
      }}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Episode</AlertDialogTitle>
            <AlertDialogDescription className="space-y-2">
              <p>
                Are you sure you want to delete &quot;{episodeToDelete?.title}&quot;?
              </p>
              <p>
                This action cannot be undone. This will permanently delete:
              </p>
              <ul className="list-disc list-inside text-sm space-y-1 ml-2">
                <li>{episodeToDelete?.tweetCount || 0} tweets</li>
                <li>{episodeToDelete?.draftCount || 0} draft responses</li>
                <li>{episodeToDelete?.keywordCount || 0} keywords</li>
                <li>All pipeline run history</li>
                <li>The episode transcript and summary</li>
              </ul>
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDeleteConfirm}
              disabled={deleteMutation.isPending}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {deleteMutation.isPending ? (
                <>
                  <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
                  Deleting...
                </>
              ) : (
                'Delete Episode'
              )}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}