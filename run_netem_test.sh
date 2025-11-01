sudo ip netns exec sender $(pwd)/venv/bin/python src/test_ordered.py   --host 10.0.0.2 --port 4433 --netem 1
