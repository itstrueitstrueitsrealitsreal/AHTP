# Network namespaces & veth configuration
SENDER_NS=sender
RECEIVER_NS=receiver
SENDER_IF=veth0
RECEIVER_IF=veth1
SENDER_IP=10.0.0.1
RECEIVER_IP=10.0.0.2
DELAY=50ms
LOSS=5%
RATE=10mbit

.PHONY: setup teardown sender receiver status clean

# ---------------------------------------------------------------------
# Create namespaces, connect veth pair, assign IPs, bring interfaces up
# ---------------------------------------------------------------------
setup:
	@echo "Setting up namespaces and veth pair..."
	sudo ip netns add $(SENDER_NS)
	sudo ip netns add $(RECEIVER_NS)
	sudo ip link add $(SENDER_IF) type veth peer name $(RECEIVER_IF)
	sudo ip link set $(SENDER_IF) netns $(SENDER_NS)
	sudo ip link set $(RECEIVER_IF) netns $(RECEIVER_NS)
	sudo ip netns exec $(SENDER_NS) ip addr add $(SENDER_IP)/24 dev $(SENDER_IF)
	sudo ip netns exec $(RECEIVER_NS) ip addr add $(RECEIVER_IP)/24 dev $(RECEIVER_IF)
	sudo ip netns exec $(SENDER_NS) ip link set $(SENDER_IF) up
	sudo ip netns exec $(RECEIVER_NS) ip link set $(RECEIVER_IF) up
	sudo ip netns exec $(SENDER_NS) ip link set lo up
	sudo ip netns exec $(SENDER_NS) tc qdisc add dev $(SENDER_IF) root netem delay $(DELAY) loss $(LOSS) rate $(RATE)
	sudo ip netns exec $(RECEIVER_NS) ip link set lo up
	sudo ip netns exec $(RECEIVER_NS) tc qdisc add dev $(RECEIVER_IF) root netem delay $(DELAY) loss $(LOSS) rate $(RATE)
	python scripts/generate_certs.py
	@echo "Setup complete. $(SENDER_IP) ↔ $(RECEIVER_IP) connected with delay $(DELAY), loss $(LOSS), rate $(RATE)."

# ---------------------------------------------------------------------
# Delete qdiscs, veths, and namespaces
# ---------------------------------------------------------------------
teardown:
	@echo "Cleaning up namespaces and qdiscs..."
	-sudo ip netns exec $(RECEIVER_NS) tc qdisc del dev $(RECEIVER_IF) root 2>/dev/null || true
	-sudo ip link delete $(SENDER_IF) type veth 2>/dev/null || true
	-sudo ip netns del $(SENDER_NS) 2>/dev/null || true
	-sudo ip netns del $(RECEIVER_NS) 2>/dev/null || true
	rm -rf certs
	@echo "Teardown complete."

# ---------------------------------------------------------------------
# Utility commands
# ---------------------------------------------------------------------
status:
	sudo ip netns list
	sudo ip netns exec $(RECEIVER_NS) tc qdisc show dev $(RECEIVER_IF)

clean: 
	make teardown
	rm -f *.jsonl
	sudo rm -f results/*
	sudo rm -f *.png
	sudo rm -f figures/*

netem:
	make clean; make setup; rm *.jsonl*; ./run_netem_test.sh


plots:
	python src/plot_metrics.py
	zip -r fig.zip figures/*
