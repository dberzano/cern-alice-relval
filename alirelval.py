#!/bin/env python

#
# alirelval.py -- by Dario Berzano <dario.berzano@cern.ch>
#
# Controls automatic trigger of the ALICE Release Validation.
#

import sys, urllib, re
from prettytable import PrettyTable


AliRootPacksBaseUrl = 'http://pcalienbuild4.cern.ch:8889/tarballs'


def get_available_packages():
  '''Returns a list of available packages in AliEn. The list is obtained from
     the AliEn URL in AliRootPacksBaseUrl. Each element of the list is a
     dictionary containing the following mandatory fields:

      - tarballurl  : full download URL of the tarball
      - software    : the program, e.g. AliRoot or ROOT
      - version     : software's version, e.g. v5-03-Rev-23a
      - platform    : the platform (not the arch), e.g. Linux-x86_64
      - packagename : the name of the package, e.g. VO_ALICE@AliRoot::v12345
      - arch        : architecture, e.g. x86_64-2.6-gnu-4.1.2 (can be None)
      - packagedeps : array of dependencies, each in the same format as
                      packagename (can be None)

     Note that this function can throw an IOError.
  '''

  packlist = []
  resp = urllib.urlopen(AliRootPacksBaseUrl+'/Packages')
  for l in resp:
    try:
      a = l.strip().split('\t', 5)
      packdef = {
        'tarballurl':   a[0],
        'software':     a[1],
        'version':      a[2],
        'platform':     a[3],
        'packagename':  a[4]
      }

      if len(a) > 5:
        packdef['packagedeps'] = a[5].split(',')
      else:
        packdef['packagedeps'] = None

      i1 = packdef['tarballurl'].find( packdef['platform'] )
      i2 = packdef['tarballurl'].find( '.tar' )

      if i2 > i1:
        packdef['arch'] = packdef['tarballurl'][i1:i2]
      else:
        packdef['arch'] = None

      packdef['tarballurl'] = AliRootPacksBaseUrl + '/' + packdef['tarballurl']

      packlist.append(packdef)

    except IndexError:
      pass

  return packlist


def main(argv):

  try:
    packs = get_available_packages()
  except IOError as e:
    print 'Cannot read list of packages: %s' % e

  tab = PrettyTable( [ 'Package name', 'Arch', 'URL' ] )
  for k in tab.align.keys():
    tab.align[k] = 'l'
  tab.padding_width = 1
  for p in packs:
    tab.add_row([
      p['packagename'],
      p['arch'],
      p['tarballurl']
    ])

  print tab

if __name__ == '__main__':
  main(sys.argv[1:])
