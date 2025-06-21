'use client';

import { useState, ChangeEvent, useEffect, useCallback } from 'react';
import { Button } from '@/components/ui/button';
import { Pencil, X, ArrowLeft } from 'lucide-react';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '@/components/ui/alert-dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Accordion } from '@/components/ui/accordion';
import { ActionAccordionItem } from './action-accordion-item';
import { Action, ActionType } from '../lib/validation';
import { useRouter } from 'next/navigation';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';

interface ScenarioFormProps {
  initialScenarioName?: string;
  initialActions?: Action[];
  isEditing?: boolean;
}

export function ScenarioForm({ 
  initialScenarioName = 'New Scenario', 
  initialActions = [], 
  isEditing = false 
}: ScenarioFormProps) {
  const router = useRouter();
  const [scenarioName, setScenarioName] = useState(initialScenarioName);
  const [isEditingName, setIsEditingName] = useState(false);
  const [tempScenarioName, setTempScenarioName] = useState('');
  const [actions, setActions] = useState<Action[]>(initialActions);
  const [confirmDeleteText, setConfirmDeleteText] = useState('');
  const [actionValidation, setActionValidation] = useState<Record<number, boolean>>({});

  // Update actions when initialActions prop changes (for editing mode)
  useEffect(() => {
    if (initialActions.length > 0) {
      setActions(initialActions);
    }
  }, [initialActions]);

  const handleAddAction = () => {
    const newAction: Action = {
      type: ActionType.DEPLOY_LAUNCHER,
      details: {
        nickname: '',
        callsign: '',
        lat: 0,
        lon: 0,
        alt: 0,
      },
      time_from_start_seconds: 0,
      scenario_name: scenarioName,
    };
    setActions([...actions, newAction]);
  };

  const handleActionChange = useCallback((index: number, updatedAction: Action) => {
    setActions(prevActions => {
      const newActions = [...prevActions];
      newActions[index] = updatedAction;
      return newActions;
    });
  }, []);

  const handleActionDelete = (index: number) => {
    const newActions = actions.filter((_, i) => i !== index);
    setActions(newActions);
    const newValidation = { ...actionValidation };
    delete newValidation[index];
    setActionValidation(newValidation);
  };

  const handleActionDuplicate = (index: number) => {
    const actionToDuplicate = actions[index];
    const duplicatedAction = { ...actionToDuplicate };
    const newActions = [...actions];
    newActions.splice(index + 1, 0, duplicatedAction);
    setActions(newActions);
  };

  const handleActionValidation = useCallback((index: number, isValid: boolean) => {
    setActionValidation((prev) => {
      if (prev[index] === isValid) return prev;
      return { ...prev, [index]: isValid };
    });
  }, []);

  const isFormFullyValid = () => {
    if (actions.length === 0) return false;
    for (let i = 0; i < actions.length; i++) {
      if (!actionValidation[i]) {
        return false;
      }
    }
    return true;
  };

  const handleDeleteScenario = async () => {
    if (scenarioName !== confirmDeleteText) {
      console.error("Confirmation text does not match scenario name.");
      return;
    }

    try {
      const response = await fetch(`/api/scenarios/${scenarioName}`, {
        method: 'DELETE',
      });

      if (!response.ok) {
        throw new Error('Failed to delete scenario');
      }

      console.log('Scenario deleted successfully');
      router.push('/scenarios');
    } catch (error) {
      console.error(error);
    }
  };

  const handleRename = () => {
    setScenarioName(tempScenarioName);
    setIsEditingName(false);
    setActions(actions.map(action => ({...action, scenario_name: tempScenarioName})));
  };

  const startEditingName = () => {
    setTempScenarioName(scenarioName);
    setIsEditingName(true);
  };

  const cancelEditingName = () => {
    setIsEditingName(false);
  };

  const handleSubmit = async () => {
    const payload = {
      actions: actions,
    };

    try {
      const response = await fetch(`/api/scenarios/${scenarioName}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        throw new Error('Failed to save scenario');
      }

      console.log('Scenario saved successfully');
      router.push('/scenarios');
    } catch (error) {
      console.error(error);
    }
  };

  return (
    <div className="container mx-auto py-10">
      <Card>
        <CardHeader>
          <div className="flex items-center gap-4">
            <Button 
              variant="ghost" 
              size="sm" 
              onClick={() => router.push('/scenarios')}
              className="flex items-center gap-2"
            >
              <ArrowLeft className="h-4 w-4" />
              Back to Scenarios
            </Button>
            <div className="flex items-center gap-2">
              {isEditingName ? (
                <>
                  <Input
                    value={tempScenarioName}
                    onChange={(e: ChangeEvent<HTMLInputElement>) => setTempScenarioName(e.target.value)}
                    className="text-lg font-semibold"
                  />
                  <Button onClick={handleRename} size="sm">Rename</Button>
                  <Button onClick={cancelEditingName} size="icon" variant="ghost">
                    <X className="h-4 w-4" />
                  </Button>
                </>
              ) : (
                <>
                  <CardTitle>{scenarioName}</CardTitle>
                  <Button onClick={startEditingName} size="icon" variant="ghost">
                    <Pencil className="h-4 w-4" />
                  </Button>
                </>
              )}
            </div>
          </div>
          <CardDescription>
            {isEditing ? 'Edit simulation scenario by modifying actions and timing.' : 'Build a new simulation scenario by adding a name and a sequence of actions.'}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <Label>Actions</Label>
            <Accordion type="multiple" className="w-full">
              {actions
                .slice()
                .sort((a, b) => a.time_from_start_seconds - b.time_from_start_seconds)
                .map((action, index) => (
                  <ActionAccordionItem
                    key={index}
                    index={index}
                    action={action}
                    onActionChange={handleActionChange}
                    onActionDelete={handleActionDelete}
                    onActionDuplicate={handleActionDuplicate}
                    onActionValidation={handleActionValidation}
                  />
                ))}
            </Accordion>
            <Button variant="outline" onClick={handleAddAction}>
              Add Action
            </Button>
          </div>
          
          <div className="flex justify-between mt-8">
            {isEditing && (
              <AlertDialog>
                <AlertDialogTrigger asChild>
                  <Button variant="destructive">Delete Scenario</Button>
                </AlertDialogTrigger>
                <AlertDialogContent>
                  <AlertDialogHeader>
                    <AlertDialogTitle>Are you absolutely sure?</AlertDialogTitle>
                    <AlertDialogDescription>
                      This action cannot be undone. This will permanently delete the
                      <strong>{scenarioName}</strong> scenario. Please type the scenario name to confirm.
                    </AlertDialogDescription>
                  </AlertDialogHeader>
                  <Input
                    value={confirmDeleteText}
                    onChange={(e: ChangeEvent<HTMLInputElement>) => setConfirmDeleteText(e.target.value)}
                    placeholder={scenarioName}
                  />
                  <AlertDialogFooter>
                    <AlertDialogCancel>Cancel</AlertDialogCancel>
                    <AlertDialogAction
                      disabled={scenarioName !== confirmDeleteText}
                      onClick={handleDeleteScenario}
                    >
                      Delete
                    </AlertDialogAction>
                  </AlertDialogFooter>
                </AlertDialogContent>
              </AlertDialog>
            )}
            <Button type="submit" onClick={handleSubmit} disabled={!isFormFullyValid()}>
              {isEditing ? 'Update Scenario' : 'Create Scenario'}
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
} 