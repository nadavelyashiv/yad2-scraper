import { useState } from 'react';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { useToast } from '@/hooks/use-toast';
import DataViewer from './components/DataViewer';
import ConfigEditor from './components/ConfigEditor';

function App() {
  const { toast } = useToast();
  const [token, setToken] = useState(() => localStorage.getItem('github_pat') || '');
  const [draftToken, setDraftToken] = useState(token);

  const saveToken = () => {
    localStorage.setItem('github_pat', draftToken);
    setToken(draftToken);
    toast({ title: 'Token Saved', description: 'GitHub PAT has been saved to local storage.' });
  };

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 font-sans p-8">
      <div className="max-w-6xl mx-auto space-y-6">
        <h1 className="text-3xl font-bold tracking-tight">Yad2 Scraper Dashboard</h1>
        
        <Tabs defaultValue="data" className="w-full">
          <TabsList className="mb-4">
            <TabsTrigger value="data">Data Viewer</TabsTrigger>
            <TabsTrigger value="config">Configuration</TabsTrigger>
            <TabsTrigger value="settings">Settings</TabsTrigger>
          </TabsList>
          
          <TabsContent value="data">
            <DataViewer token={token} />
          </TabsContent>
          
          <TabsContent value="config">
            <ConfigEditor token={token} />
          </TabsContent>

          <TabsContent value="settings">
            <Card>
              <CardHeader>
                <CardTitle>Authentication Settings</CardTitle>
                <CardDescription>
                  Enter a GitHub Personal Access Token (PAT) with `repo` scope to commit changes and avoid rate limits.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="global-pat">GitHub PAT</Label>
                  <Input 
                    id="global-pat" 
                    type="password" 
                    value={draftToken} 
                    onChange={(e: React.ChangeEvent<HTMLInputElement>) => setDraftToken(e.target.value)} 
                    placeholder="ghp_xxxxxxxxxxxxxxxxxxxx" 
                  />
                </div>
                <Button onClick={saveToken}>Save Token</Button>
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
}

export default App;
