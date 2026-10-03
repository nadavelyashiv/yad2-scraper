import { useState, useEffect } from 'react';
import { fetchGitTree, fetchFileContent } from '../lib/github';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';


interface FileData {
  name: string;
  items: [string, any][];
}

export default function DataViewer({ token }: { token: string }) {
  const [data, setData] = useState<FileData[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function loadData() {
      try {
        setLoading(true);
        const treeData = await fetchGitTree(token);
        const jsonFiles = treeData.tree.filter((f: any) => f.path.startsWith('data/') && f.path.endsWith('.json'));
        
        const loadedData = [];
        for (const file of jsonFiles) {
          const fileRes = await fetchFileContent(file.path, token);
          const parsed = JSON.parse(fileRes.content);
          loadedData.push({
            name: file.path.replace('data/', '').replace('.json', ''),
            items: Object.entries(parsed) as any,
          });
        }
        setData(loadedData);
      } catch (err: any) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, [token]);

  if (loading) return <div className="p-8 text-center text-slate-500">Loading data from GitHub...</div>;
  if (error) return <div className="p-8 text-center text-red-500">Error: {error}</div>;

  return (
    <div className="space-y-8">
      {data.map((fileData) => (
        <Card key={fileData.name}>
          <CardHeader>
            <CardTitle className="text-xl capitalize">{decodeURIComponent(fileData.name)}</CardTitle>
          </CardHeader>
          <CardContent>
            {fileData.items.length === 0 ? (
              <p className="text-slate-500 italic">No items found.</p>
            ) : (
              <div className="rounded-md border">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Address</TableHead>
                      <TableHead>Rooms</TableHead>
                      <TableHead>Floor</TableHead>
                      <TableHead>Area</TableHead>
                      <TableHead>Price</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {fileData.items.map(([id, apt]) => {
                      const isDict = typeof apt === 'object' && apt !== null;
                      return (
                        <TableRow key={id}>
                          <TableCell className="font-medium">{isDict ? (apt.address || '-') : apt}</TableCell>
                          <TableCell>{isDict ? (apt.rooms || '-') : '-'}</TableCell>
                          <TableCell>{isDict ? (apt.floor || '-') : '-'}</TableCell>
                          <TableCell>{isDict && apt.area ? `${apt.area} m²` : '-'}</TableCell>
                          <TableCell>{isDict ? (apt.price || '-') : '-'}</TableCell>
                        </TableRow>
                      );
                    })}
                  </TableBody>
                </Table>
              </div>
            )}
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
