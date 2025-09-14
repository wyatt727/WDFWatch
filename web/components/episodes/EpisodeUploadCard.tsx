'use client';

/**
 * Episode Upload Card Component
 * 
 * Allows users to upload new podcast episodes by providing transcript and metadata.
 * Integrates with: /api/episodes, Python pipeline
 */

import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Loader2, Upload, CheckCircle } from 'lucide-react';
import { useToast } from '@/components/ui/use-toast';

export function EpisodeUploadCard() {
  const [title, setTitle] = useState('');
  const [transcriptFile, setTranscriptFile] = useState<File | null>(null);
  const [videoUrl, setVideoUrl] = useState('');
  const [isUploading, setIsUploading] = useState(false);
  const [uploadSuccess, setUploadSuccess] = useState(false);
  const { toast } = useToast();

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    
    if (!file) {
      setTranscriptFile(null);
      return;
    }
    
    // Check file type
    if (file.type !== 'text/plain') {
      toast({
        title: 'Invalid file type',
        description: 'Please upload a .txt file',
        variant: 'destructive',
      });
      e.target.value = ''; // Clear the input
      return;
    }
    
    // Check file size (50MB limit)
    const maxFileSize = 50 * 1024 * 1024; // 50MB
    if (file.size > maxFileSize) {
      toast({
        title: 'File too large',
        description: `File size must be less than ${maxFileSize / (1024 * 1024)}MB. Your file is ${(file.size / (1024 * 1024)).toFixed(1)}MB.`,
        variant: 'destructive',
      });
      e.target.value = ''; // Clear the input
      return;
    }
    
    // Show size warning for large files
    if (file.size > 5 * 1024 * 1024) { // 5MB
      toast({
        title: 'Large file detected',
        description: `Uploading ${(file.size / (1024 * 1024)).toFixed(1)}MB file. This may take a moment.`,
        variant: 'default',
      });
    }
    
    setTranscriptFile(file);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!title || !transcriptFile || !videoUrl) {
      toast({
        title: 'Missing fields',
        description: 'Please fill in all required fields',
        variant: 'destructive',
      });
      return;
    }

    // Validate video URL format
    const isValidUrl = /^https?:\/\/.+/.test(videoUrl);
    const isWdfShow = /^@wdf_show$/i.test(videoUrl);
    
    if (!isValidUrl && !isWdfShow) {
      toast({
        title: 'Invalid URL format',
        description: 'Please enter a valid URL or @WDF_Show',
        variant: 'destructive',
      });
      return;
    }

    // Normalize @WDF_Show to consistent format
    const normalizedVideoUrl = isWdfShow ? '@WDF_Show' : videoUrl;

    setIsUploading(true);
    setUploadSuccess(false);

    try {
      // Create FormData for multipart upload
      const formData = new FormData();
      formData.append('title', title);
      formData.append('videoUrl', normalizedVideoUrl);
      formData.append('transcript', transcriptFile);

      // Create episode with file upload
      const response = await fetch('/api/episodes', {
        method: 'POST',
        body: formData, // No Content-Type header - browser will set it with boundary
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.error || `Upload failed with status ${response.status}`);
      }

      const episode = await response.json();

      setUploadSuccess(true);
      toast({
        title: 'Episode uploaded successfully',
        description: `${(transcriptFile.size / (1024 * 1024)).toFixed(1)}MB transcript uploaded. You can now process it from the episode details page.`,
      });

      // Reset form
      setTimeout(() => {
        setTitle('');
        setTranscriptFile(null);
        setVideoUrl('');
        setUploadSuccess(false);
        // Clear file input
        const fileInput = document.getElementById('transcript') as HTMLInputElement;
        if (fileInput) fileInput.value = '';
      }, 3000);
    } catch (error) {
      console.error('Upload error:', error);
      toast({
        title: 'Upload failed',
        description: error instanceof Error ? error.message : 'Unknown error',
        variant: 'destructive',
      });
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Upload New Episode</CardTitle>
        <CardDescription>
          Upload a podcast transcript to start the tweet discovery pipeline
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="title">Episode Title</Label>
            <Input
              id="title"
              placeholder="Episode 42: The Future of Federalism"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              disabled={isUploading}
              required
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="transcript">Transcript File (.txt)</Label>
            <Input
              id="transcript"
              type="file"
              accept=".txt"
              onChange={handleFileChange}
              disabled={isUploading}
              required
            />
            {transcriptFile && (
              <div className="text-sm text-muted-foreground space-y-1">
                <p>Selected: {transcriptFile.name}</p>
                <p>Size: {(transcriptFile.size / (1024 * 1024)).toFixed(1)}MB</p>
                {transcriptFile.size > 5 * 1024 * 1024 && (
                  <p className="text-amber-600 dark:text-amber-400">
                    ⚠️ Large file - upload may take longer
                  </p>
                )}
              </div>
            )}
          </div>

          <div className="space-y-2">
            <Label htmlFor="videoUrl">Video URL or @WDF_Show</Label>
            <Input
              id="videoUrl"
              type="text"
              placeholder="https://youtube.com/watch?v=... or @WDF_Show"
              value={videoUrl}
              onChange={(e) => setVideoUrl(e.target.value)}
              disabled={isUploading}
              required
              pattern="^(https?:\/\/.+|@[Ww][Dd][Ff]_[Ss][Hh][Oo][Ww])$"
              title="Please enter a valid URL or @WDF_Show"
            />
            <p className="text-xs text-muted-foreground">
              Enter a YouTube URL for specific episode or @WDF_Show to reference the podcast X page
            </p>
          </div>

          {uploadSuccess && (
            <Alert className="bg-green-50 dark:bg-green-950 border-green-200 dark:border-green-800">
              <CheckCircle className="h-4 w-4 text-green-600 dark:text-green-400" />
              <AlertDescription className="text-green-800 dark:text-green-200">
                Episode uploaded successfully! You can now process it from the episode details page.
              </AlertDescription>
            </Alert>
          )}

          <Button
            type="submit"
            disabled={isUploading || !title || !transcriptFile || !videoUrl}
            className="w-full"
          >
            {isUploading ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                {transcriptFile && transcriptFile.size > 5 * 1024 * 1024 
                  ? `Uploading ${(transcriptFile.size / (1024 * 1024)).toFixed(1)}MB...` 
                  : 'Uploading...'
                }
              </>
            ) : (
              <>
                <Upload className="mr-2 h-4 w-4" />
                Upload Episode
              </>
            )}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}