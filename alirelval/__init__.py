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
from timestamp import TimeStamp
import time
from smtplib import SMTP


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
    'alirelval': {
      'logdir': ['path', '~/.alirelval/log'],
      'dbpath': ['path', '~/.alirelval/status.sqlite'],
      'pidfile': ['path', '~/.alirelval/pid'],
      'packbaseurl': ['str', 'http://pcalienbuild4.cern.ch:8889/tarballs'],
      'resultsurl': ['str', 'http://localhost/$SESSIONTAG'],
      'unpackdir': ['path', '/opt/alice/aliroot/export/arch/$ARCH/Packages/AliRoot/$VERSION'],
      'modulefile': ['path', '/opt/alice/aliroot/export/arch/$ARCH/Modules/modulefiles/AliRoot/$VERSION'],
      'unpackcmd': ['str', '/usr/bin/curl -L $URL | /usr/bin/tar --strip-components=1 -C $DESTDIR -xzvvf -'],
      'relvalcmd': ['str', '/bin/false'],
      'statuscmd': ['str', '/bin/false'],
      'statuscode_running': ['int', 100],
      'statuscode_notrunning': ['int', 101],
      'statuscode_doneok': ['int', 102],
      'statuscode_donefail': ['int', 103]
    },
    'mail': {
      'host': ['str', 'localhost'],
      'port': ['int', 25],
      'from': ['str', 'noreply@localhost'],
      'to': ['str', 'noreply1@localhost,noreply2@localhost']
    }
  }

  for sec in config_vars.keys():
    for c in config_vars[sec].keys():
      vartype = config_vars[sec][c][0]
      default = False
      try:
        if vartype == 'str' or vartype == 'path':
          config_vars[sec][c] = parser.get(sec, c)
        elif vartype == 'int':
          config_vars[sec][c] = parser.getint(sec, c)
        elif vartype == 'float':
          config_vars[sec][c] = parser.getfloat(sec, c)
        elif vartype == 'bool':
          config_vars[sec][c] = parser.getboolean(sec, c)
      except Exception:
        config_vars[sec][c] = config_vars[sec][c][1]
        default = True

      if vartype == 'path':
        config_vars[sec][c] = os.path.expanduser(config_vars[sec][c])
      if default:
        log.debug('%s.%s = %s (default)' % (sec, c, config_vars[sec][c]))
      else:
        log.debug('%s.%s = %s (from file)' % (sec, c, config_vars[sec][c]))

  return config_vars


def check_lock(pidfile):
  log = get_logger()
  attempts = 10
  for i in range(1,attempts+1):
    try:
      with open(pidfile, 'r') as pf:
        pid = int(pf.read())
      log.debug('pidfile says: %d' % pid)
      os.kill(pid, 0)
      log.warning('attempt %d of %d: another instance with pid %d is running' % (i, attempts, pid))
      time.sleep(1)
    except (IOError, ValueError, OSError):
      with open(pidfile, 'w') as pf:
        pid = os.getpid()
        pf.write( str(pid)+'\n' )
      log.debug('writing current pid %d in pidfile %s' % (pid, pidfile))
      return True
  log.critical('timeout waiting other instance to finish: aborting')
  return False


def unhandled_exception(type, value, tb):
  log = get_logger()
  log.critical('uncaught exception: %s' % str(value))
  log.critical('traceback (most recent call last):')
  for tbe in traceback.format_tb(tb):
    for l in tbe.split('\n'):
      if l != '':
        log.critical(l)


def run_command(cmd, verbose=None, nonzero_raise=False):
  '''Runs a command. Returns the return code. Silences output according to the
     current debug level (can be overridden). Can raise exception if cmd
     returns nonzero.
  '''
  log = get_logger()
  if verbose is None:
    verbose = log.getEffectiveLevel() <= logging.DEBUG  # note: logging.NOTSET == 0
  log.debug('executing command: %s' % cmd)
  if verbose:
    sp = subprocess.Popen(cmd, shell=True)
  else:
    with open(os.devnull) as dev_null:
     sp = subprocess.Popen(cmd, stderr=dev_null, stdout=dev_null, shell=True)
  rc = sp.wait()
  if rc != 0 and nonzero_raise:
    raise OSError('command "%s" had nonzero (%d) exit status' % (cmd, rc))
  else:
    return rc


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


