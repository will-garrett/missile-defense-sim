'use client';

import { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from '@/components/ui/command';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { ChevronsUpDown, Plus } from 'lucide-react';

interface ScenarioComboboxProps {
  value: string;
  onChange: (value: string) => void;
}

export function ScenarioCombobox({ value, onChange }: ScenarioComboboxProps) {
  const [open, setOpen] = useState(false);
  const [scenarios, setScenarios] = useState<string[]>([]);
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [newScenarioName, setNewScenarioName] = useState('');

  useEffect(() => {
    async function fetchScenarioNames() {
      try {
        const response = await fetch('/api/scenarios');
        const data = await response.json();
        // Assuming the API returns a structure like { scenarios: { "name1": [...], "name2": [...] } }
        setScenarios(Object.keys(data.scenarios));
      } catch (error) {
        console.error('Failed to fetch scenarios:', error);
      }
    }
    fetchScenarioNames();
  }, []);

  const handleCreateScenario = () => {
    if (newScenarioName.trim()) {
      onChange(newScenarioName.trim());
      setNewScenarioName('');
      setCreateDialogOpen(false);
      setOpen(false);
    }
  };

  return (
    <>
      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger asChild>
          <Button
            variant="outline"
            role="combobox"
            aria-expanded={open}
            className="w-full justify-between"
          >
            {value || 'Select scenario...'}
            <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
          </Button>
        </PopoverTrigger>
        <PopoverContent className="w-[--radix-popover-trigger-width] p-0">
          <Command>
            <CommandInput placeholder="Search scenario..." />
            <CommandList>
              <CommandEmpty>No scenario found.</CommandEmpty>
              <CommandGroup>
                {scenarios.map((scenario) => (
                  <CommandItem
                    key={scenario}
                    value={scenario}
                    onSelect={(currentValue: string) => {
                      onChange(currentValue === value ? '' : currentValue);
                      setOpen(false);
                    }}
                  >
                    {scenario}
                  </CommandItem>
                ))}
                <Dialog open={createDialogOpen} onOpenChange={setCreateDialogOpen}>
                  <DialogTrigger asChild>
                    <CommandItem
                      value="__create_new__"
                      onSelect={() => setCreateDialogOpen(true)}
                      className="text-blue-600"
                    >
                      <Plus className="mr-2 h-4 w-4" />
                      Create new scenario...
                    </CommandItem>
                  </DialogTrigger>
                  <DialogContent>
                    <DialogHeader>
                      <DialogTitle>Create New Scenario</DialogTitle>
                      <DialogDescription>
                        Enter a name for the new scenario.
                      </DialogDescription>
                    </DialogHeader>
                    <div className="grid gap-4 py-4">
                      <div className="space-y-2">
                        <Label htmlFor="scenario-name">Scenario Name</Label>
                        <Input
                          id="scenario-name"
                          value={newScenarioName}
                          onChange={(e: React.ChangeEvent<HTMLInputElement>) => setNewScenarioName(e.target.value)}
                          placeholder="Enter scenario name..."
                          onKeyDown={(e: React.KeyboardEvent<HTMLInputElement>) => {
                            if (e.key === 'Enter') {
                              handleCreateScenario();
                            }
                          }}
                        />
                      </div>
                    </div>
                    <DialogFooter>
                      <Button variant="outline" onClick={() => setCreateDialogOpen(false)}>
                        Cancel
                      </Button>
                      <Button onClick={handleCreateScenario} disabled={!newScenarioName.trim()}>
                        Create
                      </Button>
                    </DialogFooter>
                  </DialogContent>
                </Dialog>
              </CommandGroup>
            </CommandList>
          </Command>
        </PopoverContent>
      </Popover>
    </>
  );
} 