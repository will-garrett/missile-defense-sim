'use client';

import { ChangeEvent, useState, useEffect } from 'react';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { actionSchemas } from '@/lib/validation';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"

interface PlatformType {
  nickname: string;
  category: string;
}

interface ActionDetailsFormProps {
  actionType: string;
  details: Record<string, unknown>;
  onChange: (details: Record<string, unknown>) => void;
  // Passing a function to report validation status to parent
  onValidation: (isValid: boolean) => void;
}

export function ActionDetailsForm({ actionType, details, onChange, onValidation }: ActionDetailsFormProps) {
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [platformTypes, setPlatformTypes] = useState<PlatformType[]>([]);
  const [localDetails, setLocalDetails] = useState(details);

  const detailsString = JSON.stringify(details);
  useEffect(() => {
    // Sync local state when the details prop changes from the parent
    // This happens when the action type changes and we reset the form
    setLocalDetails(details);
  }, [detailsString]);

  // Fetch platform types when the component mounts or actionType changes
  useEffect(() => {
    async function fetchPlatformTypes() {
      // Determine category based on actionType
      let category = '';
      switch (actionType) {
        case 'deploy_radar':
        case 'vector_radar':
          category = 'detection_system';
          break;
        case 'deploy_defense_battery':
        case 'vector_defense_battery':
          category = 'counter_defense';
          break;
        case 'deploy_launcher':
        case 'launch_missile':
          category = 'launch_platform';
          break;
      }
      
      if (!category) {
        setPlatformTypes([]);
        return;
      }

      try {
        const response = await fetch(`/api/platform-types?category=${category}`);
        if (!response.ok) throw new Error('Failed to fetch platform types');
        const data = await response.json();
        setPlatformTypes(data.platform_types || []);
      } catch (error) {
        console.error(error);
        setPlatformTypes([]);
      }
    }
    fetchPlatformTypes();
  }, [actionType]);

  useEffect(() => {
    const schema = actionSchemas[actionType as keyof typeof actionSchemas];
    if (schema) {
      const result = schema.safeParse(details);
      const newErrors: Record<string, string> = {};
      if (!result.success) {
        result.error.issues.forEach((issue: { path: (string | number)[]; message: string }) => {
          newErrors[issue.path.join('.')] = issue.message;
        });
      }
      setErrors(newErrors);
      onValidation(result.success);
    }
  }, [details, actionType, onValidation]);

  const handleLocalChange = (fieldPath: string, value: string | number) => {
    setLocalDetails(prev => ({ ...prev, [fieldPath]: value }));
  };
  
  const handleNestedLocalChange = (parentField: string, childField: string, value: string | number) => {
    setLocalDetails(prev => {
      const parentObject = (prev[parentField] as Record<string, unknown>) || {};
      return {
        ...prev,
        [parentField]: {
          ...parentObject,
          [childField]: value,
        },
      };
    });
  };

  const handleBlur = (fieldPath: string, isNumber: boolean) => {
    if (!isNumber) return;

    const value = localDetails[fieldPath];
    if (typeof value === 'string') {
      const parsed = parseFloat(value);
      if (!isNaN(parsed)) {
        onChange({ ...details, [fieldPath]: parsed });
      } else {
        // Revert if invalid
        setLocalDetails(details);
      }
    }
  };
  
  const handleNestedBlur = (parentField: string, childField: string, isNumber: boolean) => {
    if (!isNumber) return;

    const parentObject = localDetails[parentField] as Record<string, unknown> | undefined;
    const value = parentObject?.[childField];

    if (typeof value === 'string') {
      const parsed = parseFloat(value);
      if (!isNaN(parsed)) {
        const originalParent = (details[parentField] as Record<string, unknown>) || {};
        onChange({
          ...details,
          [parentField]: {
            ...originalParent,
            [childField]: parsed
          }
        });
      } else {
         // Revert if invalid
        setLocalDetails(details);
      }
    }
  };

  const renderInputField = (
    label: string,
    field: string,
    isNested = false,
    parentField = '',
    isNumber = false
  ) => {
    const errorKey = isNested ? `${parentField}.${field}` : field;
    const value = isNested
      ? ((localDetails[parentField] as Record<string, unknown>)?.[field] as string | number) || ''
      : (localDetails[field] as string | number) || '';

    return (
      <div className="space-y-2">
        <Label>{label}</Label>
        <Input
          type="text"
          value={value}
          onChange={(e: ChangeEvent<HTMLInputElement>) => {
            const val = e.target.value;
            if (isNested) {
              handleNestedLocalChange(parentField, field, val);
            } else {
              handleLocalChange(field, val);
            }
          }}
          onBlur={() => {
            if (isNested) {
              handleNestedBlur(parentField, field, isNumber);
            } else {
              handleBlur(field, isNumber);
            }
          }}
          className={errors[errorKey] ? 'border-red-500' : ''}
        />
        {errors[errorKey] && <p className="text-sm text-red-500">{errors[errorKey]}</p>}
      </div>
    );
  };

  const renderPlatformTypeDropdown = () => {
    return (
      <div className="space-y-2">
        <Label>Platform Type</Label>
        <Select
          value={localDetails.nickname as string || ''}
          onValueChange={(value) => handleLocalChange('nickname', value)}
        >
          <SelectTrigger className={errors['nickname'] ? 'border-red-500' : ''}>
            <SelectValue placeholder="Select a platform" />
          </SelectTrigger>
          <SelectContent>
            {platformTypes.map(pt => (
              <SelectItem key={pt.nickname} value={pt.nickname}>{pt.nickname}</SelectItem>
            ))}
          </SelectContent>
        </Select>
        {errors['nickname'] && <p className="text-sm text-red-500">{errors['nickname']}</p>}
      </div>
    );
  };

  switch (actionType) {
    case 'deploy_launcher':
    case 'deploy_defense_battery':
    case 'deploy_radar':
      return (
        <div className="grid grid-cols-2 gap-4">
          {renderPlatformTypeDropdown()}
          {renderInputField('Callsign', 'callsign')}
          {renderInputField('Latitude', 'lat', false, '', true)}
          {renderInputField('Longitude', 'lon', false, '', true)}
          {renderInputField('Altitude', 'alt', false, '', true)}
        </div>
      );
    case 'vector_defense_battery':
    case 'vector_radar':
        return (
            <div className="grid grid-cols-2 gap-4">
              {renderInputField('Callsign', 'callsign')}
              <div />
              {renderInputField('Target Latitude', 'lat', true, 'target_pos', true)}
              {renderInputField('Target Longitude', 'lon', true, 'target_pos', true)}
              {renderInputField('Target Altitude', 'alt', true, 'target_pos', true)}
            </div>
          );
    case 'launch_missile':
      return (
        <div className="grid grid-cols-2 gap-4">
          {renderPlatformTypeDropdown()}
          {renderInputField('Missile Callsign', 'callsign')}
          {renderInputField('Launcher Callsign', 'launcher_callsign')}
          <div />
          {renderInputField('Target Latitude', 'target_lat', false, '', true)}
          {renderInputField('Target Longitude', 'target_lon', false, '', true)}
          {renderInputField('Target Altitude', 'target_alt', false, '', true)}
        </div>
      );
    default:
      return (
        <p className="text-sm text-muted-foreground">
          Select an action type to see its form fields.
        </p>
      );
  }
} 