#!/bin/bash

#
# create-packs.sh -- by Dario Berzano <dario.berzano@cern.ch>
#
# Uses the Effing Package Manager for creating packages to distribute.
#

function pe() {
  echo -e "\033[35m> $1\033[m"
}

package_src="$( cd `dirname "$0"`/.. ; pwd )"
cd "$package_src"

# parse cmdline args
while [ $# -gt 0 ] ; do
  case "$1" in
    --iteration)
      iteration="$2"
      shift
    ;;
    --verbose)
      verbose=1
    ;;
    --clean)
      clean=1
    ;;
    *)
      pe "invalid param: $1"
      exit 1
    ;;
  esac
  shift
done

# dest dir *can* be under current source dir
package_dest="$package_src/misc/dist"

# clean?
if [ "$clean" == 1 ] ; then
  pe 'cleaning up packages dir'
  rm -f "${package_dest}"/*
  exit $?
fi

# work dir *cannot* be under current source dir
tmpdir_rsync=$( mktemp -d /tmp/create-pack-rsync-XXXXX )
[ $? == 0 ] || exit 1
tmpdir_fpm=$( mktemp -d /tmp/create-pack-fpm-XXXXX )

mkdir -p "$package_dest"

# config files
#export config_files=$( find etc -type f -and -not -name '*.example' -exec echo --config-files '{}' \; )
config_files=''

# exclusions
exclude_fpm=( '.git' '.gitignore' 'VERSION' 'README*' 'misc' 'tmp' )
exclude_rsync=( "${exclude_fpm[@]}" '*.pyc' '*.pyo' )

# version and "iteration"
if [ "$iteration" == '' ] ; then
  iteration=$( cat ITERATION 2> /dev/null || echo 0 )
  iteration=$(( iteration + 1 ))
fi
echo $iteration > ITERATION
version="$(cat VERSION)"
pe "version: $version, iteration: $iteration (override with --iteration <n>)"

for package_format in rpm deb ; do

  rm -rf "${tmpdir_rsync}"/* "${tmpdir_fpm}"/*

  case $package_format in
    rpm) python_libdir="/usr/lib/python2.7/site-packages" ;;
    deb) python_libdir="/usr/lib/python2.7/dist-packages" ;;
  esac
  pe "format: $package_format, python libdir: $python_libdir" 

  mkdir -p "${tmpdir_rsync}/${python_libdir}"
  rsync -a "${package_src}/pylib/" "${tmpdir_rsync}/${python_libdir}" \
    $( for i in ${exclude_rsync[@]} ; do echo --exclude $i ; done ) || exit 1
  mkdir -p "${tmpdir_rsync}/bin/"
  rsync -a "${package_src}/bin/" "${tmpdir_rsync}/bin" \
    $( for i in ${exclude_rsync[@]} ; do echo --exclude $i ; done ) || exit 1
  chmod u=rwX,g=rX,o=rX -R "${package_src}"

  if [ "$verbose" == 1 ] ; then
    pe 'python compiling'
    python -m compileall "${tmpdir_rsync}/${python_libdir}" || exit 1
  else
    python -m compileall -q "${tmpdir_rsync}/${python_libdir}" || exit 1
  fi

  if [ "$verbose" == 1 ] ; then
    pe 'listing directory structure'
    ( cd "$tmpdir_rsync" ; find . -ls )
  fi

  author='Dario Berzano <dario.berzano@cern.ch>'
  fpm \
    -s dir \
    -t $package_format \
    -a all \
    --force \
    --depends     'python >= 2.6' \
    --depends     'sqlite' \
    --depends     'python-prettytable' \
    --depends     'python-urllib3' \
    --name        'python-cern-alice-relval' \
    --version     "$version" \
    --iteration   "$iteration" \
    --prefix      / \
    --package     "$package_dest" \
    --workdir     "$tmpdir_fpm" \
    --vendor      "$author" \
    --maintainer  "$author" \
    --description 'Controls the Release Validation of the ALICE LHC experiment at CERN' \
    --url         'https://github.com/dberzano/cern-alice-setup' \
    -C            "$tmpdir_rsync" \
    $( for i in ${config_files[@]} ; do echo --config-files $i ; done ) \
    $( for i in ${exclude_fpm[@]} ; do echo --exclude $i ; done ) \
    . || exit 1

  if [ "$verbose" == 1 ] ; then
    if [ "$package_format" == 'rpm' ] ; then
      rpm_file=$( ls -1rt "$package_dest"/*.rpm | tail -n1 )
      pe 'rpm info'
      rpm -qip "$rpm_file"
      pe 'rpm contents'
      rpm -qlp "$rpm_file"
    fi
  fi

done

rm -rf "$tmpdir_rsync" "$tmpdir_fpm"
