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

interface MunitionType {
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
  const [munitionTypes, setMunitionTypes] = useState<MunitionType[]>([]);
  const [localDetails, setLocalDetails] = useState(details);

  useEffect(() => {
    setLocalDetails(details);
  }, [details]);

  // Fetch platform types when the component mounts or actionType changes
  useEffect(() => {
    async function fetchPlatformTypes() {
      let category = '';
      if (actionType === 'deploy_launcher') category = 'launch_platform';
      else if (actionType === 'deploy_defense_battery') category = 'counter_defense';
      else if (actionType === 'deploy_radar') category = 'detection_system';
      
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

  // Fetch munition types based on action
  useEffect(() => {
    async function fetchMunitionTypes() {
      let category = '';
      if (actionType === 'arm_launcher' || actionType === 'launch_missile') category = 'attack';
      else if (actionType === 'arm_battery') category = 'defense';

      if (!category) {
        setMunitionTypes([]);
        return;
      }
      try {
        const response = await fetch(`/api/munition-types?category=${category}`);
        if (!response.ok) throw new Error('Failed to fetch munition types');
        const data = await response.json();
        setMunitionTypes(data.munition_types || []);
      } catch (error) {
        console.error(error);
        setMunitionTypes([]);
      }
    }
    fetchMunitionTypes();
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
      const newParent = {
        ...parentObject,
        [childField]: value,
      };
      return {
        ...prev,
        [parentField]: newParent,
      };
    });
  };

  const handleBlur = (fieldPath: string, isNumber: boolean) => {
    if (isNumber) {
      const value = localDetails[fieldPath];
      if (typeof value === 'string') {
        const parsed = parseFloat(value);
        if (!isNaN(parsed)) {
          onChange({ ...localDetails, [fieldPath]: parsed });
        } else {
          // Revert if invalid by syncing with parent state
          setLocalDetails(details);
        }
      } else {
        // If it's already a number or something else, just make sure parent is up-to-date
        onChange(localDetails);
      }
    } else {
      // For string fields, propagate changes on blur
      onChange(localDetails);
    }
  };
  
  const handleNestedBlur = (parentField: string, childField: string, isNumber: boolean) => {
    const parentObject = localDetails[parentField] as Record<string, unknown> | undefined;
    if (!parentObject) return;

    const value = parentObject[childField];

    if (isNumber) {
      if (typeof value === 'string') {
        const parsed = parseFloat(value);
        if (!isNaN(parsed)) {
          const newParent = { ...parentObject, [childField]: parsed };
          onChange({ ...localDetails, [parentField]: newParent });
        } else {
          setLocalDetails(details); // Revert
        }
      } else {
        onChange(localDetails);
      }
    } else {
      // For string fields, propagate changes on blur
      onChange(localDetails);
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
          value={localDetails.platform_nickname as string || ''}
          onValueChange={(value) => {
            const newDetails = { ...localDetails, platform_nickname: value };
            setLocalDetails(newDetails);
            onChange(newDetails);
          }}
        >
          <SelectTrigger className={errors['platform_nickname'] ? 'border-red-500' : ''}>
            <SelectValue placeholder="Select a platform" />
          </SelectTrigger>
          <SelectContent>
            {platformTypes.map(pt => (
              <SelectItem key={pt.nickname} value={pt.nickname}>{pt.nickname}</SelectItem>
            ))}
          </SelectContent>
        </Select>
        {errors['platform_nickname'] && <p className="text-sm text-red-500">{errors['platform_nickname']}</p>}
      </div>
    );
  };

  const renderMunitionTypeDropdown = () => {
    return (
      <div className="space-y-2">
        <Label>Munition Type</Label>
        <Select
          value={localDetails.munition_nickname as string || ''}
          onValueChange={(value) => {
            const newDetails = { ...localDetails, munition_nickname: value };
            setLocalDetails(newDetails);
            onChange(newDetails);
          }}
        >
          <SelectTrigger className={errors['munition_nickname'] ? 'border-red-500' : ''}>
            <SelectValue placeholder="Select a munition" />
          </SelectTrigger>
          <SelectContent>
            {munitionTypes.map(mt => (
              <SelectItem key={mt.nickname} value={mt.nickname}>{mt.nickname}</SelectItem>
            ))}
          </SelectContent>
        </Select>
        {errors['munition_nickname'] && <p className="text-sm text-red-500">{errors['munition_nickname']}</p>}
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
    case 'arm_launcher':
    case 'arm_battery':
        return (
            <div className="grid grid-cols-2 gap-4">
              {renderInputField('Launcher Callsign', 'launcher_callsign')}
              {renderMunitionTypeDropdown()}
              {renderInputField('Quantity', 'quantity', false, '', true)}
            </div>
          );
    case 'launch_missile':
      return (
        <div className="grid grid-cols-2 gap-4">
          {renderInputField('Launcher Callsign', 'launcher_callsign')}
          {renderMunitionTypeDropdown()}
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