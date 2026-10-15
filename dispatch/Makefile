CXX ?= g++
CPPFLAGS := -Isrc -Ivendor
CXXFLAGS ?= -std=c++20 -O2 -g -Wall -Wextra -Wpedantic -Wconversion

.PHONY: all test sanitize clean
all: build/foundry-dispatch
build:
	mkdir -p build
build/foundry-dispatch: src/main.cpp src/matching.hpp src/proof.hpp vendor/json.hpp | build
	$(CXX) $(CPPFLAGS) $(CXXFLAGS) src/main.cpp -o $@
build/matching-test: tests/matching_test.cpp src/matching.hpp src/proof.hpp | build
	$(CXX) $(CPPFLAGS) $(CXXFLAGS) tests/matching_test.cpp -o $@
test: build/matching-test build/foundry-dispatch
	./build/matching-test
	python3 tests/protocol_test.py
sanitize: | build
	$(CXX) $(CPPFLAGS) -std=c++20 -O1 -g -fsanitize=address,undefined -fno-omit-frame-pointer tests/matching_test.cpp -o build/matching-sanitize
	./build/matching-sanitize
clean:
	rm -rf build
