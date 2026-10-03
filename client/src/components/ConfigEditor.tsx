import { useState, useEffect } from 'react';
import { fetchFileContent, commitFile } from '../lib/github';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { useToast } from '@/hooks/use-toast';

export default function ConfigEditor({ token }: { token: string }) {
  const { toast } = useToast();
  const [configStr, setConfigStr] = useState('');
  const [sha, setSha] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    async function load() {
      try {
        setLoading(true);
        const { content, sha } = await fetchFileContent('config.json', token);
        setConfigStr(content);
        setSha(sha);
      } catch (err: any) {
        toast({ title: 'Error loading config', description: err.message, variant: 'destructive' });
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [token]);

  const handleSave = async () => {
    if (!token) {
      toast({ title: 'Missing Token', description: 'Please enter a GitHub Personal Access Token in the Settings tab.', variant: 'destructive' });
      return;
    }
    try {
      // Validate JSON
      JSON.parse(configStr);
    } catch (e) {
      toast({ title: 'Invalid JSON', description: 'Please fix syntax errors before saving.', variant: 'destructive' });
      return;
    }

    try {
      setSaving(true);
      const res = await commitFile('config.json', configStr, sha, 'Update config via UI', token);
      setSha(res.content.sha); // update sha for subsequent saves
      toast({ title: 'Success', description: 'Configuration successfully saved to main branch.' });
    } catch (err: any) {
      toast({ title: 'Failed to save', description: err.message, variant: 'destructive' });
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <div className="p-8 text-center text-slate-500">Loading config.json from GitHub...</div>;

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>config.json</CardTitle>
          <CardDescription>Edit the configuration file below. Must be valid JSON.</CardDescription>
        </CardHeader>
        <CardContent>
          <textarea 
            className="w-full h-[400px] font-mono text-sm p-4 border rounded-md bg-slate-50 focus:outline-none focus:ring-2 focus:ring-slate-900"
            value={configStr}
            onChange={(e) => setConfigStr(e.target.value)}
          />
          <div className="mt-4 flex justify-end">
            <Button onClick={handleSave} disabled={saving}>
              {saving ? 'Committing to GitHub...' : 'Save Changes'}
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
