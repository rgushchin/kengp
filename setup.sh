#!/bin/bash

echo "Checking out submodules..."
git submodule init
git submodule update

echo "Building semcode..."
cd semcode
cargo build --release
cd ..

echo "Done"

