import { useEffect, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { RefreshCw } from 'lucide-react';
import { fetchLatestWorkflowRun, fetchWorkflowJobs, fetchJobLogs } from '../lib/github';

export default function LogsViewer({ token }: { token: string }) {
  const [logs, setLogs] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadLogs = async () => {
    if (!token) {
      setError('Please configure your GitHub PAT in Settings first.');
      return;
    }
    
    setLoading(true);
    setError(null);
    try {
      const run = await fetchLatestWorkflowRun(token);
      if (!run) throw new Error('No workflow runs found');
      
      const jobs = await fetchWorkflowJobs(run.id, token);
      const scraperJob = jobs.find((j: any) => j.name === 'scraper');
      if (!scraperJob) throw new Error('Scraper job not found');
      
      const rawLogs = await fetchJobLogs(scraperJob.id, token);
      
      // Parse the logs for the "Run scrapers" phase
      // GitHub groups logs with ##[group]...
      const lines = rawLogs.split('\n');
      let isInPhase = false;
      const filteredLogs = [];
      
      for (const line of lines) {
        if (line.includes('##[group]Run Run scrapers')) {
          isInPhase = true;
          continue;
        }
        if (isInPhase && line.includes('##[endgroup]')) {
          break;
        }
        // Also break if a new group starts, just in case
        if (isInPhase && line.includes('##[group]') && !line.includes('Run scrapers')) {
          break;
        }
        if (isInPhase) {
          // Remove the ISO timestamp prefix (e.g. "2024-10-03T16:44:55.1234567Z ")
          const cleanLine = line.replace(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+Z /, '');
          filteredLogs.push(cleanLine);
        }
      }
      
      if (filteredLogs.length === 0) {
        setLogs('No logs found for "Run scrapers" phase. Raw logs might have a different format.');
      } else {
        setLogs(filteredLogs.join('\n'));
      }
      
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadLogs();
  }, [token]);

  return (
    <Card className="w-full">
      <CardHeader className="flex flex-row items-center justify-between">
        <div>
          <CardTitle>Scraper Execution Logs</CardTitle>
          <CardDescription>Latest "Run scrapers" phase logs from GitHub Actions</CardDescription>
        </div>
        <Button variant="outline" size="sm" onClick={loadLogs} disabled={loading || !token}>
          <RefreshCw className={`w-4 h-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
          Refresh
        </Button>
      </CardHeader>
      <CardContent>
        {error ? (
          <div className="text-red-500 text-sm">{error}</div>
        ) : (
          <div className="bg-slate-950 text-slate-50 p-4 rounded-md overflow-x-auto h-[500px] overflow-y-auto font-mono text-sm whitespace-pre">
            {loading && !logs ? 'Loading logs...' : (logs || 'No logs to display')}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
