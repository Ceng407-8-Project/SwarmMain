#!/usr/bin/env bash
set -eo pipefail

workspace_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
ros_distro="${ROS_DISTRO:-jazzy}"
mode="${1:-build}"

if [[ "$mode" != "build" && "$mode" != "deps" ]]; then
    echo 'Usage: buildRaft.sh [build|deps]' >&2
    exit 2
fi

if [[ ! -d "$workspace_dir/src/swarm_msgs" || ! -d "$workspace_dir/src/swarm_raft" || ! -d "$workspace_dir/src/swarm_controller" ]]; then
    echo "Expected swarm_msgs, swarm_raft, and swarm_controller under $workspace_dir/src" >&2
    exit 1
fi

set +u
source "/opt/ros/$ros_distro/setup.bash"
set -u
cd "$workspace_dir"

prepare_dependencies() {
    rosdep install --from-paths src/swarm_msgs src/swarm_raft src/swarm_controller \
        --ignore-src --rosdistro "$ros_distro" -y

    colcon build --base-paths src/swarm_msgs --packages-select swarm_msgs
}

if [[ "$mode" == "deps" || ! -f install/swarm_msgs/share/swarm_msgs/local_setup.bash ]]; then
    prepare_dependencies
fi

if [[ "$mode" == "build" ]]; then
    set +u
    source "$workspace_dir/install/swarm_msgs/share/swarm_msgs/local_setup.bash"
    set -u
    colcon build --base-paths src/swarm_raft --packages-select swarm_raft
    set +u
    source "$workspace_dir/install/swarm_raft/share/swarm_raft/local_setup.bash"
    set -u
    colcon build --base-paths src/swarm_controller --packages-select swarm_controller
fi