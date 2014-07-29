#!/bin/env python

#
# alirelval.py -- by Dario Berzano <dario.berzano@cern.ch>
#
# Controls automatic trigger of the ALICE Release Validation.
#

import sys, urllib, re

AliRootDepsUrl = 'http://pcalienbuild4.cern.ch:8889/tarballs/Packages'


def main(argv):
  print 'here I am'

  try:
    resp = urllib.urlopen(AliRootDepsUrl)
    for l in resp:
      try:
        a = l.strip().split('\t', 5)
        packdef = {
          'tarball':      a[0],
          'software':     a[1],
          'version':      a[2],
          'platform':     a[3],
          'packagename':  a[4]
        }

        if len(a) > 5:
          packdef['packagedeps'] = a[5].split(',')

        m = re.match( r'^[^.]+\.(.*)\.tar\.gz$', packdef['tarball'] )
        if m:
          packdef['arch'] = m.group(1)
        else:
          packdef['arch'] = None

        if packdef['software'] == 'AliRoot' and packdef['arch'] is not None:
          print "%s (%s)" % ( packdef['packagename'], packdef['arch'] )

      except IndexError:
        pass
  except IOError as e:
    print 'Cannot read from URL: %s'

if __name__ == '__main__':
  main(sys.argv[1:])
