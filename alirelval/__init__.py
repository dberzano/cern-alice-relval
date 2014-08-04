#
# alirelval -- by Dario Berzano <dario.berzano@cern.ch>
#
# Controls automatic trigger of the ALICE Release Validation.
#

import sys, os, urllib
from prettytable import PrettyTable
from alipack import AliPack, AliPackError
from valstatus import ValStatus
import logging, logging.handlers
import ConfigParser
from getopt import gnu_getopt, GetoptError
import sqlite3


def get_available_packages(baseurl, listpath='/Packages'):
  '''Returns a list of available packages in AliEn. The list is obtained from
     the given URL.
  '''

  log = get_logger()
  log.debug('getting list of available packages from %s%s' % (baseurl, listpath))
  packlist = []
  resp = urllib.urlopen(baseurl+listpath)
  if resp.getcode() != 200:
    raise IOError('code %d while reading %s%s' % (resp.getcode(), baseurl, listpath))
  for l in resp:
    try:
      packdef = AliPack(rawstring=l, baseurl=baseurl)
      packlist.append(packdef)
    except AliPackError as e:
      log.warning('quietly skipping unparsable package definition: %s' % e)
      pass
  log.debug('created list of %d package(s)' % len(packlist))
  return packlist


def get_logger():
  return logging.getLogger('alirelval')


def init_logger(log_directory=None, debug=False):
  format = '%(asctime)s [%(name)s.%(funcName)s] %(levelname)s %(message)s'
  datefmt = '%Y-%m-%d %H:%M:%S'

  # CRITICAL=50, ERROR=40, WARNING=30, INFO=20, DEBUG=10, NOTSET=0
  if debug:
    level = logging.DEBUG
  else:
    level = logging.INFO

  # configure the root logger
  logging.basicConfig(format=format, datefmt=datefmt, stream=sys.stderr)
  logging.getLogger('').setLevel(level)

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


def init_config(config_file):
  log = get_logger()
  parser = ConfigParser.SafeConfigParser()
  parser.read(config_file)
  sec = 'alirelval'

  # 'key': ['type', default]
  config_vars = {
    'logdir': ['path', '~/.alirelval/log'],
    'dbpath': ['path', '~/.alirelval/status.sqlite'],
    'packbaseurl': ['str', 'http://pcalienbuild4.cern.ch:8889/tarballs']
  }

  for c in config_vars.keys():
    vartype = config_vars[c][0]
    try:
      if vartype == 'str' or vartype == 'path':
        config_vars[c] = parser.get(sec, c)
      elif vartype == 'int':
        config_vars[c] = parser.getint(sec, c)
      elif vartype == 'float':
        config_vars[c] = parser.getfloat(sec, c)
      elif vartype == 'bool':
        config_vars[c] = parser.getboolean(sec, c)
    except Exception:
      config_vars[c] = config_vars[c][1]
      default = True

    if vartype == 'path':
      config_vars[c] = os.path.expanduser(config_vars[c])
    if default:
      log.debug('%s.%s = %s (default)' % (sec, c, config_vars[c]))
    else:
      log.debug('%s.%s = %s (from file)' % (sec, c, config_vars[c]))

  return config_vars

list_what = {
  'CACHED':     0,
  'VALIDATION': 1,
  'PUBLISHED':  2
}
def list_packages(baseurl, what, extended=False, valstatus=None):
  log = get_logger()
  if what == list_what['CACHED']:
    packs = valstatus.get_packages()
  elif what == list_what['PUBLISHED']:
    packs = get_available_packages(baseurl) # IOError
  elif what == list_what['VALIDATION']:
    packs = get_available_packages(baseurl, '/Packages-Validation')
  else:
    assert False, 'invalid parameter'
  if extended:
    for p in packs:
      print p
  else:
    tab = PrettyTable( [ 'Package', 'Arch', 'URL' ] )
    for k in tab.align.keys():
      tab.align[k] = 'l'
    tab.padding_width = 1
    for p in packs:
      if p.deps is None:
        deps = '<none>'
      else:
        deps = ', '.join(p.deps)
      tab.add_row([
        p.get_package_name(),
        p.arch,
        deps
      ])
    print tab
  return True


def queue_validation(valstatus, baseurl, tarball):
  log = get_logger()
  if tarball is None:
    log.debug('tarball not provided, waiting on stdin (terminate with EOF)...')
    inp = sys.stdin.read()
    tarball = inp.strip()
    log.debug('tarball to validate (from stdin): %s' % tarball)
  else:
    log.debug('tarball to validate: %s' % tarball)
  # package to validate (cache in sqlite)
  pack = valstatus.get_cached_pack_from_tarball(tarball, get_available_packages(baseurl))
  if pack is None:
    log.error('package from tarball %s not found!' % tarball)
    return False
  else:
    print pack
    # queue validation
    if valstatus.add_validation(pack):
      log.info('queued validation of %s' % pack.tarball)
    else:
      log.warning('validation of %s already queued' % pack.tarball)
    return True


def list_validations(valstatus):
  for v in valstatus.get_validations():
    print v
  return True


def start_queued_validations(valstatus, baseurl):
  log = get_logger()
  log.debug('ok')
  return True


def main(argv):

  init_logger(log_directory=None, debug=False)
  log = get_logger()

  debug = False
  tarball = None
  extended = False

  try:
    opts, remainder = gnu_getopt(argv, '', [ 'debug', 'tarball=', 'extended' ])
    for o, a in opts:
      if o == '--debug':
        debug = True
      elif o == '--tarball':
        tarball = a
      elif o == '--extended':
        extended = True
  except GetoptError as e:
    log.error('error parsing options: %s' % e)
    return 1

  try:
    action = remainder[0]
  except IndexError:
    log.error('please specify an action')
    return 1

  # read configuration and re-init logger
  if debug:
    init_logger(log_directory=None, debug=True)
  cfg = init_config( os.path.expanduser('~/.alirelval/alirelval.conf') )
  init_logger( log_directory=cfg['logdir'], debug=debug )

  # init the database
  valstatus = ValStatus(dbpath=cfg['dbpath'], baseurl=cfg['packbaseurl'])

  # what to do
  if action == 'list-pub-packages':
    s = list_packages(cfg['packbaseurl'], what=list_what['PUBLISHED'], extended=extended)
  if action == 'list-val-packages':
    s = list_packages(cfg['packbaseurl'], what=list_what['VALIDATION'], extended=extended)
  elif action == 'list-known-packages':
    s = list_packages(cfg['packbaseurl'], what=list_what['CACHED'], extended=extended, valstatus=valstatus)
  elif action == 'list-validations':
    s = list_validations(valstatus)
  elif action == 'queue-validation':
    s = queue_validation(valstatus, cfg['packbaseurl'], tarball)
  elif action == 'start-queued-validations':
    s = start_queued_validations(valstatus, cfg['packbaseurl'])
  else:
    log.error('wrong action')
    return 1

  if s:
    return 0

  return 1