def queue_validation(valstatus, baseurl, tarball, dryrun=False):
  log = get_logger()
  if tarball is None:
    log.debug('tarball not provided, waiting on stdin (terminate with EOF)...')
    inp = sys.stdin.read()
    tarball = inp.strip()
    log.debug('tarball to validate (from stdin): %s' % tarball)
  else:
    log.debug('tarball to validate: %s' % tarball)
  # package to validate (cache in sqlite)
  pack = valstatus.get_cached_pack_from_tarball(tarball, get_available_packages(baseurl, '/Packages-Validation'))
  if pack is None:
    log.error('package from tarball %s not found!' % tarball)
    return False
  else:
    print pack
    # queue validation
    if dryrun:
      log.info('DRY RUN: not queuing validation of %s' % pack.tarball)
    else:
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
    vals = valstatus.get_validations(status=ValStatus.status['NOT_RUNNING'])
  else:
    assert False, 'invalid parameter'
  for v in vals:
    print v
  return True


def start_next_queued_validation(valstatus, baseurl, unpackdir=None, modulefile=None, unpackcmd=None, relvalcmd=None, mail=None, dryrun=False):
  log = get_logger()
  for p in [unpackdir, modulefile, unpackcmd, relvalcmd, mail]:
    assert p is not None, 'invalid parameters'

  v = valstatus.get_oldest_queued_validation()
  if v is None:
    log.info('no validations queued: nothing to do')
    return True
  else:
    startedts = TimeStamp()
    varsubst = {
        'PLATFORM': v.package.platform,
        'ARCH': v.package.arch,
        'VERSION': v.package.version,
        'MODULEFILE_DEPS': ' '.join(v.package.deps).replace(v.package.org+'@', '').replace('::', '/'),
        'URL': v.package.get_url(),
        'SESSIONTAG': v.get_session_tag()
    }

    destdir = string.Template(unpackdir).safe_substitute(varsubst)
    varsubst['DESTDIR'] = destdir
    destdirexists = os.path.isdir(destdir)
    if v.package.fetched and destdirexists:
      log.info('package already unpacked in %s' % destdir)
    else:
      if not destdirexists:
        os.makedirs(destdir) # OSError
      cmd = string.Template(unpackcmd).safe_substitute(varsubst)
      log.info('downloading and unpacking %s (might take time)' % varsubst['URL'])
      if dryrun:
        log.info('DRY RUN: not running command %s' % cmd)
        v.package.fetched = True
      else:
        try:
          run_command(cmd, nonzero_raise=True)
        except OSError:
          log.error('error unpacking: cleaning up %s' % destdir)
          shutil.rmtree(destdir)
          raise
        log.info('unpacked in %s successfully' % varsubst['DESTDIR'])
        v.package.fetched = True
        valstatus.update_package(v.package)

    destmod = string.Template(modulefile).safe_substitute(varsubst)
    destmoddir = os.path.dirname(destmod)
    if not dryrun and not os.path.isdir(destmoddir):
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

    if not dryrun:
      with open(destmod, 'w') as f:
        f.write(destmodcontent)
      log.info('modulefile %s written' % destmod)
    else:
      log.info('DRY RUN: not writing modulefile, outputting it on screen')
    print destmodcontent

    cmd = string.Template(relvalcmd).safe_substitute(varsubst)
    if not dryrun:
      log.info('running validation command')
      run_command(cmd, nonzero_raise=True)
    else:
      log.info('DRY RUN: not running validation command')

    v.started = startedts
    v.status = ValStatus.status['RUNNING']
    if not dryrun:
      valstatus.update_validation(v)

    varsubst['VALIDATION_STR'] = str(v)
    send_mail(
      host=mail['host'],
      port=mail['port'],
      sender=mail['from'],
      to=mail['to'].split(','),
      subject='[AliRelVal] Validation started: $VERSION',
      message='The following validation has started:\n\n$VALIDATION_STR',
      varsubst=varsubst )

  return True


