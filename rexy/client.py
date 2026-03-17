"""GT7 telemetry client: serializer, sync callbacks, event wiring."""
from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING

from gt_telem import TurismoClient
from gt_telem.events.game_events import GameEvents
from gt_telem.events.race_events import RaceEvents
from gt_telem.models.telemetry import Telemetry

if TYPE_CHECKING:
    from rexy.recorder import LapRecorder


def telemetry_to_dict(t: Telemetry) -> dict:
    """Flat dict of all telemetry fields, suitable for JSON and SQLite.

    Does NOT use Telemetry.as_dict — that property returns nested Vector3D/
    WheelMetric objects and strips the flat per-axis and per-corner fields we need.
    """
    return {
        "packet_id": t.packet_id,
        "speed_mps": t.speed_mps,
        "engine_rpm": t.engine_rpm,
        "current_gear": t.bits & 0b1111,
        "suggested_gear": t.bits >> 4,
        "throttle": t.throttle,
        "brake": t.brake,
        "clutch_pedal": t.clutch_pedal,
        "clutch_engagement": t.clutch_engagement,
        "boost_pressure": t.boost_pressure,
        "fuel_level": t.fuel_level,
        "fuel_capacity": t.fuel_capacity,
        "oil_pressure": t.oil_pressure,
        "oil_temp": t.oil_temp,
        "water_temp": t.water_temp,
        "tire_fl_temp": t.tire_fl_temp,
        "tire_fr_temp": t.tire_fr_temp,
        "tire_rl_temp": t.tire_rl_temp,
        "tire_rr_temp": t.tire_rr_temp,
        "tire_fl_sus_height": t.tire_fl_sus_height,
        "tire_fr_sus_height": t.tire_fr_sus_height,
        "tire_rl_sus_height": t.tire_rl_sus_height,
        "tire_rr_sus_height": t.tire_rr_sus_height,
        "tire_fl_radius": t.tire_fl_radius,
        "tire_fr_radius": t.tire_fr_radius,
        "tire_rl_radius": t.tire_rl_radius,
        "tire_rr_radius": t.tire_rr_radius,
        "wheel_fl_rps": t.wheel_fl_rps,
        "wheel_fr_rps": t.wheel_fr_rps,
        "wheel_rl_rps": t.wheel_rl_rps,
        "wheel_rr_rps": t.wheel_rr_rps,
        "current_lap": t.current_lap,
        "total_laps": t.total_laps,
        "best_lap_time_ms": t.best_lap_time_ms,
        "last_lap_time_ms": t.last_lap_time_ms,
        "time_of_day_ms": t.time_of_day_ms,
        "race_start_pos": t.race_start_pos,
        "total_cars": t.total_cars,
        "position_x": t.position_x,
        "position_y": t.position_y,
        "position_z": t.position_z,
        "velocity_x": t.velocity_x,
        "velocity_y": t.velocity_y,
        "velocity_z": t.velocity_z,
        "ang_vel_x": t.ang_vel_x,
        "ang_vel_y": t.ang_vel_y,
        "ang_vel_z": t.ang_vel_z,
        "rotation_x": t.rotation_x,
        "rotation_y": t.rotation_y,
        "rotation_z": t.rotation_z,
        "road_plane_x": t.road_plane_x,
        "road_plane_y": t.road_plane_y,
        "road_plane_z": t.road_plane_z,
        "road_plane_dist": t.road_plane_dist,
        "body_height": t.body_height,
        "orientation": t.orientation,
        "min_alert_rpm": t.min_alert_rpm,
        "max_alert_rpm": t.max_alert_rpm,
        "calc_max_speed": t.calc_max_speed,
        "trans_rpm": t.trans_rpm,
        "trans_top_speed": t.trans_top_speed,
        "gear1": t.gear1,
        "gear2": t.gear2,
        "gear3": t.gear3,
        "gear4": t.gear4,
        "gear5": t.gear5,
        "gear6": t.gear6,
        "gear7": t.gear7,
        "gear8": t.gear8,
        "car_code": t.car_code,
        # Decoded flags — bit positions from Telemetry source
        "tcs_active": bool(t.flags & (1 << 11)),
        "asm_active": bool(t.flags & (1 << 10)),
        "cars_on_track": bool(t.flags & (1 << 0)),
        "is_paused": bool(t.flags & (1 << 1)),
        "in_gear": bool(t.flags & (1 << 3)),
        "rev_limit": bool(t.flags & (1 << 5)),
        "hand_brake_active": bool(t.flags & (1 << 6)),
        # Heartbeat B only — None for A and ~
        "wheel_rotation_radians": getattr(t, "wheel_rotation_radians", None),
        "filler_float_fb": getattr(t, "filler_float_fb", None),
        "sway": getattr(t, "sway", None),
        "heave": getattr(t, "heave", None),
        "surge": getattr(t, "surge", None),
        # Heartbeat ~ only — None for A and B
        "throttle_filtered": getattr(t, "throttle_filtered", None),
        "brake_filtered": getattr(t, "brake_filtered", None),
        "energy_recovery": getattr(t, "energy_recovery", None),
    }


def setup_client(
    tc: TurismoClient,
    raw_queue: asyncio.Queue,
    recorder: LapRecorder,
    loop: asyncio.AbstractEventLoop,
    heartbeat_type: str,
) -> None:
    """Register all gt-telem callbacks. Call before tc.start().

    All callbacks are sync and communicate back to the asyncio loop via
    call_soon_threadsafe — gt-telem runs callbacks in its own thread pool.

    GameEvents and RaceEvents use class-level lists; create exactly one instance
    of each per process to avoid duplicate callback registrations.
    """
    game_events = GameEvents(tc)
    race_events = RaceEvents(tc)

    def on_frame_handler(t: Telemetry) -> None:
        frame = telemetry_to_dict(t)
        frame["ts"] = time.time()
        frame["heartbeat_type"] = heartbeat_type
        loop.call_soon_threadsafe(raw_queue.put_nowait, frame)

    def on_at_track_handler() -> None:
        # TT / practice: cars_on_track=False; current_lap not available here
        loop.call_soon_threadsafe(
            lambda: asyncio.create_task(recorder.reset_and_new_lap(1))
        )

    def on_in_race_handler() -> None:
        # Race start: cars_on_track=True, current_lap=0; on_lap_change(1) flushes it
        loop.call_soon_threadsafe(
            lambda: asyncio.create_task(recorder.reset_and_new_lap(0))
        )

    def on_race_end_handler() -> None:
        loop.call_soon_threadsafe(
            lambda: asyncio.create_task(recorder.close())
        )

    def on_lap_change_handler(new_lap_number: int) -> None:
        loop.call_soon_threadsafe(
            lambda n=new_lap_number: asyncio.create_task(recorder.flush_and_new_lap(n))
        )

    def on_track_detected_handler(track_id: int) -> None:
        loop.call_soon_threadsafe(recorder.set_track_id, track_id)

    game_events.on_at_track.append(on_at_track_handler)
    game_events.on_in_race.append(on_in_race_handler)
    game_events.on_race_end.append(on_race_end_handler)
    game_events.on_in_game_menu.append(on_race_end_handler)
    race_events.on_lap_change.append(on_lap_change_handler)
    race_events.on_track_detected.append(on_track_detected_handler)
    tc.register_callback(on_frame_handler)
