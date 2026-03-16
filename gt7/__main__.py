"""Run the GT7 telemetry client (entrypoint for Docker / python -m gt7)."""
from time import sleep

from gt_telem import TurismoClient
from gt_telem.errors.playstation_errors import (
    PlayStationNotFoundError,
    PlayStationOnStandbyError,
)


def main() -> None:
    try:
        tc = TurismoClient()
    except PlayStationOnStandbyError as e:
        print("PlayStation is on standby. Turn it on.")
        raise SystemExit(1) from e
    except PlayStationNotFoundError as e:
        print("PlayStation not found. Ensure PC and PS are on the same network.")
        raise SystemExit(1) from e

    tc.start()
    try:
        for i in range(30):
            sleep(1)
            t = tc.telemetry
            if t:
                print(f"[{i+1}] speed={t.speed_mps:.1f} m/s  rpm={t.engine_rpm}  gear={t.gear}")
            else:
                print(f"[{i+1}] waiting for telemetry...")
    except KeyboardInterrupt:
        pass
    finally:
        tc.stop()


if __name__ == "__main__":
    main()