def refresh_validations(valstatus, statuscmd=None, statusmap=None, resultsurl=None, mail=None, dryrun=False):
  log = get_logger()
  for p in [statuscmd, statusmap, resultsurl, mail]:
    assert p is not None, 'invalid parameters'
  for v in valstatus.get_validations(status=ValStatus.status['RUNNING']):
    varsubst = {
        'PLATFORM': v.package.platform,
        'ARCH': v.package.arch,
        'VERSION': v.package.version,
        'SESSIONTAG': v.get_session_tag()
    }
    varsubst['RESULTS_URL'] = string.Template(resultsurl).safe_substitute(varsubst)
    cmd = string.Template(statuscmd).safe_substitute(varsubst)
    log.debug('querying status for %s' % varsubst['SESSIONTAG'])
    rc = run_command(cmd)
    status_str = None
    status_num = None
    for s in statusmap.keys():
      if statusmap[s] == rc:
        status_str = s
        status_num = ValStatus.status[status_str]
        break
    if status_num == ValStatus.status['RUNNING']:
      log.debug('status of %s unchanged, still RUNNING' % varsubst['SESSIONTAG'])
    elif status_num == ValStatus.status['DONE_OK'] or status_num == ValStatus.status['DONE_FAIL']:
      log.info('status of %s: RUNNING -> %s' % (varsubst['SESSIONTAG'], status_str))
      v.ended = TimeStamp()
      v.status = status_num
      if not dryrun:
        valstatus.update_validation(v)
      else:
        log.info('DRY RUN: not updating validation status')

      if status_num == ValStatus.status['DONE_OK']:
        varsubst['STATUS_STR'] = 'OK'
      else:
        varsubst['STATUS_STR'] = 'failed'
      varsubst['VALIDATION_STR'] = str(v)
      send_mail(
        host=mail['host'],
        port=mail['port'],
        sender=mail['from'],
        to=mail['to'].split(','),
        subject='[AliRelVal] Validation $STATUS_STR: $VERSION',
        message='''Validation for $VERSION: $STATUS_STR.

Find the results here:

  $RESULTS_URL

Validation details:

$VALIDATION_STR''',
        varsubst=varsubst )

    elif status_num == ValStatus.status['NOT_RUNNING']:
      log.error('status of %s appears to be RUNNING -> NOT_RUNNING: something went wrong, skipping')
    if status_num is None:
      log.warning('unknown value (%d) returned when checking status of %s: skipping' % (rc,varsubst['SESSIONTAG']))
  return True


def send_mail(host, port, sender, to, subject, message, varsubst={}):
  log = get_logger()
  log.debug('sending email')
  message = '''From: %s
To: %s
Subject: %s

%s''' % (sender, ', '.join(to), subject, message)
  m = string.Template(message).safe_substitute(varsubst)
  try:
    mailer = SMTP(host, port)
    mailer.sendmail(sender, to, m)
  except Exception as e:
    log.error('cannot send notification email: %s' % e)


def main(argv):

  init_logger(log_directory=None, debug=False)
  log = get_logger()
  sys.excepthook = unhandled_exception

  debug = False
  tarball = None
  extended = False
  dryrun = False

  try:
    opts, remainder = gnu_getopt(argv, '', [ 'debug', 'tarball=', 'extended', 'dryrun' ])
    for o, a in opts:
      if o == '--debug':
        debug = True
      elif o == '--tarball':
        tarball = a
      elif o == '--extended':
        extended = True
      elif o == '--dryrun':
        dryrun = True
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
  init_logger( log_directory=cfg['alirelval']['logdir'], debug=debug )

  if not check_lock(cfg['alirelval']['pidfile']):
    return 1

  # init the database
  valstatus = ValStatus(dbpath=cfg['alirelval']['dbpath'], baseurl=cfg['alirelval']['packbaseurl'])

  # what to do
  if action == 'list-pub-packages':
    s = list_packages(cfg['alirelval']['packbaseurl'], what=what_pack['PUBLISHED'], extended=extended)
  elif action == 'list-val-packages':
    s = list_packages(cfg['alirelval']['packbaseurl'], what=what_pack['VALIDATION'], extended=extended)
  elif action == 'list-known-packages':
    s = list_packages(cfg['alirelval']['packbaseurl'], what=what_pack['CACHED'], extended=extended, valstatus=valstatus)
  elif action == 'list-validations':
    s = list_validations(valstatus, what=what_val['ALL'])
  elif action == 'list-queued-validations':
    s = list_validations(valstatus, what=what_val['QUEUED'])
  elif action == 'queue-validation':
    s = queue_validation(valstatus, cfg['alirelval']['packbaseurl'], tarball, dryrun=dryrun)
  elif action == 'start-next-queued-validation':
    s = start_next_queued_validation(valstatus, cfg['alirelval']['packbaseurl'], unpackdir=cfg['alirelval']['unpackdir'], modulefile=cfg['alirelval']['modulefile'], unpackcmd=cfg['alirelval']['unpackcmd'], relvalcmd=cfg['alirelval']['relvalcmd'], mail=cfg['mail'], dryrun=dryrun)
  elif action == 'refresh-validations':
    statusmap = {
      'RUNNING': cfg['alirelval']['statuscode_running'],
      'NOT_RUNNING': cfg['alirelval']['statuscode_notrunning'],
      'DONE_OK': cfg['alirelval']['statuscode_doneok'],
      'DONE_FAIL': cfg['alirelval']['statuscode_donefail']
    }
    s = refresh_validations(valstatus, statuscmd=cfg['alirelval']['statuscmd'], statusmap=statusmap, resultsurl=cfg['alirelval']['resultsurl'], mail=cfg['mail'], dryrun=dryrun)
  else:
    log.error('wrong action')
    s = False

  try:
    log.debug('removing pidfile %s' % cfg['alirelval']['pidfile'])
    os.remove(cfg['alirelval']['pidfile'])
  except OSError:
    pass

  if s:
    return 0

  return 1
