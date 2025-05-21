import re
import sys

if len(sys.argv) != 2:
    print(f"Usage: {sys.argv[0]} <scenescape-build.log>")
    sys.exit(1)

logfile = sys.argv[1]
total_time = 0.0

layer_cmd_re = re.compile(r"^(#(\d+) \[[ a-z_]*([ 0-9]+)/([0-9]+)\] .+)")
done_re = re.compile(r"^(#(\d+) DONE ([0-9.]+)s)")

# Store layer info: {stage_num: {"cmd": str, "done": str, "time": float}}
layers = {}

with open(logfile, "r") as f:
    for line in f:
        line = line.rstrip("\n")
        m_cmd = layer_cmd_re.match(line)
        if m_cmd:
            stage_num = m_cmd.group(2)
            layers.setdefault(stage_num, {})["cmd"] = line
            # print(line)
        m_done = done_re.match(line)
        if m_done:
            stage_num = m_done.group(2)
            time = float(m_done.group(3))
            layers.setdefault(stage_num, {})["done"] = m_done.group(1)
            layers[stage_num]["time"] = time
            print(m_done.group(1))
            total_time += time

print(f"\n{logfile} build time [s]: {total_time:.1f}")

# Find top 3 time-consuming layers
top_layers = sorted(
    (v for v in layers.values() if "time" in v),
    key=lambda x: x["time"],
    reverse=True
)[:3]

print("\nTop 3 time-consuming layers:")
for i, layer in enumerate(top_layers, 1):
    print(f"{i}. Time: {layer['time']:.1f}s")
    print(f"   Command: {layer.get('cmd', '(unknown)')}")
