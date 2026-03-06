# make install setup start
# in new terminal, run a workload: make [allocate4G, memory_workload, cpu_workload, stressng_memory_workload]
# stop workload and visualize: make visualize


all: setup start

install:
	sudo apt update
	sudo apt upgrade
	sudo apt install cgroup-tools stress-ng python3-psutil python3-matplotlib python3-pandas

setup: setup.sh
	sudo ./setup.sh

start: controller.py
	sudo python3 controller.py

visualize: visualize.py movement_avoidance_results.csv
	python3 visualize.py



EXEC=sudo cgexec -g memory:movement_avoidance_test

# Python workloads

memory_workload: memory_workload.py
	$(EXEC) python3 $<

cpu_workload: cpu_workload.py
	$(EXEC) python3 $<

stressng_memory_workload: stressng_memory_workload.py
	$(EXEC) python3 $< --duration 30--pattern random --contention 50

stressng_sweep: stressng_memory_workload.py
	$(EXEC) python3 $< --duration 60


# C workloads

allocate1G: allocate_memory
	$(EXEC) ./$< 1G 4M

allocate4G: allocate_memory
	$(EXEC) ./$< 4G 4M

allocate_memory: allocate_memory.c
	gcc -O3 -o $@ $<

clean:
	rm -f allocate_memory
