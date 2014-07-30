import sqlite3
import logging
from alipack import AliPack, AliPackError

def sqlite3_dict_factory(cursor, row):
  d = {}
  for idx, col in enumerate(cursor.description):
      d[col[0]] = row[idx]
  return d

class ValStatus:

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
    self._db.commit()
    #self._db.close()

  def get_pack_from_tarball(self, tarball):
    cursor = self._db.cursor()
    cursor.execute('SELECT * FROM package WHERE tarball=? LIMIT 1', (tarball,))
    result = cursor.fetchone()
    if result is None:
      self._log.debug('could not find package in db')
    else:
      self._log.debug('package found in db')
      return AliPack(dictionary=result, baseurl=self._baseurl)

  def get_packages(self):
    cursor = self._db.cursor()
    cursor.execute('SELECT * FROM package')
    packs = []
    for r in cursor:
      packs.append( AliPack(dictionary=r, baseurl=self._baseurl) )
    return packs

class ValStatusError(Exception):
  pass
