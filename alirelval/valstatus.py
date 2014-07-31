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
        arch       TEXT NOT NULL,
        deps       TEXT
      )
    ''')
    cursor.execute('''
      CREATE TABLE IF NOT EXISTS validation(
        validation_id INTEGER PRIMARY KEY AUTOINCREMENT,
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

  def get_pack_from_tarball(self, tarball, alipacks):
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
          self.add_package(pack)
          break
    else:
      self._log.debug('package found in db')
      pack = AliPack(dictionary=result, baseurl=self._baseurl)
    return pack

  def get_packages(self):
    cursor = self._db.cursor()
    cursor.execute('SELECT * FROM package')
    packs = []
    for r in cursor:
      packs.append( AliPack(dictionary=r, baseurl=self._baseurl) )
    return packs

  def get_validations(self):
    cursor = self._db.cursor()
    cursor.execute('SELECT * FROM validation AUTO JOIN package')
    vals = []
    for r in cursor:
      vals.append( Validation(dictionary=r) )
    return vals

  def add_package(self, pack):
    cursor = self._db.cursor()
    cursor.execute('''
      INSERT INTO package(tarball,software,version,arch,org,deps)
      VALUES(?,?,?,?,?,?)
    ''',
    (pack.tarball, pack.software, pack.version, pack.arch, pack.org, ','.join(pack.deps)))
    self._db.commit()
    self._log.debug('package %s inserted successfully with id %d' % (pack.get_package_name(), cursor.lastrowid))
    return cursor.lastrowid


class ValStatusError(Exception):
  pass


class Validation:

  def __init__(self, dictionary=None):
    if dictionary is None:
      raise ValidationError('dictionary is mandatory')
    self._from_dict(dictionary)

  def __str__(self):
    status = '<unknown>'
    for k in ValStatus.status.keys():
      if ValStatus.status[k] == self.status:
        status = k
    if self.ended is None:
      ended = '<not completed>'
      timetaken = ended
    else:
      ended = self.ended
      timetaken = str(self.ended - self.started)
    return \
      'Validation #%d:\n' \
      ' - Started  : %s\n' \
      ' - Ended    : %s\n' \
      ' - Delta    : %s\n' \
      ' - Status   : %s\n' \
      ' - PackId   : %d\n' \
      '%s' \
      % (self.id, self.started, ended, timetaken, status, self.package_id, self.package)

  def _from_dict(self, dictionary):
    self.id = dictionary['validation_id']
    self.started = TimeStamp( dictionary['started'] )
    if dictionary['ended'] is not None:
      self.ended = TimeStamp( dictionary['ended'] )
    else:
      self.ended = None
    self.status = dictionary['status']
    self.package_id = dictionary['package_id']
    self.package = AliPack(baseurl='', dictionary=dictionary)


class ValidationError(Exception):
  pass
