import sqlite3
import logging
from alipack import AliPack, AliPackError
from timestamp import TimeStamp

def sqlite3_dict_factory(cursor, row):
  d = {}
  for idx, col in enumerate(cursor.description):
      d[col[0]] = row[idx]
  return d

class ValStatus:

  status = {
    'RUNNING': 0,
    'NOT_RUNNING': 1,
    'DONE_OK': 2,
    'DONE_FAIL': 3
  }

  def __init__(self, dbpath=None, baseurl=None):
    if dbpath is None or baseurl is None:
      raise ValStatusError('dbpath and baseurl are mandatory')
    self._dbpath = dbpath
    self._baseurl = baseurl
    self._log = logging.getLogger('ValStatus')
    self._log.debug('opening SQLite3 database %s' % dbpath)
    self._db = sqlite3.connect(dbpath)
    self._db.row_factory = sqlite3_dict_factory
    cursor = self._db.cursor()
    cursor.execute('''
      CREATE TABLE IF NOT EXISTS package(
        package_id INTEGER PRIMARY KEY AUTOINCREMENT,
        tarball    TEXT UNIQUE NOT NULL,
        software   TEXT NOT NULL,
        org        TEXT NOT NULL,
        version    TEXT NOT NULL,
        platform   TEXT,
        arch       TEXT,
        deps       TEXT,
        fetched    INT NOT NULL DEFAULT 0
      )
    ''')
    cursor.execute('''
      CREATE TABLE IF NOT EXISTS validation(
        validation_id INTEGER PRIMARY KEY AUTOINCREMENT,
        inserted      INTEGER NOT NULL,
        started       INTEGER,
        ended         INTEGER,
        status        INTEGER NOT NULL,
        package_id    INTEGER NOT NULL,
        FOREIGN KEY(package_id) REFERENCES package(package_id)
      )
    ''')
    cursor.execute('PRAGMA foreign_keys = ON') # not sure
    self._db.commit()
    #self._db.close()

  def get_cached_pack_from_tarball(self, tarball, alipacks):
    cursor = self._db.cursor()
    cursor.execute('SELECT * FROM package WHERE tarball=? LIMIT 1', (tarball,))
    result = cursor.fetchone()
    if result is None:
      self._log.debug('could not find package in db: searching in the remote list')
      pack = None
      for ap in alipacks:
        if ap.tarball == tarball:
          pack = ap
          self._log.debug('found package: %s, inserting into database' % pack.get_package_name())
          packid = self._add_package_cache(pack)
          self._log.debug('package inserted in db with id %d' % packid)
          pack.id = packid
          break
      if pack is None:
        self._log.debug('package not found')
    else:
      packid = result['package_id']
      self._log.debug('package found in db with id %d' % packid)
      pack = AliPack(dictionary=result, baseurl=self._baseurl)
    return pack

  def get_packages(self):
    cursor = self._db.cursor()
    cursor.execute('SELECT * FROM package')
    packs = []
    for r in cursor:
      packs.append( AliPack(dictionary=r, baseurl=self._baseurl) )
    return packs

  def get_validations(self, status=None):
    cursor = self._db.cursor()
    if status is not None:
      where = 'WHERE status = %d' % status
    else:
      where = ''
    self._log.debug('querying for validations (status=%s)' % status)
    cursor.execute('SELECT * FROM validation JOIN package ON package.package_id=validation.package_id %s ORDER BY inserted ASC' % where)
    vals = []
    for r in cursor:
      vals.append( Validation(dictionary=r, baseurl=self._baseurl) )
    return vals

  def get_oldest_queued_validation(self):
    cursor = self._db.cursor()
    status = self.status['NOT_RUNNING']
    cursor.execute('SELECT * FROM validation JOIN package ON package.package_id=validation.package_id WHERE status = ? ORDER BY inserted ASC LIMIT 1', (status,))
    r = cursor.fetchone()
    if r is None:
      return None
    return Validation(dictionary=r, baseurl=self._baseurl)

  def _add_package_cache(self, pack):
    cursor = self._db.cursor()
    cursor.execute('''
      INSERT INTO package(tarball,software,version,platform,arch,org,deps)
      VALUES(?,?,?,?,?,?,?)
    ''',
    (pack.tarball, pack.software, pack.version, pack.platform, pack.arch, pack.org, ','.join(pack.deps)))
    self._db.commit()
    self._log.debug('package %s inserted successfully with id %d' % (pack.get_package_name(), cursor.lastrowid))
    return cursor.lastrowid

  def add_validation(self, pack):
    cursor = self._db.cursor()
    inserted = TimeStamp()
    status = self.status['NOT_RUNNING']
    cursor.execute('SELECT package_id FROM package WHERE tarball=?', (pack.tarball,))
    package_id = cursor.fetchone()['package_id']  # ValueError
    self._log.debug('found id %d for %s' % (package_id, pack.tarball))
    # if a validation for that package which is NOT_RUNNING or RUNNING already exists, don't insert
    cursor.execute('''
      INSERT INTO validation(inserted,status,package_id)
      SELECT ?,?,?
      WHERE NOT EXISTS (
        SELECT 1 FROM validation WHERE package_id=? AND ( status == ? OR status == ? )
      )
    ''', (inserted.get_timestamp_usec_utc(), status, package_id, package_id, self.status['NOT_RUNNING'], self.status['RUNNING']))
    self._db.commit()
    if cursor.lastrowid == 0:
      self._log.debug('validation for %s already queued or in progress' % pack.tarball)
      return False
    else:
      self._log.debug('validation for %s queued with id %d' % (pack.tarball,cursor.lastrowid))
      return True

  def update_validation(self, val):
    cursor = self._db.cursor()
    if val.started is None:
      started = None
      ended = None
    elif val.ended is not None:
      started = val.started.get_timestamp_usec_utc()
      ended = val.ended.get_timestamp_usec_utc()
    else:
      started = val.started.get_timestamp_usec_utc()
      ended = None
    self._log.debug('updating validation %s' % val.get_session_tag())
    cursor.execute('''
      UPDATE validation SET inserted=?,started=?,ended=?,status=?,package_id=(
        SELECT package_id FROM package WHERE tarball=? LIMIT 1
      ) WHERE validation_id=?
    ''', (val.inserted.get_timestamp_usec_utc(), started, ended, val.status, val.package.tarball, val.id))
    self._db.commit()
    if cursor.rowcount == 0:
      raise ValStatusError('cannot update: validation not in database')
    self._log.debug('validation updated')

  def update_package(self, pack):
    cursor = self._db.cursor()
    if pack.fetched:
      fetched = 1
    else:
      fetched = 0
    self._log.debug('updating package cache for %s' % pack.tarball)
    cursor.execute('''
      UPDATE package
      SET tarball=?,software=?,version=?,platform=?,arch=?,org=?,deps=?,fetched=?
      WHERE package_id=?
    ''',
    (pack.tarball, pack.software, pack.version, pack.platform, pack.arch, pack.org,
      ','.join(pack.deps), fetched, pack.id))
    self._db.commit()
    if cursor.rowcount == 0:
      raise ValStatusError('cannot update: package not in database')
    self._log.debug('package cache updated')


