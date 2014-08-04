class AliPack:

  '''An ALICE package. Fields:
      - tarball  : package file name (e.g. aliroot-blahblah.tar.gz) - not None
      - software : software's name (e.g. AliRoot) - not None
      - version  : version (e.g. vAN-12345) - not None
      - platform : operating system (e.g. Linux) - may be None
      - arch     : architecture (e.g. Linux-x86_64-2.6-gnu-4.1.2) - may be None
      - org      : virtual organization (e.g. VO_ALICE) not None
      - deps     : array of package deps - may be None (but not empty)
  '''

  def __init__(self, rawstring=None, dictionary=None, baseurl=None):
    if baseurl is None:
      raise AliPackError('baseurl missing')
    if rawstring is not None and dictionary is None:
      self._from_str(rawstring, baseurl)
    elif dictionary is not None and rawstring is None:
      self._from_dict(dictionary, baseurl)

  def __str__(self):
    if self.deps is None:
      deps = '<no deps>'
    else:
      deps = ', '.join(self.deps)
    if self.platform is None:
      platform = '<no platform>'
    else:
      platform = self.platform
    if self.arch is None:
      arch = '<no arch>'
    else:
      arch = self.arch
    return \
      'Package %s:\n' \
      ' - URL      : %s\n' \
      ' - Software : %s\n' \
      ' - Version  : %s\n' \
      ' - Platform : %s\n' \
      ' - Arch     : %s\n' \
      ' - Org      : %s\n' \
      ' - Deps     : %s' \
      % (self.get_package_name(), self.get_url(), self.software, \
         self.version, platform, arch, self.org, deps)

  def get_package_name(self):
    return '%s@%s::%s' % (self.org, self.software, self.version)

  def get_url(self):
    return '%s/%s' % ( self._baseurl, self.tarball )

  def _from_dict(self, dictionary, baseurl):
    '''Constructs the package definition from a dictionary. May throw a
       KeyError.
    '''
    self.tarball  = dictionary['tarball']
    self.software = dictionary['software']
    self.version  = dictionary['version']
    self.platform = dictionary['platform']
    self.arch     = dictionary['arch']
    self.org      = dictionary['org']

    if dictionary['deps'] is not None:
      self.deps = dictionary['deps'].split(',')
    else:
      self.deps = None

    self._baseurl = baseurl


  def _from_str(self, rawstring, baseurl):
    '''Constructs the package definition from a string. String's format is the
       same as lines here: http://pcalienbuild4.cern.ch:8889/tarballs/Packages
    '''
    try:

      rawstring = rawstring.strip()
      a = rawstring.split(None, 5)

      self.tarball  = a[0]
      self.software = a[1]
      self.version  = a[2]

      i2 = a[4].find('@')
      if i2 < 0:
        raise AliPackError('cannot find package organization: %s' % rawstring)
      self.org = a[4][:i2]

      if self.get_package_name() != a[4]:
        raise AliPackError('inconsistency in package name: %s' % rawstring)

      # check if a[3] ("platform") is in the form <os>-<cpu>
      i3 = a[3].find('-')
      if i3 > 0:
        i1 = a[0].find( a[3] )
        if i1 >= 0:
          i1 += i3 + 1
        i2 = a[0].find( '.tar' )
        if i2 > i1:
          self.arch = a[0][i1:i2]
          self.platform = a[3][0:i3]
        else:
          self.arch = None
          self.platform = None
      else:
        self.arch = None
        self.platform = None

      self._baseurl = baseurl

      if len(a) > 5:
        self.deps = a[5].split(',')
      else:
        self.deps = None

    except IndexError:
      raise AliPackError('invalid string format for package definition: %s' % rawstring)


class AliPackError(Exception):
  pass
