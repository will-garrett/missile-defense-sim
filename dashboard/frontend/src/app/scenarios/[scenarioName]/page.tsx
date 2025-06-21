'use client';

import { useState, useEffect } from 'react';
import { useParams } from 'next/navigation';
import { ScenarioForm } from '@/components/scenario-form';
import { Action } from '@/lib/validation';

export default function EditScenarioPage() {
  const params = useParams<{ scenarioName: string }>();
  const scenarioName = params.scenarioName;

  const [scenario, setScenario] = useState<{ actions: Action[] } | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!scenarioName) return;

    async function fetchScenario() {
      try {
        const response = await fetch(`/api/scenarios/${encodeURIComponent(scenarioName)}`);
        if (!response.ok) {
          throw new Error('Failed to fetch scenario');
        }
        const data = await response.json();
        setScenario(data);
      } catch (error) {
        console.error(error);
        setError('Failed to load scenario');
      } finally {
        setLoading(false);
      }
    }

    fetchScenario();
  }, [scenarioName]);

  if (loading) {
    return (
      <div className="container mx-auto py-10">
        <div className="text-center">Loading scenario...</div>
      </div>
    );
  }

  if (error || !scenario) {
    return (
      <div className="container mx-auto py-10">
        <div className="text-center text-red-600">
          {error || 'Scenario not found'}
        </div>
      </div>
    );
  }

  return (
    <ScenarioForm
      initialScenarioName={decodeURIComponent(scenarioName)}
      initialActions={scenario.actions}
      isEditing={true}
    />
  );
} 