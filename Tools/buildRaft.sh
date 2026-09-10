#!/usr/bin/env bash
set -eo pipefail

workspace_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
ros_distro="${ROS_DISTRO:-jazzy}"
mode="${1:-build}"

if [[ "$mode" != "build" && "$mode" != "deps" ]]; then
    echo 'Usage: buildRaft.sh [build|deps]' >&2
    exit 2
fi

source "/opt/ros/$ros_distro/setup.bash"
cd "$workspace_dir"

prepare_dependencies() {
    rosdep install --from-paths src/swarm_msgs src/swarm_raft \
        --ignore-src --rosdistro "$ros_distro" -y

    colcon build --base-paths src/swarm_msgs --packages-select swarm_msgs
}

if [[ "$mode" == "deps" || ! -f install/swarm_msgs/share/swarm_msgs/local_setup.bash ]]; then
    prepare_dependencies
fi

if [[ "$mode" == "build" ]]; then
    source "$workspace_dir/install/swarm_msgs/share/swarm_msgs/local_setup.bash"
    colcon build --base-paths src/swarm_raft --packages-select swarm_raft
fi