#
# alirelval -- by Dario Berzano <dario.berzano@cern.ch>
#
# Controls automatic trigger of the ALICE Release Validation.
#

import sys, os, urllib
from prettytable import PrettyTable
from alipack import AliPack, AliPackError
import logging, logging.handlers
import ConfigParser
from getopt import getopt, GetoptError


def get_available_packages(baseurl):
  '''Returns a list of available packages in AliEn. The list is obtained from
     the given URL.
  '''

  packlist = []
  resp = urllib.urlopen(baseurl+'/Packages')
  for l in resp:
    try:
      packdef = AliPack(l, baseurl)
      packlist.append(packdef)
    except AliPackError as e:
      print 'skipping one package: %s' % e
      pass

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
    'logdir': ['str', '~/.alirelval/log'],
    'db': ['str', '~/.alirelval/status.sqlite'],
    'packbaseurl': ['str', 'http://pcalienbuild4.cern.ch:8889/tarballs']
  }

  for c in config_vars.keys():
    try:
      if config_vars[c][0] == 'str':
        config_vars[c] = parser.get(sec, c)
      elif config_vars[c][0] == 'int':
        config_vars[c] = parser.getint(sec, c)
      elif config_vars[c][0] == 'float':
        config_vars[c] = parser.getfloat(sec, c)
      elif config_vars[c][0] == 'bool':
        config_vars[c] = parser.getboolean(sec, c)
    except Exception:
      config_vars[c] = config_vars[c][1]
      log.debug('%s.%s = %s (default)' % (sec, c, config_vars[c]))
    log.debug('%s.%s = %s (from file)' % (sec, c, config_vars[c]))

  return config_vars

def list_packages(baseurl):
  log = get_logger()
  try:
    packs = get_available_packages(baseurl)
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


def main(argv):

  init_logger(log_directory=None, debug=False)
  log = get_logger()

  debug = False

  try:
    opts, remainder = getopt(argv, 'a:bc', [ 'debug', 'dummy2', 'dummy3' ])
    for o, a in opts:
      if o == '--debug':
        debug = True
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
  init_logger( log_directory=os.path.expanduser(cfg['logdir']), debug=debug )

  # what to do
  if action == 'list-packages':
    list_packages(cfg['packbaseurl'])

  return 0
