#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "$0")"
output="$PWD/results/$(date +%Y%m%d-%H%M%S)"
mkdir -p "$output"
controller_pid=''
cleanup() {
    if [[ -n "$controller_pid" ]]; then
        kill "$controller_pid" 2>/dev/null || true
        wait "$controller_pid" 2>/dev/null || true
    fi
}
trap cleanup EXIT
trap 'exit 130' INT TERM
# Obtain permission before starting the experiment; sudo is limited to Mininet.
sudo -v
python3 -B generate_content.py
./sdn-env/bin/python -B sdn_launcher.py --results "$output" > "$output/controller.log" 2>&1 &
controller_pid=$!
sleep 1
if ! kill -0 "$controller_pid" 2>/dev/null; then cat "$output/controller.log"; exit 1; fi
status=0
sudo /usr/bin/python3 -B experiment.py --results "$output" "$@" || status=$?
python3 -B plot_results.py "$output" || status=1
printf 'Results: %s\n' "$output"
exit "$status"
