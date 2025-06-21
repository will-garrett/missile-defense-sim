'use client';

import { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import Link from 'next/link';
import { Plus } from 'lucide-react';

type ScenarioAction = Record<string, unknown>;

export default function ScenariosPage() {
  const [scenarios, setScenarios] = useState<Record<string, ScenarioAction[]>>({});

  useEffect(() => {
    async function fetchScenarios() {
      try {
        const response = await fetch('/api/scenarios');
        if (!response.ok) {
          throw new Error('Failed to fetch scenarios');
        }
        const data = await response.json();
        setScenarios(data.scenarios);
      } catch (error) {
        console.error(error);
      }
    }
    fetchScenarios();
  }, []);

  return (
    <div className="container mx-auto py-10">
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>Scenarios</CardTitle>
              <CardDescription>
                Manage and create simulation scenarios.
              </CardDescription>
            </div>
            <Link href="/scenarios/create">
              <Button className="flex items-center gap-2">
                <Plus className="h-4 w-4" />
                Create Scenario
              </Button>
            </Link>
          </div>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Scenario Name</TableHead>
                <TableHead>Actions Count</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {Object.keys(scenarios).map((scenarioName) => (
                <TableRow key={scenarioName}>
                  <TableCell className="font-medium">{scenarioName}</TableCell>
                  <TableCell>{scenarios[scenarioName].length}</TableCell>
                  <TableCell className="text-right">
                    <Link href={`/scenarios/${encodeURIComponent(scenarioName)}`}>
                      <Button variant="outline" size="sm">
                        View & Edit
                      </Button>
                    </Link>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
} 