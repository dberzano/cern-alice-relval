#!/bin/bash

#
# create-packs.sh -- by Dario Berzano <dario.berzano@cern.ch>
#
# Uses the Effing Package Manager for creating packages to distribute.
#

function pe() {
  echo -e "\033[35m> $1\033[m"
}

PackageSourceDir="$( cd `dirname "$0"`/.. ; pwd )"
cd "$PackageSourceDir"

# dest dir can be under current source dir
PackageDestDir="$PackageSourceDir/misc/dist"

# work dir *cannot* be under current source dir
PackageWorkDir=$( mktemp -d /tmp/packwd-XXXXX )
[ $? == 0 ] || exit 1
FpmWorkDir=$( mktemp -d /tmp/fpmwd-XXXXX )

# author, vendor, maintanier
MetaAuthor='Dario Berzano <dario.berzano@cern.ch>'
MetaDescr='Controls the Release Validation of the ALICE LHC experiment at CERN'
MetaUrl='https://github.com/dberzano/cern-alice-setup'
MetaName='python-cern-alice-relval'

pe "Source : $PackageSourceDir"
pe "Dest   : $PackageDestDir"

mkdir -p "$PackageDestDir"

# Configuration files: all in etc but without *.example files
#export ConfigFiles=$( find etc -type f -and -not -name '*.example' -exec echo --config-files '{}' \; )
ConfigFiles=''

# config files
PackConfigFiles=''

# exclusions
PackExclusions=( '.git' '.gitignore' 'VERSION' 'README*' 'misc' 'tmp' )
RsyncExclusions=( "${PackExclusions[@]}" '*.pyc' '*.pyo' )

pe 'creating directory structure'
PyLib=$( python -c 'from distutils.sysconfig import get_python_lib; print get_python_lib()' )
mkdir -p "${PackageWorkDir}/${PyLib}"
rsync -va "${PackageSourceDir}/pylib/" "${PackageWorkDir}/${PyLib}" \
  $( for i in ${RsyncExclusions[@]} ; do echo --exclude $i ; done ) || exit 1
mkdir -p "${PackageWorkDir}/bin/"
rsync -va "${PackageSourceDir}/bin/" "${PackageWorkDir}/bin" \
  $( for i in ${RsyncExclusions[@]} ; do echo --exclude $i ; done ) || exit 1
chmod u=rwX,g=rX,o=rX -R "${PackageSourceDir}"

pe 'python compiling'
python -m compileall "${PackageWorkDir}/${PyLib}" || exit 1

pe 'listing directory structure'
( cd "$PackageWorkDir" ; find . -ls )

MetaIteration=$( cat ITERATION 2> /dev/null || echo 0 )
MetaIteration=$(( MetaIteration + 1 ))
echo $MetaIteration > ITERATION
pe "version: $(cat VERSION) iteration: $MetaIteration"

fpm \
  -s dir \
  -t rpm \
  -a all \
  --depends 'python >= 2.6' \
  --depends 'sqlite' \
  --depends 'python-prettytable' \
  --depends 'python-urllib3' \
  --force \
  --version "$(cat VERSION)" \
  --iteration "$MetaIteration" \
  --name "$MetaName" \
  --package "$PackageDestDir" \
  --workdir "$FpmWorkDir" \
  --vendor "$MetaAuthor" \
  --maintainer "$MetaAuthor" \
  --description "$MetaDescr" \
  --url "$MetaUrl" \
  $( for i in ${PackConfigFiles[@]} ; do echo --config-files $i ; done ) \
  --prefix / \
  $( for i in ${PackExclusions[@]} ; do echo --exclude $i ; done ) \
  -C "$PackageWorkDir" \
  . || exit 1

rm -rf "$PackageWorkDir" "$FpmWorkDir"

Rpm=$( ls -1rt "$PackageDestDir"/*.rpm | tail -n1 )

pe 'packages dir'
ls -l "$PackageDestDir"

pe 'rpm info'
rpm -qip "$Rpm"

pe 'rpm contents'
rpm -qlp "$Rpm"
