#!/usr/bin/env bash
set -Eeuo pipefail

usage() {
    cat <<'EOF'
Usage: runSITLSwarm.sh [options]

Start PX4 SITL instances, the Micro XRCE-DDS agent, one Raft node, and one
controller per vehicle, then request the common group takeoff and wait for
Raft commit. Keep processes running until Ctrl+C.

Options:
  -n, --drones N       Number of SITL vehicles (default: 3)
  -g, --group ID       Raft group to take off (default: 0)
      --dry-run        Print commands without starting processes or ROS 2
  -h, --help           Show this help

Environment overrides:
  PX4_DIR              PX4-Autopilot directory (default: ~/Project/Drone/Px4/PX4-Autopilot)
  ROS_DISTRO           ROS distribution (default: jazzy)
  XRCE_AGENT            XRCE agent executable (default: MicroXRCEAgent)
  SITL_MODEL           PX4 model (default: gz_x500)
  ROS_DOMAIN_ID        ROS domain shared by all processes (default: 0)
  WAIT_TIMEOUT         Readiness/takeoff timeout in seconds (default: 60)
  START_RETRIES        Process startup attempts (default: 3)
  LOG_DIR              Directory for launcher logs (default: /tmp/sitl-swarm-<pid>)
  PX4_GZ_WORLD         Gazebo world name (default: default)
  PX4_SPAWN_OFFSET_X  X spacing between vehicles in metres (default: 5)
  PX4_SPAWN_OFFSET_Y  Y spacing between vehicles in metres (default: 0)
  PX4_START_DELAY     Seconds between PX4 instance starts (default: 3)
EOF
}

workspace_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
for arg in "$@"; do
    case "$arg" in
        -h|--help) usage; exit 0 ;;
        --dry-run) exec python3 "$workspace_dir/Tools/sitl_swarm.py" "$@" ;;
    esac
done
set +u
source "/opt/ros/${ROS_DISTRO:-jazzy}/setup.bash"
source "$workspace_dir/install/setup.bash"
set -u
exec python3 "$workspace_dir/Tools/sitl_swarm.py" "$@"
