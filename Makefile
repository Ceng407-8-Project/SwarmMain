.PHONY: build pack clear

build:
	@colcon build

pack:
	@./Tools/packageScript.sh

clear:
	@rm -rf build install log package