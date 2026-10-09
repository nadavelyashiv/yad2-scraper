import { useEffect, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { RefreshCw, ExternalLink, Activity } from 'lucide-react';
import { fetchLatestWorkflowRun } from '../lib/github';

export default function LogsViewer({ token }: { token: string }) {
  const [run, setRun] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadRun = async () => {
    if (!token) {
      setError('Please configure your GitHub PAT in Settings first.');
      return;
    }
    
    setLoading(true);
    setError(null);
    try {
      const latestRun = await fetchLatestWorkflowRun(token);
      if (!latestRun) throw new Error('No workflow runs found');
      setRun(latestRun);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadRun();
  }, [token]);

  return (
    <Card className="w-full">
      <CardHeader className="flex flex-row items-center justify-between">
        <div>
          <CardTitle className="flex items-center gap-2">
            GitHub Actions Logs
            {run && (run.status === 'in_progress' || run.status === 'queued') && (
              <span className="flex items-center text-xs font-medium text-emerald-600 bg-emerald-100 px-2 py-1 rounded-full animate-pulse">
                <Activity className="w-3 h-3 mr-1" />
                Live
              </span>
            )}
          </CardTitle>
          <CardDescription>View the execution logs directly on GitHub</CardDescription>
        </div>
        <Button variant="outline" size="sm" onClick={() => loadRun()} disabled={loading || !token}>
          <RefreshCw className={`w-4 h-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
          Refresh
        </Button>
      </CardHeader>
      <CardContent>
        {error ? (
          <div className="text-red-500 text-sm">{error}</div>
        ) : run ? (
          <div className="flex flex-col items-center justify-center p-12 bg-slate-50 border border-slate-200 rounded-lg text-center">
            <h3 className="text-lg font-semibold mb-2 text-slate-700">Latest Run: {run.name || 'Yad2 Scraper'}</h3>
            <p className="text-sm text-slate-500 mb-6">
              Status: <span className="font-medium text-slate-700">{run.status}</span>
              {run.conclusion && ` • Conclusion: ${run.conclusion}`}
            </p>
            <Button asChild>
              <a href={run.html_url} target="_blank" rel="noopener noreferrer">
                <ExternalLink className="w-4 h-4 mr-2" />
                Open Logs in GitHub
              </a>
            </Button>
          </div>
        ) : (
          <div className="p-8 text-center text-slate-500">Loading latest workflow run...</div>
        )}
      </CardContent>
    </Card>
  );
}
