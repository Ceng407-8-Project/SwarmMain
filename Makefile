.PHONY: build pack clear

build:
	@colcon build

pack:
	@./Tools/packageScript.sh

clear:
	@rm -rf build install log package

.PHONY: raft raft-deps

raft:
	@bash ./Tools/buildRaft.sh build

raft-deps:
	@bash ./Tools/buildRaft.sh deps
