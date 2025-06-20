"""
Messaging and database handler for Battery Simulation Service
Handles NATS, DB, and engagement order subscription
"""
import os
import json
import asyncpg
import nats
from nats.aio.client import Client as NATS
from typing import Optional, Callable
from battery_logic import EngagementOrder, BatteryCapability

class BatteryMessagingService:
    def __init__(self, callsign: str, db_pool: asyncpg.Pool, nats_client: NATS):
        self.callsign = callsign
        self.db_pool = db_pool
        self.nats_client = nats_client

    async def load_battery_capabilities(self) -> (BatteryCapability, int):
        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT pt.max_range_m, pt.max_altitude_m, pt.accuracy_percent,
                       pt.reload_time_sec, pt.max_speed_mps, pt.blast_radius_m,
                       i.ammo_count
                FROM installation i
                JOIN platform_type pt ON i.platform_type_id = pt.id
                WHERE i.callsign = $1
            """, self.callsign)
            if row:
                return (
                    BatteryCapability(
                        max_range_m=row['max_range_m'],
                        max_altitude_m=row['max_altitude_m'],
                        accuracy_percent=row['accuracy_percent'],
                        reload_time_sec=row['reload_time_sec'],
                        max_speed_mps=row['max_speed_mps'],
                        blast_radius_m=row['blast_radius_m']
                    ),
                    row['ammo_count']
                )
            else:
                # Defaults
                return (
                    BatteryCapability(
                        max_range_m=200000,
                        max_altitude_m=150000,
                        accuracy_percent=85,
                        reload_time_sec=30,
                        max_speed_mps=3500,
                        blast_radius_m=50  # Defense missiles have blast radius for intercept detonation
                    ),
                    10
                )

    async def get_battery_position(self) -> Optional[dict]:
        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT geom, altitude_m
                FROM installation
                WHERE callsign = $1
            """, self.callsign)
            if row:
                geom_str = row['geom']
                lon = float(geom_str.split('(')[1].split(' ')[0])
                lat = float(geom_str.split('(')[1].split(' ')[1])
                return {"lat": lat, "lon": lon, "alt": row['altitude_m']}
        return None

    async def subscribe_engagement_orders(self, handler: Callable):
        await self.nats_client.subscribe(
            f"battery.{self.callsign}.engage",
            cb=handler
        )

    async def publish_engagement_result(self, result: dict):
        await self.nats_client.publish(
            "engagement.result",
            json.dumps(result).encode()
        ) 