import { z } from 'zod';

export enum ActionType {
  DEPLOY_LAUNCHER = 'deploy_launcher',
  DEPLOY_DEFENSE_BATTERY = 'deploy_defense_battery',
  DEPLOY_RADAR = 'deploy_radar',
  LAUNCH_MISSILE = 'launch_missile',
  VECTOR_DEFENSE_BATTERY = 'vector_defense_battery',
  VECTOR_RADAR = 'vector_radar',
}

const positionSchema = z.object({
  lat: z.number().min(-90, 'Must be >= -90').max(90, 'Must be <= 90'),
  lon: z.number().min(-180, 'Must be >= -180').max(180, 'Must be <= 180'),
  alt: z.number(),
});

const launcherDetailsSchema = z.object({
  nickname: z.string().min(1, 'Nickname is required.'),
  callsign: z.string().min(1, 'Callsign is required.'),
  lat: z.number().min(-90, 'Must be >= -90').max(90, 'Must be <= 90'),
  lon: z.number().min(-180, 'Must be >= -180').max(180, 'Must be <= 180'),
  alt: z.number(),
});

const radarDetailsSchema = z.object({
  nickname: z.string().min(1, 'Nickname is required.'),
  callsign: z.string().min(1, 'Callsign is required.'),
  lat: z.number().min(-90, 'Must be >= -90').max(90, 'Must be <= 90'),
  lon: z.number().min(-180, 'Must be >= -180').max(180, 'Must be <= 180'),
  alt: z.number(),
});

const missileLaunchDetailsSchema = z.object({
  nickname: z.string().min(1, 'Nickname is required.'),
  callsign: z.string().min(1, 'Callsign is required.'),
  launcher_callsign: z.string().min(1, 'Launcher callsign is required.'),
  target_lat: z.number().min(-90, 'Must be >= -90').max(90, 'Must be <= 90'),
  target_lon: z.number().min(-180, 'Must be >= -180').max(180, 'Must be <= 180'),
  target_alt: z.number(),
});

const vectorDetailsSchema = z.object({
  callsign: z.string().min(1, 'Callsign is required.'),
  target_pos: positionSchema,
});

export type LauncherDetails = z.infer<typeof launcherDetailsSchema>;
export type RadarDetails = z.infer<typeof radarDetailsSchema>;
export type MissileLaunchDetails = z.infer<typeof missileLaunchDetailsSchema>;
export type VectorDetails = z.infer<typeof vectorDetailsSchema>;

export type ActionDetails = LauncherDetails | RadarDetails | MissileLaunchDetails | VectorDetails;

export const actionSchemas = {
  [ActionType.DEPLOY_LAUNCHER]: launcherDetailsSchema,
  [ActionType.DEPLOY_DEFENSE_BATTERY]: launcherDetailsSchema,
  [ActionType.DEPLOY_RADAR]: radarDetailsSchema,
  [ActionType.LAUNCH_MISSILE]: missileLaunchDetailsSchema,
  [ActionType.VECTOR_DEFENSE_BATTERY]: vectorDetailsSchema,
  [ActionType.VECTOR_RADAR]: vectorDetailsSchema,
};

export const actionSchema = z.object({
  type: z.nativeEnum(ActionType),
  details: z.any(),
  time_from_start_seconds: z.number().min(0),
  scenario_name: z.string(),
}).refine(data => {
  const schema = actionSchemas[data.type];
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
      return { nickname: '', callsign: '', lat: 0, lon: 0, alt: 0 };
    case ActionType.VECTOR_DEFENSE_BATTERY:
    case ActionType.VECTOR_RADAR:
      return { callsign: '', target_pos: { lat: 0, lon: 0, alt: 0 } };
    case ActionType.LAUNCH_MISSILE:
      return { nickname: '', callsign: '', launcher_callsign: '', target_lat: 0, target_lon: 0, target_alt: 0 };
    default:
      // This case should ideally not be reached if the UI is correct
      return {} as ActionDetails;
  }
} 