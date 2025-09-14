'use client';

import { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import { Slider } from '@/components/ui/slider';
import { Button } from '@/components/ui/button';
import { toast } from '@/components/ui/use-toast';
import { Loader2, Save, RotateCcw, Info } from 'lucide-react';
import { Alert, AlertDescription } from '@/components/ui/alert';

interface ScoreRange {
  min: number;
  max: number;
  label: string;
}

interface ScoringConfig {
  relevancy_threshold: number;
  score_ranges: {
    high: ScoreRange;
    relevant: ScoreRange;
    maybe: ScoreRange;
    skip: ScoreRange;
  };
  priority_threshold?: number;
  review_threshold?: number;
}

export default function ScoringSettingsPage() {
  const [config, setConfig] = useState<ScoringConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    fetchConfig();
  }, []);

  const fetchConfig = async () => {
    try {
      const response = await fetch('/api/settings/scoring');
      if (!response.ok) throw new Error('Failed to fetch config');
      const data = await response.json();
      setConfig(data);
    } catch (error) {
      console.error('Error fetching scoring config:', error);
      toast({
        title: 'Error',
        description: 'Failed to load scoring configuration',
        variant: 'destructive',
      });
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    if (!config) return;

    setSaving(true);
    try {
      const response = await fetch('/api/settings/scoring', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config),
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.error || 'Failed to save');
      }

      toast({
        title: 'Success',
        description: 'Scoring configuration saved successfully',
      });
    } catch (error) {
      console.error('Error saving config:', error);
      toast({
        title: 'Error',
        description: error instanceof Error ? error.message : 'Failed to save configuration',
        variant: 'destructive',
      });
    } finally {
      setSaving(false);
    }
  };

  const handleReset = async () => {
    setSaving(true);
    try {
      const response = await fetch('/api/settings/scoring', {
        method: 'DELETE',
      });

      if (!response.ok) throw new Error('Failed to reset');

      const data = await response.json();
      setConfig(data.config);
      
      toast({
        title: 'Success',
        description: 'Scoring configuration reset to defaults',
      });
    } catch (error) {
      console.error('Error resetting config:', error);
      toast({
        title: 'Error',
        description: 'Failed to reset configuration',
        variant: 'destructive',
      });
    } finally {
      setSaving(false);
    }
  };

  const updateThreshold = (field: keyof ScoringConfig, value: number) => {
    if (!config) return;
    
    const newConfig = { ...config };
    newConfig[field] = value as any;
    
    // Update score ranges when relevancy threshold changes
    if (field === 'relevancy_threshold') {
      newConfig.score_ranges.relevant.min = value;
      newConfig.score_ranges.maybe.max = Math.max(0, value - 0.01);
    }
    
    setConfig(newConfig);
  };

  const getScoreLabel = (score: number): string => {
    if (!config) return '';
    
    for (const range of Object.values(config.score_ranges)) {
      if (score >= range.min && score <= range.max) {
        return range.label;
      }
    }
    return 'Unknown';
  };

  const getScoreColor = (score: number): string => {
    if (score >= 0.85) return 'text-green-600';
    if (score >= 0.70) return 'text-blue-600';
    if (score >= 0.30) return 'text-yellow-600';
    return 'text-red-600';
  };

  if (loading) {
    return (
      <div className="container mx-auto py-6 flex items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin" />
      </div>
    );
  }

  if (!config) {
    return (
      <div className="container mx-auto py-6">
        <Alert>
          <AlertDescription>Failed to load configuration</AlertDescription>
        </Alert>
      </div>
    );
  }

  return (
    <div className="container mx-auto py-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Scoring Configuration</h1>
          <p className="text-muted-foreground mt-2">
            Configure relevancy scoring thresholds for tweet classification
          </p>
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Relevancy Threshold</CardTitle>
          <CardDescription>
            Tweets with scores at or above this threshold are considered relevant and will be processed for responses
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="space-y-4">
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <Label>Relevancy Threshold</Label>
                <span className={`text-2xl font-bold ${getScoreColor(config.relevancy_threshold)}`}>
                  {config.relevancy_threshold.toFixed(2)}
                </span>
              </div>
              <Slider
                value={[config.relevancy_threshold]}
                onValueChange={([value]) => updateThreshold('relevancy_threshold', value)}
                min={0}
                max={1}
                step={0.05}
                className="w-full"
              />
              <p className="text-sm text-muted-foreground">
                Currently: {getScoreLabel(config.relevancy_threshold)}
              </p>
            </div>

            {config.priority_threshold !== undefined && (
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <Label>Priority Threshold</Label>
                  <span className={`text-xl font-semibold ${getScoreColor(config.priority_threshold)}`}>
                    {config.priority_threshold.toFixed(2)}
                  </span>
                </div>
                <Slider
                  value={[config.priority_threshold]}
                  onValueChange={([value]) => updateThreshold('priority_threshold', value)}
                  min={config.relevancy_threshold}
                  max={1}
                  step={0.05}
                  className="w-full"
                />
                <p className="text-sm text-muted-foreground">
                  Tweets above this score get priority processing
                </p>
              </div>
            )}

            {config.review_threshold !== undefined && (
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <Label>Manual Review Threshold</Label>
                  <span className={`text-xl font-semibold ${getScoreColor(config.review_threshold)}`}>
                    {config.review_threshold.toFixed(2)}
                  </span>
                </div>
                <Slider
                  value={[config.review_threshold]}
                  onValueChange={([value]) => updateThreshold('review_threshold', value)}
                  min={0}
                  max={config.relevancy_threshold - 0.05}
                  step={0.05}
                  className="w-full"
                />
                <p className="text-sm text-muted-foreground">
                  Tweets between this and relevancy threshold might benefit from manual review
                </p>
              </div>
            )}
          </div>

          <div className="border rounded-lg p-4 bg-muted/50">
            <h3 className="font-semibold mb-3">Score Ranges</h3>
            <div className="space-y-2 text-sm">
              {Object.entries(config.score_ranges).map(([key, range]) => (
                <div key={key} className="flex items-center justify-between">
                  <span className={getScoreColor((range.min + range.max) / 2)}>
                    {range.label}
                  </span>
                  <span className="font-mono text-muted-foreground">
                    {range.min.toFixed(2)} - {range.max.toFixed(2)}
                  </span>
                </div>
              ))}
            </div>
          </div>

          <Alert>
            <Info className="h-4 w-4" />
            <AlertDescription>
              Changes to scoring thresholds will only affect future tweet classifications. 
              Previously classified tweets will retain their original scores.
            </AlertDescription>
          </Alert>

          <div className="flex gap-2">
            <Button 
              onClick={handleSave} 
              disabled={saving}
            >
              {saving ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Saving...
                </>
              ) : (
                <>
                  <Save className="mr-2 h-4 w-4" />
                  Save Configuration
                </>
              )}
            </Button>
            <Button 
              variant="outline" 
              onClick={handleReset}
              disabled={saving}
            >
              <RotateCcw className="mr-2 h-4 w-4" />
              Reset to Defaults
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Example Scores</CardTitle>
          <CardDescription>
            See how different scores would be classified with current settings
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {[0.95, 0.85, 0.75, 0.70, 0.65, 0.50, 0.30, 0.15].map(score => (
              <div 
                key={score} 
                className="text-center p-3 border rounded-lg"
              >
                <div className={`text-2xl font-bold ${getScoreColor(score)}`}>
                  {score.toFixed(2)}
                </div>
                <div className="text-sm text-muted-foreground mt-1">
                  {getScoreLabel(score)}
                </div>
                <div className="text-xs mt-1">
                  {score >= config.relevancy_threshold ? '✓ Process' : '✗ Skip'}
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}