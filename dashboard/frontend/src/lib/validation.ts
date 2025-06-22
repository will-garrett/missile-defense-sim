import { z } from 'zod';

export enum ActionType {
  DEPLOY_LAUNCHER = 'deploy_launcher',
  DEPLOY_DEFENSE_BATTERY = 'deploy_defense_battery',
  DEPLOY_RADAR = 'deploy_radar',
  ARM_LAUNCHER = 'arm_launcher',
  ARM_BATTERY = 'arm_battery',
  LAUNCH_MISSILE = 'launch_missile',
}

// Base schema for deploying any platform
const deployDetailsSchema = z.object({
  platform_nickname: z.string().min(1, 'Platform type is required.'),
  callsign: z.string().min(1, 'Callsign is required.'),
  lat: z.number().min(-90, 'Must be >= -90').max(90, 'Must be <= 90'),
  lon: z.number().min(-180, 'Must be >= -180').max(180, 'Must be <= 180'),
  alt: z.number(),
});

// Schema for arming a launcher or battery
const armSchema = z.object({
  launcher_callsign: z.string().min(1, 'Launcher callsign is required.'),
  munition_nickname: z.string().min(1, 'Munition type is required.'),
  quantity: z.number().min(1, 'Quantity must be at least 1'),
});

// Schema for launching an attack missile
const missileLaunchDetailsSchema = z.object({
  launcher_callsign: z.string().min(1, 'Launcher callsign is required.'),
  munition_nickname: z.string().min(1, 'Munition type is required.'),
  target_lat: z.number().min(-90, 'Must be >= -90').max(90, 'Must be <= 90'),
  target_lon: z.number().min(-180, 'Must be >= -180').max(180, 'Must be <= 180'),
  target_alt: z.number(),
});

export type DeployDetails = z.infer<typeof deployDetailsSchema>;
export type ArmDetails = z.infer<typeof armSchema>;
export type MissileLaunchDetails = z.infer<typeof missileLaunchDetailsSchema>;

export type ActionDetails = DeployDetails | ArmDetails | MissileLaunchDetails;

export const actionSchemas = {
  [ActionType.DEPLOY_LAUNCHER]: deployDetailsSchema,
  [ActionType.DEPLOY_DEFENSE_BATTERY]: deployDetailsSchema,
  [ActionType.DEPLOY_RADAR]: deployDetailsSchema,
  [ActionType.ARM_LAUNCHER]: armSchema,
  [ActionType.ARM_BATTERY]: armSchema,
  [ActionType.LAUNCH_MISSILE]: missileLaunchDetailsSchema,
};

export const actionSchema = z.object({
  type: z.nativeEnum(ActionType),
  details: z.any(),
  time_from_start_seconds: z.number().min(0),
  scenario_name: z.string(),
}).refine(data => {
  const schema = actionSchemas[data.type as keyof typeof actionSchemas];
  if (!schema) return false;
  return schema.safeParse(data.details).success;
}, {
  message: 'Invalid details for action type',
  path: ['details'],
});

export type Action = z.infer<typeof actionSchema>;

export function getDefaultActionDetails(actionType: string): ActionDetails {
  switch (actionType) {
    case ActionType.DEPLOY_LAUNCHER:
    case ActionType.DEPLOY_DEFENSE_BATTERY:
    case ActionType.DEPLOY_RADAR:
      return { platform_nickname: '', callsign: '', lat: 0, lon: 0, alt: 0 };
    case ActionType.ARM_LAUNCHER:
    case ActionType.ARM_BATTERY:
      return { launcher_callsign: '', munition_nickname: '', quantity: 1 };
    case ActionType.LAUNCH_MISSILE:
      return { launcher_callsign: '', munition_nickname: '', target_lat: 0, target_lon: 0, target_alt: 0 };
    default:
      return {} as ActionDetails;
  }
} 