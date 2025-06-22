"""
Messaging service for the Battery Simulation Service.
Handles all database interactions and NATS communication.
"""
import asyncio
import asyncpg
import nats
from nats.aio.client import Client as NATS
import json
import time
from typing import Optional, Dict, List, Any

class BatteryMessagingService:
    def __init__(self, db_dsn: str, nats_url: str):
        self.db_dsn = db_dsn
        self.nats_url = nats_url
        self.db_pool: Optional[asyncpg.Pool] = None
        self.nats_client: Optional[NATS] = None

    async def initialize(self):
        """Initializes the database pool and NATS client."""
        self.db_pool = await asyncpg.create_pool(dsn=self.db_dsn)
        self.nats_client = NATS()
        await self.nats_client.connect(self.nats_url)
        print("Battery Messaging Service initialized.")

    async def shutdown(self):
        """Closes all connections."""
        if self.nats_client:
            await self.nats_client.close()
        if self.db_pool:
            await self.db_pool.close()
        print("Battery Messaging Service shut down.")

    async def create_installation(self, platform_nickname: str, callsign: str, 
                                  lat: float, lon: float, altitude_m: float = 0) -> Dict[str, Any]:
        """Creates a new battery installation in the database."""
        async with self.db_pool.acquire() as con:
            platform_id = await con.fetchval("SELECT id FROM platform_type WHERE nickname = $1 AND category = 'counter_defense'", platform_nickname)
            if not platform_id:
                raise ValueError(f"Platform '{platform_nickname}' is not a valid counter-defense platform.")

            existing = await con.fetchval("SELECT id FROM installation WHERE callsign = $1", callsign)
            if existing:
                raise ValueError(f"Installation with callsign '{callsign}' already exists.")

            await con.execute("""
                INSERT INTO installation (platform_type_id, callsign, geom, altitude_m)
                VALUES ($1, $2, ST_SetSRID(ST_MakePoint($3, $4), 4326)::geography, $5)
            """, platform_id, callsign, lon, lat, altitude_m)
            
            return {"status": "created", "callsign": callsign}

    async def arm_battery(self, battery_callsign: str, munition_nickname: str, quantity: int) -> Dict[str, Any]:
        """Arms a battery installation with a specific munition."""
        async with self.db_pool.acquire() as con:
            battery_id = await con.fetchval("SELECT id FROM installation WHERE callsign = $1", battery_callsign)
            if not battery_id:
                raise ValueError(f"Battery with callsign '{battery_callsign}' not found.")

            munition_id = await con.fetchval("SELECT id FROM munition_type WHERE nickname = $1 AND category = 'defense'", munition_nickname)
            if not munition_id:
                raise ValueError(f"Munition '{munition_nickname}' is not a valid defense munition.")

            await con.execute("""
                INSERT INTO installation_munition (installation_id, munition_type_id, quantity)
                VALUES ($1, $2, $3)
                ON CONFLICT (installation_id, munition_type_id)
                DO UPDATE SET quantity = installation_munition.quantity + EXCLUDED.quantity;
            """, battery_id, munition_id, quantity)
            
            return {"status": "armed", "battery_callsign": battery_callsign, "munition": munition_nickname, "quantity": quantity}

    async def launch_defense_missile(self, battery_callsign: str, munition_nickname: str, target_missile_id: str) -> Dict[str, Any]:
        """Validates and initiates a defense missile launch."""
        async with self.db_pool.acquire() as con:
            async with con.transaction():
                battery = await con.fetchrow("SELECT id, ST_X(geom::geometry) as lon, ST_Y(geom::geometry) as lat, altitude_m as alt FROM installation WHERE callsign = $1", battery_callsign)
                if not battery:
                    raise ValueError(f"Battery '{battery_callsign}' not found.")

                munition_type = await con.fetchrow("SELECT id FROM munition_type WHERE nickname = $1 AND category = 'defense'", munition_nickname)
                if not munition_type:
                    raise ValueError(f"'{munition_nickname}' is not a valid defense munition.")

                ammo_record = await con.fetchrow("SELECT id, quantity FROM installation_munition WHERE installation_id = $1 AND munition_type_id = $2", battery['id'], munition_type['id'])
                if not ammo_record or ammo_record['quantity'] < 1:
                    raise ValueError(f"Battery '{battery_callsign}' has no '{munition_nickname}' ammunition.")

                await con.execute("UPDATE installation_munition SET quantity = quantity - 1 WHERE id = $1", ammo_record['id'])

                fired_count = await con.fetchval("SELECT COUNT(*) FROM active_missile WHERE launch_installation_id = $1", battery['id'])
                munition_abbreviation = "".join([c for c in munition_nickname if c.isupper() or c.isdigit()])
                new_missile_callsign = f"{battery_callsign}-{munition_abbreviation}-{fired_count + 1}"

                # The command center will calculate the intercept point. 
                # For now, we assume a simplified targeting model where the target is the enemy missile.
                # The simulation service will handle the actual intercept physics.
                launch_message = {
                    "type": "missile_launch",
                    "missile_callsign": new_missile_callsign,
                    "munition_nickname": munition_nickname,
                    "launch_callsign": battery_callsign,
                    "launch_lat": battery['lat'],
                    "launch_lon": battery['lon'],
                    "launch_alt": battery['alt'],
                    "missile_type": "defense",
                    "target_missile_id": target_missile_id, # Target for the interceptor
                    "timestamp": time.time()
                }
                
                await self.nats_client.publish("simulation.launch", json.dumps(launch_message).encode())
                
                return {"status": "launched", "interceptor_callsign": new_missile_callsign, "target": target_missile_id}

    async def handle_engagement_order(self, msg):
        """Callback to process engagement orders from the command center."""
        try:
            order = json.loads(msg.data.decode())
            battery_callsign = order.get("battery_callsign")
            munition_nickname = order.get("munition_nickname", "SM-3") # Default interceptor
            target_missile_id = order.get("target_missile_id")

            if not all([battery_callsign, target_missile_id]):
                print(f"Invalid engagement order received: {order}")
                return

            print(f"Received engagement order for battery {battery_callsign} to intercept {target_missile_id}")
            
            # Directly call launch logic. A more complex system might have a readiness check.
            await self.launch_defense_missile(
                battery_callsign=battery_callsign,
                munition_nickname=munition_nickname,
                target_missile_id=target_missile_id
            )

        except json.JSONDecodeError:
            print(f"Failed to decode engagement order: {msg.data.decode()}")
        except ValueError as e:
            print(f"Failed to process engagement for {order.get('battery_callsign')}: {e}")
        except Exception as e:
            print(f"An unexpected error occurred while handling engagement order: {e}")

    async def listen_for_engagement_orders(self):
        """Subscribes to NATS subjects for engagement orders."""
        # Subscribes to a wildcard subject for all battery engagements
        await self.nats_client.subscribe("orders.engagement.>", cb=self.handle_engagement_order)
        print("Listening for engagement orders on 'orders.engagement.>'") 