class ValStatusError(Exception):
  pass


class Validation:

  def __init__(self, dictionary=None, baseurl=None):
    if dictionary is None or baseurl is None:
      raise ValidationError('all parameters are mandatory')
    self._from_dict(dictionary, baseurl)

  def __str__(self):
    status = '<unknown>'
    for k in ValStatus.status.keys():
      if ValStatus.status[k] == self.status:
        status = k
    if self.started is None:
      started = '<not started>'
      ended = started
      timetaken = started
    elif self.ended is not None:
      started = self.started
      ended = self.ended
      timetaken = ended-started
    else:
      started = self.started
      ended = '<not completed>'
      timetaken = ended
    package = str(self.package).replace('\n', '\n   ')
    return \
      'Validation:\n' \
      ' - Id       : %d\n' \
      ' - Added    : %s\n' \
      ' - Started  : %s\n' \
      ' - Ended    : %s\n' \
      ' - Delta    : %s\n' \
      ' - Status   : %s\n' \
      ' - %s' \
      % (self.id, self.inserted, started, ended, timetaken, status, package)

  def _from_dict(self, dictionary, baseurl):
    self.id = dictionary['validation_id']
    self.inserted = TimeStamp( dictionary['inserted'] )
    if dictionary['started'] is not None:
      self.started = TimeStamp( dictionary['started'] )
    else:
      self.started = None
    if dictionary['ended'] is not None:
      self.ended = TimeStamp( dictionary['ended'] )
    else:
      self.ended = None
    self.status = dictionary['status']
    self.package_id = dictionary['package_id']
    self.package = AliPack(baseurl=baseurl, dictionary=dictionary)

  def get_session_tag(self):
    return '%s-%s-%s-%s-utc' % (self.package.version, self.package.platform,
      self.package.arch, self.inserted.get_formatted_str('%Y%m%d-%H%M%S'))


class ValidationError(Exception):
  pass
