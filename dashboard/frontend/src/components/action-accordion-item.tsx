'use client';

import {
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '@/components/ui/accordion';
import { AccordionHeader } from '@radix-ui/react-accordion';
import { Button } from '@/components/ui/button';
import { ActionDetailsForm } from './action-details-form';
import { Trash2, Copy } from 'lucide-react';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
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
import { Action, ActionType } from '../lib/validation';
import { ActionDetails } from '../lib/validation';
import { useCallback, useState, useEffect } from 'react';
import { actionSchemas, getDefaultActionDetails } from '@/lib/validation';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"

interface ActionAccordionItemProps {
  action: Action;
  index: number;
  onActionChange: (index: number, action: Action) => void;
  onActionDelete: (index: number) => void;
  onActionDuplicate: (index: number) => void;
  onActionValidation: (index: number, isValid: boolean) => void;
}

export function ActionAccordionItem({
  action,
  index,
  onActionChange,
  onActionDelete,
  onActionDuplicate,
  onActionValidation,
}: ActionAccordionItemProps) {
  const [timeStr, setTimeStr] = useState(action.time_from_start_seconds.toString());

  useEffect(() => {
    // Sync from parent prop if it changes, ensuring we don't overwrite user input unnecessarily
    if (parseFloat(timeStr) !== action.time_from_start_seconds) {
      setTimeStr(action.time_from_start_seconds.toString());
    }
  }, [action.time_from_start_seconds, timeStr]);

  const handleValidation = useCallback((isValid: boolean) => {
    onActionValidation(index, isValid);
  }, [onActionValidation, index]);

  const handleActionTypeChange = (newType: string) => {
    const defaultDetails = getDefaultActionDetails(newType);
    onActionChange(index, { 
      ...action, 
      type: newType as ActionType, 
      details: defaultDetails 
    });
  };

  const handleTimeBlur = () => {
    const parsedTime = parseFloat(timeStr);
    if (!isNaN(parsedTime) && parsedTime >= 0) {
      onActionChange(index, { ...action, time_from_start_seconds: parsedTime });
    } else {
      // Revert to last known good value from parent state if input is invalid
      setTimeStr(action.time_from_start_seconds.toString());
    }
  };

  return (
    <AccordionItem value={`item-${index}`}>
      <AccordionHeader className="flex">
        <AccordionTrigger className="flex-1 text-left">
            <div className="flex gap-4 items-center">
              <span>Time: {action.time_from_start_seconds}s</span>
              <span>Type: {action.type}</span>
              <span>Callsign: {(action.details as { callsign?: string }).callsign || 'N/A'}</span>
            </div>
        </AccordionTrigger>
        <div className="flex items-center pr-2">
          <Button variant="ghost" size="icon" onClick={(e: React.MouseEvent) => {e.stopPropagation(); onActionDuplicate(index);}}>
            <Copy className="h-4 w-4" />
          </Button>
          <AlertDialog>
            <AlertDialogTrigger asChild>
              <Button variant="ghost" size="icon" onClick={(e: React.MouseEvent) => e.stopPropagation()}>
                <Trash2 className="h-4 w-4" />
              </Button>
            </AlertDialogTrigger>
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>Are you sure?</AlertDialogTitle>
                <AlertDialogDescription>
                  This action will be permanently deleted.
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel>Cancel</AlertDialogCancel>
                <AlertDialogAction onClick={() => onActionDelete(index)}>
                  Delete
                </AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
        </div>
      </AccordionHeader>
      <AccordionContent>
        <div className="p-4 space-y-4">
            <div className="space-y-2">
                <Label>Action Type</Label>
                <Select value={action.type} onValueChange={handleActionTypeChange}>
                  <SelectTrigger>
                    <SelectValue placeholder="Select an action type" />
                  </SelectTrigger>
                  <SelectContent>
                    {Object.keys(actionSchemas).map(type => (
                      <SelectItem key={type} value={type}>{type}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
            </div>
            <div className="space-y-2">
              <Label>Time From Start (seconds)</Label>
              <Input
                type="text"
                value={timeStr}
                onChange={(e) => setTimeStr(e.target.value)}
                onBlur={handleTimeBlur}
              />
            </div>
          <ActionDetailsForm
            actionType={action.type}
            details={action.details}
            onChange={(details: Record<string, unknown>) => onActionChange(index, { ...action, details: details as ActionDetails })}
            onValidation={handleValidation}
          />
        </div>
      </AccordionContent>
    </AccordionItem>
  );
} 