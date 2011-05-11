#!/bin/bash
# Build the debian package for my.cnf templates

# chdir to the script dir
self="${0#./}"
base="${self%/*}"
current=`pwd`

if [ "$base" = "$self" ] ; then
    home=$current
elif [[ $base =~ ^/ ]]; then
    home="$base"
else
    home="$current/$base"
fi

cd $home

# Setup the build directory for building the package
build_dir="build"
rm -rf $build_dir
mkdir -p $build_dir
cp -R debian $build_dir
cp -R etc $build_dir

cd $build_dir

# Build the package
DEB_BUILD_OPTIONS=nocheck,nodocs dpkg-buildpackage -rfakeroot -b -uc -us -d
