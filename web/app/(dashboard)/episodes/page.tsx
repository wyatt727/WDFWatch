/**
 * Episodes Page
 * 
 * Main page for episode management - upload new episodes and view existing ones.
 * Integrates with: EpisodeUploadCard, EpisodeList components
 */

import { Metadata } from 'next';
import { EpisodeUploadCard } from '@/components/episodes/EpisodeUploadCard';
import { EpisodeList } from '@/components/episodes/EpisodeList';
import { Separator } from '@/components/ui/separator';

export const dynamic = 'force-dynamic';

export const metadata: Metadata = {
  title: 'Episodes | WDFWatch',
  description: 'Manage podcast episodes and processing pipeline',
};

export default function EpisodesPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Episodes</h1>
        <p className="text-muted-foreground mt-2">
          Upload new podcast episodes and monitor their processing status
        </p>
      </div>
      
      <Separator />
      
      <div className="grid gap-6 lg:grid-cols-3">
        <div className="lg:col-span-1">
          <EpisodeUploadCard />
        </div>
        
        <div className="lg:col-span-2">
          <div className="space-y-4">
            <div>
              <h2 className="text-xl font-semibold">Recent Episodes</h2>
              <p className="text-sm text-muted-foreground">
                View and manage previously uploaded episodes
              </p>
            </div>
            
            <EpisodeList />
          </div>
        </div>
      </div>
    </div>
  );
}