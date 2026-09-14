#!/usr/bin/env python3
"""Supervise SITL and require a converged Raft roster before issuing a command."""

import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import time
import uuid


def converged(states, count, now):
    active = [s for stamp, s in states.values() if now - stamp < 1.5]
    if len(active) != count or any(s.phase != 4 or s.membership.joint for s in active):
        return None

    swarms = {bytes(s.swarm_id) for s in active}
    ids = {s.member_id for s in active}
    leaders = [s for s in active if s.role == 2]

    if (len(swarms) != 1 or not any(next(iter(swarms))) or len(ids) != count or len(leaders) != 1):
        return None
    
    leader = leaders[0]
    roster = {
        (m.member_id, bytes(m.device_uid), m.px4_system_id)
        for m in leader.membership.members
    }
    
    if {m[2] for m in roster} != set(range(2, count + 2)):
        return None

    for s in active:
        if (
            s.leader_id != leader.member_id
            or s.term != leader.term
            or set(s.membership.voters) != ids
            or s.membership.learners
            or {
                (m.member_id, bytes(m.device_uid), m.px4_system_id)
                for m in s.membership.members
            }
            != roster
            or (s.member_id, bytes(s.device_uid)) not in {(m[0], m[1]) for m in roster}
        ):
            return None
    return leader


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-n", "--drones", type=int, default=3)
    parser.add_argument("-g", "--group", type=int, default=0)
    parser.add_argument("--dry-run", action="store_true")
    
    args = parser.parse_args()
    
    if not 1 <= args.drones <= 254 or not 0 <= args.group <= 255:
        parser.error("drones must be 1..254 and group 0..255")
        
    workspace = Path(__file__).resolve().parent.parent
    px4 = Path(
        # TODO: Buradaki px4 path generic yapilmasi lazim
        os.environ.get("PX4_DIR", str(Path.home() / "Project/Drone/Px4/PX4-Autopilot"))
    )
    
    timeout = float(os.environ.get("WAIT_TIMEOUT", "60"))
    delay = float(os.environ.get("PX4_START_DELAY", "3"))
    retries = int(os.environ.get("START_RETRIES", "3"))
    spacing = [
        float(os.environ.get("PX4_SPAWN_OFFSET_X", "5")),
        float(os.environ.get("PX4_SPAWN_OFFSET_Y", "0")),
    ]
    
    if timeout <= 0 or delay < 0 or retries < 1:
        parser.error("invalid WAIT_TIMEOUT, PX4_START_DELAY or START_RETRIES")
        
    domain = int(os.environ.get("ROS_DOMAIN_ID", "0"))
    
    if not 0 <= domain <= 232:
        parser.error("ROS_DOMAIN_ID must be 0..232")
        
    env = dict(
        os.environ,
        ROS_DOMAIN_ID=str(domain),
        GZ_PARTITION=os.environ.get("GZ_PARTITION", "px4_swarm_test"),
        GZ_IP=os.environ.get("GZ_IP", "127.0.0.1"),
        PX4_SIM_SPEED_FACTOR=os.environ.get("PX4_SIM_SPEED_FACTOR", "1.0"),
    )
    
    logs = Path(os.environ.get("LOG_DIR", f"/tmp/sitl-swarm-{os.getpid()}"))
    processes = []
    handles = []
    node = None

    def check():
        for name, proc in processes:
            if proc.poll() is not None:
                raise RuntimeError(
                    f'{name} exited ({proc.returncode}); see {logs / (name + ".log")}'
                )

    def pause(seconds):
        until = time.monotonic() + seconds
        while time.monotonic() < until:
            check()
            time.sleep(min(0.1, max(0, until - time.monotonic())))

    def start(name, command, extra=None, cwd=workspace):
        print(name, ":", " ".join(command), extra or {}, flush=True)
        if args.dry_run:
            return
        for attempt in range(retries):
            handle = open(logs / (name + ".log"), "a")
            handles.append(handle)
            proc = subprocess.Popen(
                command,
                env=dict(env, **(extra or {})),
                cwd=cwd,
                stdin=subprocess.DEVNULL,
                stdout=handle,
                stderr=handle,
                start_new_session=True,
            )
            time.sleep(0.3)
            if proc.poll() is None:
                processes.append((name, proc))
                return
            try:
                os.killpg(proc.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
        raise RuntimeError(f'{name} failed to start; see {logs / (name + ".log")}')

    def stop(*_):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, stop)
    try:
        if not args.dry_run:
            logs.mkdir(parents=True, exist_ok=True)
            if not (px4 / "build/px4_sitl_default/bin/px4").is_file():
                raise RuntimeError(f"PX4 binary not found under {px4}")
        start(
            "xrce",
            [os.environ.get("XRCE_AGENT", "MicroXRCEAgent"), "udp4", "-p", "8888"],
        )
        for i in range(1, args.drones + 1):
            extra = dict(
                PX4_SYS_AUTOSTART="4001",
                PX4_SIM_MODEL=os.environ.get("SITL_MODEL", "gz_x500"),
                PX4_GZ_WORLD=os.environ.get("PX4_GZ_WORLD", "default"),
                PX4_GZ_MODEL_POSE=f"{(i-1)*spacing[0]},{(i-1)*spacing[1]},0,0,0,0",
                PX4_UXRCE_DDS_NS=f"px4_{i}",
                PX4_GZ_STANDALONE="0" if i == 1 else "1",
            )
            start(
                f"px4_{i}",
                [str(px4 / "build/px4_sitl_default/bin/px4"), "-d", "-i", str(i)],
                extra,
                px4,
            )
            if not args.dry_run:
                pause(max(10, delay) if i == 1 else delay)
        for i in range(1, args.drones + 1):
            start(
                f"raft_{i}",
                [
                    str(workspace / "install/swarm_raft/lib/swarm_raft/raft_node"),
                    "--ros-args",
                    "-r",
                    f"__node:=raft_{i}",
                    "-p",
                    f"px4_system_id:={i+1}",
                    "-p",
                    "discovery_min_ms:=3000",
                    "-p",
                    "discovery_max_ms:=5000",
                ],
            )
        if args.dry_run:
            print(
                "Wait for fresh statuses: one swarm, one leader, matching full voter rosters."
            )
            print(
                "Start controllers with admitted member IDs, swarm ID and /px4_N namespaces."
            )
            print(
                "Wait for each PX4 sensor topic; submit targeted takeoff and match its completion."
            )
            return

        import rclpy
        from rclpy.qos import (
            QoSProfile,
            DurabilityPolicy,
            ReliabilityPolicy,
            qos_profile_sensor_data,
        )
        from swarm_msgs.msg import RaftStatus, CommandRequest, CommandCompletion
        from px4_msgs.msg import SensorCombined

        rclpy.init()
        node = rclpy.create_node("sitl_swarm_launcher")
        states, completions, sensors = {}, [], {}
        qos = QoSProfile(
            depth=30,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
            reliability=ReliabilityPolicy.RELIABLE,
        )
        subscriptions = [
            node.create_subscription(
                RaftStatus,
                "/swarm/raft/status",
                lambda s: states.__setitem__(
                    bytes(s.device_uid), (time.monotonic(), s)
                ),
                qos,
            ),
            node.create_subscription(
                CommandCompletion,
                "/swarm/raft/command_completion",
                completions.append,
                64,
            ),
        ]
        publisher = node.create_publisher(CommandRequest, "/swarm/raft/command", 64)
        for i in range(1, args.drones + 1):
            subscriptions.append(
                node.create_subscription(
                    SensorCombined,
                    f"/px4_{i}/fmu/out/sensor_combined",
                    lambda _, i=i: sensors.__setitem__(i, time.monotonic()),
                    qos_profile_sensor_data,
                )
            )

        def wait_for(predicate, description):
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                check()
                rclpy.spin_once(node, timeout_sec=0.1)
                value = predicate()
                if value:
                    print(description, flush=True)
                    return value
            summary = [
                (
                    s.member_id,
                    s.phase,
                    s.role,
                    bytes(s.swarm_id).hex(),
                    list(s.membership.voters),
                )
                for _, s in states.values()
            ]
            raise RuntimeError(
                f"{description}: timed out; states={summary}; logs={logs}"
            )

        leader = wait_for(
            lambda: converged(states, args.drones, time.monotonic()),
            "Raft cluster converged",
        )
        for member in leader.membership.members:
            i = member.px4_system_id - 1

            swarm_id_str = leader.swarm_id.tolist()

            start(
                f"controller_{i}",
                [
                    str(
                        workspace
                        / "install/swarm_controller/lib/swarm_controller/takeoff_controller_node"
                    ),
                    "--ros-args",
                    "-r",
                    f"__node:=controller_{i}",
                    "-r",
                    f"__ns:=/px4_{i}",
                    "-p",
                    f"px4_system_id:={member.px4_system_id}",
                    "-p",
                    f"member_id:={member.member_id}",
                    "-p",
                    f"group_id:={args.group}",
                    "-p",
                    "swarm_id:=" + json.dumps(swarm_id_str),
                ],
            )
        wait_for(
            lambda: len(sensors) == args.drones
            and all(time.monotonic() - t < 2 for t in sensors.values()),
            "All PX4 sensor streams available",
        )
        wait_for(
            lambda: publisher.get_subscription_count() >= args.drones,
            "Raft command subscribers available",
        )
        wait_for(
            lambda: node.count_subscribers("/swarm/raft/committed_operation_mode")
            >= args.drones,
            "Controllers connected",
        )
        leader = wait_for(
            lambda: converged(states, args.drones, time.monotonic()),
            "Raft membership confirmed",
        )
        while True:
            check()
            rclpy.spin_once(node, timeout_sec=0.2)
    except KeyboardInterrupt:
        pass
    finally:
        for _, proc in reversed(processes):
            try:
                os.killpg(proc.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
        for _, proc in reversed(processes):
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                pass
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        for handle in handles:
            handle.close()
        if node is not None:
            node.destroy_node()
            rclpy.shutdown()
        if not args.dry_run:
            print(f"Logs retained in {logs}", flush=True)


if __name__ == "__main__":
    main()
