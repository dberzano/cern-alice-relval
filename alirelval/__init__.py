#
# alirelval -- by Dario Berzano <dario.berzano@cern.ch>
#
# Controls automatic trigger of the ALICE Release Validation.
#

import sys, urllib
from prettytable import PrettyTable
from alipack import AliPack, AliPackError


ALI_BASE_PACK_URL = 'http://pcalienbuild4.cern.ch:8889/tarballs'


def get_available_packages():
  '''Returns a list of available packages in AliEn. The list is obtained from
     the AliEn URL in ALI_BASE_PACK_URL.
  '''

  packlist = []
  resp = urllib.urlopen(ALI_BASE_PACK_URL+'/Packages')
  for l in resp:
    try:
      packdef = AliPack(l, ALI_BASE_PACK_URL)
      packlist.append(packdef)
    except AliPackError as e:
      print 'skipping one package: %s' % e
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
      p.get_package_name(),
      p.arch,
      p.get_url()
    ])

  print tab
  return 0
