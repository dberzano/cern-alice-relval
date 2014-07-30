#
# alirelval -- by Dario Berzano <dario.berzano@cern.ch>
#
# Controls automatic trigger of the ALICE Release Validation.
#

import sys, os, urllib
from prettytable import PrettyTable
from alipack import AliPack, AliPackError
import logging, logging.handlers


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


def init_logger(log_directory):
  format = '%(asctime)s [%(name)s.%(funcName)s] %(levelname)s %(message)s'
  datefmt = '%Y-%m-%d %H:%M:%S'
  # CRITICAL=50, ERROR=40, WARNING=30, INFO=20, DEBUG=10, NOTSET=0
  level = logging.DEBUG

  # log to console
  logging.basicConfig(level=level, format=format, datefmt=datefmt, stream=sys.stderr)

  # log to file as well
  if log_directory is not None:
    filename = '%s/alirelval.log' % log_directory

    if not os.path.isdir(log_directory):
      os.makedirs(log_directory, 0755)

    log_file = logging.handlers.RotatingFileHandler(filename, mode='a', maxBytes=1000000, backupCount=30)
    log_file.setLevel(level)
    log_file.setFormatter( logging.Formatter(format, datefmt) )
    logging.getLogger('').addHandler(log_file)
    #log_file.doRollover()  # rotate now: start from a clean slate
    return filename

  return None


def main(argv):

  init_logger( os.path.expanduser('~/alirelval') )

  log = logging.getLogger('alirelval')
  log.info('ALICE Release Validation trigger started')

  try:
    packs = get_available_packages()
  except IOError as e:
    log.error('cannot read list of packages: %s' % e)
    return 1

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
