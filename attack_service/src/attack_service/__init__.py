"""
Attack Service Package

A service for managing missile launches and platform installations
in the missile defense simulation system.
"""

__version__ = "2.0.0"
__author__ = "Missile Defense Sim Team"

from .api import AttackServiceAPI, ArmRequest, LaunchRequest, InstallationRequest
from .messaging import MessagingService, MissileState

__all__ = [
    "AttackServiceAPI",
    "ArmRequest", 
    "LaunchRequest",
    "InstallationRequest",
    "MessagingService",
    "MissileState"
] 