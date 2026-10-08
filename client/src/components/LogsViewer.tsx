import { useEffect, useState, useRef } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { RefreshCw, Activity } from 'lucide-react';
import { fetchLatestWorkflowRun, fetchWorkflowJobs, fetchJobLogs } from '../lib/github';

export default function LogsViewer({ token }: { token: string }) {
  const [logs, setLogs] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isLive, setIsLive] = useState(false);
  const logsEndRef = useRef<HTMLDivElement>(null);

  const loadLogs = async (isAutoRefresh = false) => {
    if (!token) {
      setError('Please configure your GitHub PAT in Settings first.');
      return;
    }
    
    if (!isAutoRefresh) setLoading(true);
    setError(null);
    try {
      const run = await fetchLatestWorkflowRun(token);
      if (!run) throw new Error('No workflow runs found');
      
      const active = run.status === 'in_progress' || run.status === 'queued';
      setIsLive(active);
      
      const jobs = await fetchWorkflowJobs(run.id, token);
      const scraperJob = jobs.find((j: any) => j.name === 'scraper');
      if (!scraperJob) throw new Error('Scraper job not found');
      
      const rawLogs = await fetchJobLogs(scraperJob.id, token);
      
      // Parse the logs for the "Run scrapers" phase
      const lines = rawLogs.split('\n');
      let isInPhase = false;
      const filteredLogs = [];
      
      for (const line of lines) {
        if (line.includes('##[group]Run Run scrapers') || line.includes('##[group]Run export API_TOKEN=')) {
          isInPhase = true;
          continue;
        }
        if (isInPhase && line.includes('##[endgroup]')) {
          break;
        }
        if (isInPhase && line.includes('##[group]') && !line.includes('Run scrapers')) {
          break;
        }
        if (isInPhase) {
          const cleanLine = line.replace(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+Z /, '');
          filteredLogs.push(cleanLine);
        }
      }
      
      if (filteredLogs.length === 0) {
        setLogs(active ? 'Waiting for "Run scrapers" phase to start...' : 'No logs found for "Run scrapers" phase.');
      } else {
        setLogs(filteredLogs.join('\n'));
      }
      
    } catch (err: any) {
      // If job logs aren't available yet (e.g. queued), just ignore if auto-refreshing
      if (!isAutoRefresh) setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadLogs();
  }, [token]);

  useEffect(() => {
    let intervalId: any;
    if (isLive && token) {
      intervalId = setInterval(() => {
        loadLogs(true);
      }, 5000);
    }
    return () => {
      if (intervalId) clearInterval(intervalId);
    };
  }, [isLive, token]);

  useEffect(() => {
    if (logsEndRef.current) {
      logsEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [logs]);

  return (
    <Card className="w-full">
      <CardHeader className="flex flex-row items-center justify-between">
        <div>
          <CardTitle className="flex items-center gap-2">
            Scraper Execution Logs
            {isLive && (
              <span className="flex items-center text-xs font-medium text-emerald-600 bg-emerald-100 px-2 py-1 rounded-full animate-pulse">
                <Activity className="w-3 h-3 mr-1" />
                Live
              </span>
            )}
          </CardTitle>
          <CardDescription>Latest "Run scrapers" phase logs from GitHub Actions</CardDescription>
        </div>
        <Button variant="outline" size="sm" onClick={() => loadLogs()} disabled={loading || !token}>
          <RefreshCw className={`w-4 h-4 mr-2 ${loading && !isLive ? 'animate-spin' : ''}`} />
          Refresh
        </Button>
      </CardHeader>
      <CardContent>
        {error ? (
          <div className="text-red-500 text-sm">{error}</div>
        ) : (
          <div className="bg-slate-950 text-slate-50 p-4 rounded-md h-[500px] overflow-y-auto font-mono text-sm whitespace-pre">
            {loading && !logs && !isLive ? 'Loading logs...' : (logs || 'No logs to display')}
            <div ref={logsEndRef} />
          </div>
        )}
      </CardContent>
    </Card>
  );
}
