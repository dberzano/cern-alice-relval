class AliPack:

  def __init__(self, rawstring, base_url):
    self._from_str(rawstring, base_url)

  def get_package_name(self):
    return '%s@%s::%s' % (self.org, self.software, self.version)

  def get_url(self):
    return '%s/%s' % ( self._baseurl, self.tarball )

  def _from_str(self, rawstring, base_url):
    '''Constructs the package definition from a string. String's format is the
       same as lines here: http://pcalienbuild4.cern.ch:8889/tarballs/Packages
    '''
    try:

      rawstring = rawstring.strip()
      a = rawstring.split(None, 5)

      self.tarball  = a[0]
      self.software = a[1]
      self.version  = a[2]
      self.platform = a[3]

      i2 = a[4].find('@')
      if i2 < 0:
        raise AliPackError('cannot find package organization: %s' % rawstring)
      self.org = a[4][:i2]

      if self.get_package_name() != a[4]:
        raise AliPackError('inconsistency in package name: %s' % rawstring)

      i1 = a[0].find( self.platform )
      i2 = a[0].find( '.tar' )

      if i2 > i1:
        self.arch = a[0][i1:i2]
      else:
        self.arch = None

      self._baseurl = base_url

      if len(a) > 5:
        self._deps = a[5].split(',')
      else:
        self._deps = None

    except IndexError:
      raise AliPackError('invalid string format for package definition: %s' % rawstring)


class AliPackError(Exception):
  pass
