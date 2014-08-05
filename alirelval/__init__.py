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
import string
import subprocess
import traceback
import shutil


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
    'packbaseurl': ['str', 'http://pcalienbuild4.cern.ch:8889/tarballs'],
    'unpackdir': ['path', '/opt/alice/aliroot/export/arch/$ARCH/Packages/AliRoot/$VERSION'],
    'modulefile': ['path', '/opt/alice/aliroot/export/arch/$ARCH/Modules/modulefiles/AliRoot/$VERSION'],
    'unpackcmd': ['str', '/usr/bin/curl -L $URL | /usr/bin/tar --strip-components=1 -C $DESTDIR -xzvvf -']
  }

  for c in config_vars.keys():
    vartype = config_vars[c][0]
    default = False
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


def unhandled_exception(type, value, tb):
  log = get_logger()
  log.critical('uncaught exception: %s' % str(value))
  log.critical('traceback (most recent call last):')
  for tbe in traceback.format_tb(tb):
    for l in tbe.split('\n'):
      if l != '':
        log.critical(l)


what_pack = {
  'CACHED':     0,
  'VALIDATION': 1,
  'PUBLISHED':  2
}
def list_packages(baseurl, what, extended=False, valstatus=None):
  log = get_logger()
  if what == what_pack['CACHED']:
    packs = valstatus.get_packages()
  elif what == what_pack['PUBLISHED']:
    packs = get_available_packages(baseurl) # IOError
  elif what == what_pack['VALIDATION']:
    packs = get_available_packages(baseurl, '/Packages-Validation') # IOError
  else:
    assert False, 'invalid parameter'
  if extended:
    for p in packs:
      print p
  else:
    tab = PrettyTable( [ 'Package', 'Platform', 'Arch', 'URL' ] )
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
        p.platform,
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


what_val = {
  'ALL': 0,
  'QUEUED': 1
}
def list_validations(valstatus, what):
  if what == what_val['ALL']:
    vals = valstatus.get_validations()
  elif what == what_val['QUEUED']:
    vals = valstatus.get_queued_validations()
  else:
    assert False, 'invalid parameter'
  for v in vals:
    print v
  return True


def start_queued_validations(valstatus, baseurl, unpackdir=None, modulefile=None, unpackcmd=None):
  log = get_logger()
  assert unpackdir is not None and modulefile is not None and unpackcmd is not None, 'invalid parameters'
  for v in valstatus.get_queued_validations():

    varsubst = {
        'ARCH': v.package.arch,
        'VERSION': v.package.version,
        'MODULEFILE_DEPS': ' '.join(v.package.deps).replace(v.package.org+'@', '').replace('::', '/'),
        'URL': v.package.get_url()
    }

    destdir = string.Template(unpackdir).safe_substitute(varsubst)
    varsubst['DESTDIR'] = destdir
    if os.path.isdir(destdir):
      log.debug('not downloading and unpacking: directory %s already exists' % destdir)
    else:
      os.makedirs(destdir) # OSError
      cmd = string.Template(unpackcmd).safe_substitute(varsubst)
      log.debug('executing fetch+untar command: %s' % cmd)
      try:
        sp = subprocess.Popen(cmd, shell=True)
        rc = sp.wait()
        if rc != 0:
          raise OSError('command "%s" had nonzero (%d) exit status' % (cmd, rc))
      except OSError:
        log.error('error unpacking: cleaning up %s' % destdir)
        shutil.rmtree(destdir)
        raise

    destmod = string.Template(modulefile).safe_substitute(varsubst)
    destmoddir = os.path.dirname(destmod)
    if not os.path.isdir(destmoddir):
      os.makedirs(destmoddir) # OSError

    log.debug('preparing module file %s' % destmod)
    destmodcontent = string.Template('''#%Module1.0
proc ModulesHelp { } {
  global version
  puts stderr "This module is for an AliRoot version to be validated."
}
set version $VERSION
module-whatis "AliRoot version to be validated"
module load BASE/1.0 $MODULEFILE_DEPS
setenv ALIROOT_VERSION $version
setenv ALICE $::env(BASEDIR)/AliRoot
setenv ALIROOT_RELEASE $::env(ALIROOT_VERSION)
setenv ALICE_ROOT $::env(BASEDIR)/AliRoot/$::env(ALIROOT_RELEASE)
prepend-path PATH $::env(ALICE_ROOT)/bin/tgt_$::env(ALICE_TARGET_EXT)
prepend-path LD_LIBRARY_PATH $::env(ALICE_ROOT)/lib/tgt_$::env(ALICE_TARGET_EXT)
''').safe_substitute(varsubst)

    with open(destmod, 'w') as f:
      f.write(destmodcontent)

    break # debug
  return True


def main(argv):

  init_logger(log_directory=None, debug=False)
  log = get_logger()
  sys.excepthook = unhandled_exception

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
    s = list_packages(cfg['packbaseurl'], what=what_pack['PUBLISHED'], extended=extended)
  elif action == 'list-val-packages':
    s = list_packages(cfg['packbaseurl'], what=what_pack['VALIDATION'], extended=extended)
  elif action == 'list-known-packages':
    s = list_packages(cfg['packbaseurl'], what=what_pack['CACHED'], extended=extended, valstatus=valstatus)
  elif action == 'list-validations':
    s = list_validations(valstatus, what=what_val['ALL'])
  elif action == 'list-queued-validations':
    s = list_validations(valstatus, what=what_val['QUEUED'])
  elif action == 'queue-validation':
    s = queue_validation(valstatus, cfg['packbaseurl'], tarball)
  elif action == 'start-queued-validations':
    s = start_queued_validations(valstatus, cfg['packbaseurl'], unpackdir=cfg['unpackdir'], modulefile=cfg['modulefile'], unpackcmd=cfg['unpackcmd'])
  else:
    log.error('wrong action')
    return 1

  if s:
    return 0

  return 1
